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
mkdir -p /tmp/api_lambda_deploy/api
mkdir -p /tmp/api_lambda_deploy/src

# Copy the main handler file to api/ directory to match the handler path
cp "$EMAIL_INTAKE_DIR/api/lambda_api.py" /tmp/api_lambda_deploy/api/
cp "$EMAIL_INTAKE_DIR/api/__init__.py" /tmp/api_lambda_deploy/api/ 2>/dev/null || true

# Copy entire src tree for email_intake and storage to avoid missing modules
mkdir -p /tmp/api_lambda_deploy/src/agents
cp -R "$REPO_ROOT/src/agents/email_intake" /tmp/api_lambda_deploy/src/agents/
cp -R "$REPO_ROOT/src/storage" /tmp/api_lambda_deploy/src/

# Include providers and common utilities required by code model
cp -R "$REPO_ROOT/src/providers" /tmp/api_lambda_deploy/src/
cp -R "$REPO_ROOT/src/common" /tmp/api_lambda_deploy/src/

# Include minimal dev context utility used by providers
mkdir -p /tmp/api_lambda_deploy/src/agents/dev
cp "$REPO_ROOT/src/agents/dev/context_packer.py" /tmp/api_lambda_deploy/src/agents/dev/

# No root-level fallbacks needed; all imports use src.* package paths

# Preflight import check to fail fast if packaging misses anything
echo "🔎 Running import preflight..."
python3 - <<'PY'
import sys, types
sys.path.insert(0, '/tmp/api_lambda_deploy')

# Provide lightweight stubs for boto3/botocore to avoid local dependency
if 'boto3' not in sys.modules:
    boto3 = types.ModuleType('boto3')
    def _noop(*a, **k):
        return None
    boto3.client = _noop
    boto3.resource = _noop
    sys.modules['boto3'] = boto3
    # DynamoDB stubs used by TypeDeserializer
    dynamodb = types.ModuleType('boto3.dynamodb')
    sys.modules['boto3.dynamodb'] = dynamodb
    dynamodb_types = types.ModuleType('boto3.dynamodb.types')
    class TypeDeserializer:
        def deserialize(self, v):
            return v
    dynamodb_types.TypeDeserializer = TypeDeserializer
    sys.modules['boto3.dynamodb.types'] = dynamodb_types
    dynamodb_conditions = types.ModuleType('boto3.dynamodb.conditions')
    class Key:
        def __init__(self, *a, **k):
            pass
        def eq(self, *a, **k):
            return self
        def gt(self, *a, **k):
            return self
        def __and__(self, other):
            return self
    dynamodb_conditions.Key = Key
    sys.modules['boto3.dynamodb.conditions'] = dynamodb_conditions

if 'botocore' not in sys.modules:
    botocore = types.ModuleType('botocore')
    sys.modules['botocore'] = botocore
    exceptions = types.ModuleType('botocore.exceptions')
    class ClientError(Exception):
        pass
    class BotoCoreError(Exception):
        pass
    class ParamValidationError(Exception):
        pass
    exceptions.ClientError = ClientError
    exceptions.BotoCoreError = BotoCoreError
    exceptions.ParamValidationError = ParamValidationError
    sys.modules['botocore.exceptions'] = exceptions

def ok(name):
    print(f"   ✅ {name}")

try:
    import api.lambda_api  # noqa: F401
    ok('api.lambda_api')
    import src.providers  # noqa: F401
    ok('src.providers')
    import src.agents.email_intake.vision_analyzer  # noqa: F401
    ok('src.agents.email_intake.vision_analyzer')
    import src.agents.email_intake.patch_builder  # noqa: F401
    ok('src.agents.email_intake.patch_builder')
    import src.storage.s3_proposal_store  # noqa: F401
    ok('src.storage.s3_proposal_store')
except Exception as e:
    print("Preflight import failed:", e)
    sys.exit(1)
PY

# Create zip file
cd /tmp/api_lambda_deploy
zip -r function.zip . >/dev/null

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
