#!/bin/bash
# Deploy API Lambda function with email sending capability

set -e

FUNCTION_NAME="email-agent-api"
REGION="${AWS_REGION:-us-east-2}"

echo "🚀 Deploying API Lambda function..."

# Get the repository root (go up from scripts dir)
REPO_ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
EMAIL_INTAKE_DIR="$REPO_ROOT/src/agents/email_intake"

# Create deployment package with proper directory structure
echo "📦 Creating deployment package..."
rm -rf /tmp/api_lambda_deploy
mkdir -p /tmp/api_lambda_deploy/src/agents/email_intake

# Copy the main handler file to root
cp "$EMAIL_INTAKE_DIR/api/lambda_api.py" /tmp/api_lambda_deploy/

# Copy all required modules to preserve src structure
cp "$EMAIL_INTAKE_DIR/email_sender.py" /tmp/api_lambda_deploy/src/agents/email_intake/
cp "$EMAIL_INTAKE_DIR/conversation_state.py" /tmp/api_lambda_deploy/src/agents/email_intake/
cp "$EMAIL_INTAKE_DIR/utils.py" /tmp/api_lambda_deploy/src/agents/email_intake/
cp "$EMAIL_INTAKE_DIR/pdf_generator.py" /tmp/api_lambda_deploy/src/agents/email_intake/

# Also copy email_sender and other deps to root for backward compatibility
cp "$EMAIL_INTAKE_DIR/email_sender.py" /tmp/api_lambda_deploy/
cp "$EMAIL_INTAKE_DIR/conversation_state.py" /tmp/api_lambda_deploy/
cp "$EMAIL_INTAKE_DIR/utils.py" /tmp/api_lambda_deploy/
cp "$EMAIL_INTAKE_DIR/pdf_generator.py" /tmp/api_lambda_deploy/

# Create zip file
cd /tmp/api_lambda_deploy
zip -r function.zip .

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
