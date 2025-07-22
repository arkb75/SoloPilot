#!/bin/bash
# Deploy API Lambda function with email sending capability

set -e

FUNCTION_NAME="email-agent-api"
REGION="${AWS_REGION:-us-east-2}"

echo "🚀 Deploying API Lambda function..."

# Change to email_intake directory
cd "$(dirname "$0")/.."

# Create deployment package
echo "📦 Creating deployment package..."
mkdir -p /tmp/api_lambda_deploy

# Copy API files
cp -r api/*.py /tmp/api_lambda_deploy/

# Copy shared modules that API needs
cp email_sender.py /tmp/api_lambda_deploy/
# Include conversation state manager so API Lambda can modify conversation records
cp conversation_state.py /tmp/api_lambda_deploy/
cp utils.py /tmp/api_lambda_deploy/

# Create zip file
cd /tmp/api_lambda_deploy
zip -r function.zip ./*.py

# Update Lambda function code
echo "📤 Updating Lambda function code..."
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://function.zip \
    --region $REGION

# Wait for update to complete
echo "⏳ Waiting for update to complete..."
aws lambda wait function-updated \
    --function-name $FUNCTION_NAME \
    --region $REGION

# Get function info
echo "✅ API Lambda function updated successfully!"
aws lambda get-function-configuration \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query '{LastModified: LastModified, State: State, Handler: Handler}' \
    --output table

# Clean up
rm -rf /tmp/api_lambda_deploy

echo ""
echo "Next steps:"
echo "1. Test the approval endpoint via API or frontend"
echo "2. Monitor CloudWatch logs for email sending"