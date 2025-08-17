#!/bin/bash
# Deploy PDF Lambda function with esbuild bundling

set -e

FUNCTION_NAME="solopilot-document-generation"
REGION="${AWS_REGION:-us-east-2}"

echo "🚀 Deploying PDF Lambda function with bundling..."

# Build the bundle
echo "📦 Building bundle with esbuild..."
npm run build

# Check bundle size
BUNDLE_SIZE=$(du -sh dist/index.js | cut -f1)
echo "📏 Bundle size: $BUNDLE_SIZE"

# Create deployment package
echo "📦 Creating deployment package..."
npm run package

# Check package size
PACKAGE_SIZE=$(du -sh function.zip | cut -f1)
echo "📦 Package size: $PACKAGE_SIZE"

# Update Lambda function code
echo "📤 Updating Lambda function code..."
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://function.zip \
    --region $REGION

# Update handler to point to bundled file
echo "🔧 Updating Lambda handler..."
aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --handler index.handler \
    --region $REGION \
    --output text > /dev/null

# Wait for update to complete
echo "⏳ Waiting for update to complete..."
aws lambda wait function-updated \
    --function-name $FUNCTION_NAME \
    --region $REGION

# Get function info
echo "✅ PDF Lambda function updated successfully!"
aws lambda get-function-configuration \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query '{LastModified: LastModified, State: State, CodeSize: CodeSize}' \
    --output table

# Clean up
rm -f function.zip

echo ""
echo "Next steps:"
echo "1. Test PDF generation via email intake or API"
echo "2. Monitor CloudWatch logs for any errors"
echo "3. Check S3 bucket for generated PDFs"