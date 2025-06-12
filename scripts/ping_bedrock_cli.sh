#!/bin/bash
# Direct AWS CLI Bedrock Testing Script
# Demonstrates correct AWS CLI syntax for inference profiles

set -e

# Configuration
REGION="us-east-2"
INFERENCE_PROFILE_ARN="arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-3-5-haiku-20241022-v1:0"

# Check for NO_NETWORK
if [ "$NO_NETWORK" = "1" ]; then
    echo "🚫 NO_NETWORK=1, skipping AWS CLI Bedrock test"
    exit 0
fi

echo "🔧 AWS CLI Bedrock Ping Test"
echo "============================="

# Check AWS CLI availability
if ! command -v aws >/dev/null 2>&1; then
    echo "❌ AWS CLI not installed"
    echo "Install with: pip install awscli or brew install awscli"
    exit 1
fi

echo "📦 AWS CLI Version: $(aws --version)"

# Check AWS credentials
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo "❌ AWS credentials not configured"
    echo "Run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "🔑 AWS Account: $ACCOUNT_ID"

# Create temporary files
BODY_FILE=$(mktemp /tmp/bedrock_body.XXXXXX.json)
OUTPUT_FILE=$(mktemp /tmp/bedrock_output.XXXXXX.json)

# Cleanup function
cleanup() {
    rm -f "$BODY_FILE" "$OUTPUT_FILE"
}
trap cleanup EXIT

# Create request body
cat > "$BODY_FILE" << EOF
{
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 10,
    "temperature": 0.1,
    "messages": [
        {
            "role": "user", 
            "content": "Say hello"
        }
    ]
}
EOF

echo "📍 Region: $REGION"
echo "🔗 Inference Profile ARN: $INFERENCE_PROFILE_ARN"
echo "📝 Sending test request..."

# Execute AWS CLI command with correct syntax
if aws bedrock-runtime invoke-model \
    --model-id "$INFERENCE_PROFILE_ARN" \
    --body "file://$BODY_FILE" \
    --cli-binary-format raw-in-base64-out \
    --region "$REGION" \
    "$OUTPUT_FILE"; then
    
    echo "✅ AWS CLI Bedrock test successful!"
    
    # Parse response
    if command -v jq >/dev/null 2>&1; then
        echo "📊 Response details:"
        echo "   Content: $(jq -r '.content[0].text' "$OUTPUT_FILE" 2>/dev/null || echo "N/A")"
        echo "   Input tokens: $(jq -r '.usage.input_tokens' "$OUTPUT_FILE" 2>/dev/null || echo "N/A")"
        echo "   Output tokens: $(jq -r '.usage.output_tokens' "$OUTPUT_FILE" 2>/dev/null || echo "N/A")"
    else
        echo "📄 Raw response (install jq for formatted output):"
        head -c 200 "$OUTPUT_FILE"
        echo "..."
    fi
    
    echo "🎉 Bedrock CLI ping test passed!"
else
    echo "❌ AWS CLI Bedrock test failed"
    echo "💡 Troubleshooting:"
    echo "   1. Verify AWS credentials: aws sts get-caller-identity"
    echo "   2. Check Bedrock permissions: bedrock:InvokeModel"
    echo "   3. Verify inference profile exists in region: $REGION"
    echo "   4. Check account access to profile: $INFERENCE_PROFILE_ARN"
    exit 1
fi