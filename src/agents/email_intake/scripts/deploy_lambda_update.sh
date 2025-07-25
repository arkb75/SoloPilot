#!/bin/bash
# Deploy Lambda function update with conversation ID fix

set -e

FUNCTION_NAME="solopilot-email-intake"
REGION="${AWS_REGION:-us-east-2}"

echo "🚀 Deploying Lambda function update..."

# Get the repository root (go up from scripts dir)
REPO_ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
EMAIL_INTAKE_DIR="$REPO_ROOT/src/agents/email_intake"

# Create deployment package with proper directory structure
echo "📦 Creating deployment package..."
rm -rf /tmp/lambda_deploy
mkdir -p /tmp/lambda_deploy/src/agents/email_intake

# Copy all Python files to preserve src structure
cp "$EMAIL_INTAKE_DIR"/*.py /tmp/lambda_deploy/src/agents/email_intake/

# Also copy the main handler to root for Lambda entry point
cp "$EMAIL_INTAKE_DIR/lambda_function.py" /tmp/lambda_deploy/

# Create zip file
cd /tmp/lambda_deploy
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
echo "✅ Lambda function updated successfully!"
aws lambda get-function-configuration \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query '{LastModified: LastModified, State: State, StateReason: StateReason}' \
    --output table

# Clean up
rm -rf /tmp/lambda_deploy

echo ""
echo "Next steps:"
echo "1. Run the table creation script: python scripts/create_message_map_table.py"
echo "2. Test the email threading with real emails"
echo "3. Monitor CloudWatch logs for any errors"
