#!/bin/bash

# Deploy email forwarder Lambda
set -e

FUNCTION_NAME="solopilot-email-forwarder"
REGION="us-east-2"
ROLE_ARN="arn:aws:iam::392894085110:role/email-intake-lambda-role"

echo "Creating deployment package for email forwarder..."

# Create temp directory
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

# Copy the forwarder code
cp /Users/rafaykhurram/projects/SoloPilot/src/agents/email_intake/email_forwarder.py lambda_function.py

# Create zip
zip -r forwarder-lambda.zip lambda_function.py

# Check if function exists
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --profile root 2>/dev/null; then
    echo "Updating existing function..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://forwarder-lambda.zip \
        --region $REGION \
        --profile root
        
    # Update configuration
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --environment Variables="{
            FORWARD_FROM=noreply@abdulkhurram.com,
            FORWARD_TO=rafaykhurram@live.com,
            EMAIL_BUCKET=solopilot-emails
        }" \
        --region $REGION \
        --profile root
else
    echo "Creating new function..."
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime python3.9 \
        --role $ROLE_ARN \
        --handler lambda_function.lambda_handler \
        --timeout 30 \
        --memory-size 256 \
        --zip-file fileb://forwarder-lambda.zip \
        --environment Variables="{
            FORWARD_FROM=noreply@abdulkhurram.com,
            FORWARD_TO=rafaykhurram@live.com,
            EMAIL_BUCKET=solopilot-emails
        }" \
        --description "Forwards emails from rafay@abdulkhurram.com to rafaykhurram@live.com" \
        --region $REGION \
        --profile root
fi

# Clean up
cd -
rm -rf $TEMP_DIR

echo "Email forwarder Lambda deployed successfully!"
echo "Function ARN: arn:aws:lambda:$REGION:392894085110:function:$FUNCTION_NAME"