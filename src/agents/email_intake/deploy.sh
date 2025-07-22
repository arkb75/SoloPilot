#!/bin/bash

# Email Agent Management System Deployment Script

set -e

echo "Email Agent Management System Deployment"
echo "========================================"

# Check AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed"
    exit 1
fi

# Configuration
REGION=${AWS_REGION:-"us-east-1"}
STACK_NAME="email-agent-management"
FRONTEND_BUCKET="email-agent-frontend-$(aws sts get-caller-identity --query Account --output text)"
API_LAMBDA_NAME="email-agent-api"
EMAIL_LAMBDA_NAME="email-intake-manual"

echo "Region: $REGION"
echo "Stack Name: $STACK_NAME"
echo "Frontend Bucket: $FRONTEND_BUCKET"

# Step 1: Package and deploy Lambda functions
echo ""
echo "Step 1: Packaging Lambda functions..."

# Package API Lambda
cd api
zip -r ../api-lambda.zip lambda_api.py ../conversation_state_v3.py ../utils.py
cd ..

# Package Email Lambda  
zip -r email-lambda.zip lambda_function_manual_approval.py conversational_responder_v2.py conversation_state_v3.py email_parser.py requirement_extractor.py pdf_generator.py utils.py

# Step 2: Update Lambda functions
echo ""
echo "Step 2: Updating Lambda functions..."

# Update API Lambda
aws lambda update-function-code \
    --function-name $API_LAMBDA_NAME \
    --zip-file fileb://api-lambda.zip \
    --region $REGION || echo "API Lambda not found, please create it first"

# Update Email Lambda
aws lambda update-function-code \
    --function-name $EMAIL_LAMBDA_NAME \
    --zip-file fileb://email-lambda.zip \
    --region $REGION || echo "Email Lambda not found, please create it first"

# Step 3: Build and deploy frontend
echo ""
echo "Step 3: Building frontend..."

cd frontend
npm install
npm run build

# Create S3 bucket if it doesn't exist
aws s3api create-bucket \
    --bucket $FRONTEND_BUCKET \
    --region $REGION \
    --create-bucket-configuration LocationConstraint=$REGION 2>/dev/null || true

# Enable static website hosting
aws s3 website s3://$FRONTEND_BUCKET/ \
    --index-document index.html \
    --error-document index.html

# Upload frontend files
aws s3 sync dist/ s3://$FRONTEND_BUCKET/ \
    --delete \
    --cache-control "public, max-age=31536000" \
    --exclude "index.html"

aws s3 cp dist/index.html s3://$FRONTEND_BUCKET/ \
    --cache-control "no-cache, no-store, must-revalidate"

# Set bucket policy for public access
cat > bucket-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$FRONTEND_BUCKET/*"
        }
    ]
}
EOF

aws s3api put-bucket-policy \
    --bucket $FRONTEND_BUCKET \
    --policy file://bucket-policy.json

cd ..

# Step 4: Output deployment information
echo ""
echo "Deployment Complete!"
echo "==================="
echo ""
echo "Frontend URL: http://$FRONTEND_BUCKET.s3-website-$REGION.amazonaws.com"
echo ""
echo "Next Steps:"
echo "1. Create/Update API Gateway using the api_gateway_config.yaml"
echo "2. Update frontend/.env with the API Gateway URL"
echo "3. Configure API Gateway API key for authentication"
echo "4. Update Lambda environment variables with correct table names and configurations"
echo ""

# Cleanup
rm -f api-lambda.zip email-lambda.zip bucket-policy.json

echo "Done!"