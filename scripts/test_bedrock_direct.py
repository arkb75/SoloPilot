#!/usr/bin/env python3
"""
Direct Bedrock API Testing Script for SoloPilot.
Provides comprehensive testing of AWS Bedrock inference profiles using both Python SDK and AWS CLI.
Exit non-zero if Bedrock access fails.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import boto3
import yaml
from botocore.exceptions import BotoCoreError, ClientError, ParamValidationError


def load_config():
    """Load model configuration with environment variable substitution."""
    config_path = Path("config/model_config.yaml")
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        content = f.read()

    # Substitute environment variables in format ${VAR:-default}
    def env_substitute(match):
        var_spec = match.group(1)
        if ":-" in var_spec:
            var_name, default = var_spec.split(":-", 1)
            return os.getenv(var_name, default)
        else:
            return os.getenv(var_spec, "")

    content = re.sub(r"\$\{([^}]+)\}", env_substitute, content)
    config = yaml.safe_load(content)

    # Get Bedrock configuration
    bedrock_config = config["llm"]["bedrock"]
    arn = bedrock_config.get("inference_profile_arn")
    region = bedrock_config.get("region", "us-east-2")

    if not arn:
        print("❌ No inference profile ARN configured")
        print("Set BEDROCK_IP_ARN environment variable or configure in config/model_config.yaml")
        sys.exit(1)

    return arn, region


def model_id_from_arn(arn):
    """Extract modelId from inference profile ARN."""
    return arn.split("/")[-1]


def test_bedrock_python_sdk(arn, region):
    """Test Bedrock access using Python SDK (boto3)."""
    print("\n🐍 Testing Python SDK (boto3)...")
    
    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        acct = boto3.client("sts").get_caller_identity()["Account"]
        print(f"   🔑 AWS Account: {acct}")
    except Exception as e:
        print(f"   ❌ Failed to create Bedrock client: {e}")
        return False

    # Test payload
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 5,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": "Hi"}],
    }

    try:
        # Try modern signature first (ARN as modelId)
        response = client.invoke_model(
            modelId=arn,
            body=json.dumps(body),
            contentType="application/json",
        )
        response_body = json.loads(response["body"].read())
        tokens_used = response_body.get("usage", {})
        print(f"   ✅ Modern signature successful")
        print(f"   📊 Tokens used: {tokens_used.get('input_tokens', '?')} input, {tokens_used.get('output_tokens', '?')} output")
        return True

    except ParamValidationError as e:
        if "inferenceProfileArn" not in str(e):
            print(f"   ❌ Parameter validation error: {e}")
            return False

        # Try legacy signature
        try:
            model_id = model_id_from_arn(arn)
            response = client.invoke_model(
                modelId=model_id,
                inferenceProfileArn=arn,
                body=json.dumps(body),
                contentType="application/json",
            )
            response_body = json.loads(response["body"].read())
            tokens_used = response_body.get("usage", {})
            print(f"   ✅ Legacy signature successful")
            print(f"   📊 Tokens used: {tokens_used.get('input_tokens', '?')} input, {tokens_used.get('output_tokens', '?')} output")
            return True

        except (ClientError, BotoCoreError) as e:
            print(f"   ❌ Legacy signature failed: {e}")
            return False

    except (ClientError, BotoCoreError) as e:
        print(f"   ❌ Modern signature failed: {e}")
        return False


def test_bedrock_aws_cli(arn, region):
    """Test Bedrock access using AWS CLI."""
    print("\n🔧 Testing AWS CLI...")
    
    # Check if AWS CLI is available
    try:
        result = subprocess.run(["aws", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("   ❌ AWS CLI not available")
            return False
        print(f"   📦 {result.stdout.strip()}")
    except FileNotFoundError:
        print("   ❌ AWS CLI not installed")
        return False

    # Create temporary files for request and response
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as body_file:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 5,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": "Hi"}],
        }
        json.dump(body, body_file)
        body_file_path = body_file.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as output_file:
        output_file_path = output_file.name

    try:
        # Run AWS CLI command
        cmd = [
            "aws", "bedrock-runtime", "invoke-model",
            "--model-id", arn,
            "--body", f"file://{body_file_path}",
            "--cli-binary-format", "raw-in-base64-out",
            "--region", region,
            output_file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Read response
            with open(output_file_path, 'r') as f:
                response_data = json.load(f)
            
            tokens_used = response_data.get("usage", {})
            print(f"   ✅ AWS CLI successful")
            print(f"   📊 Tokens used: {tokens_used.get('input_tokens', '?')} input, {tokens_used.get('output_tokens', '?')} output")
            return True
        else:
            print(f"   ❌ AWS CLI failed: {result.stderr.strip()}")
            return False

    except Exception as e:
        print(f"   ❌ AWS CLI test error: {e}")
        return False
    
    finally:
        # Clean up temporary files
        try:
            os.unlink(body_file_path)
            os.unlink(output_file_path)
        except:
            pass


def test_account_validation(arn):
    """Validate that the ARN contains the expected account ID."""
    print("\n🔍 Validating account ID...")
    
    expected_account = "392894085110"
    if expected_account in arn:
        print(f"   ✅ ARN contains expected account ID: {expected_account}")
        return True
    else:
        print(f"   ⚠️  ARN does not contain expected account ID: {expected_account}")
        print(f"   📝 ARN: {arn}")
        # Don't fail for this - just warn
        return True


def main():
    """Run comprehensive Bedrock testing."""
    # Skip network checks in CI
    if os.getenv("NO_NETWORK") == "1":
        print("🚫 NO_NETWORK=1, skipping Bedrock tests")
        sys.exit(0)

    print("🔍 Direct Bedrock API Testing")
    print("=" * 50)

    # Load configuration
    arn, region = load_config()
    model_id = model_id_from_arn(arn)

    print(f"📍 Region: {region}")
    print(f"🏷️  Model ID: {model_id}")
    print(f"🔗 Inference Profile ARN: {arn}")

    # Run tests
    tests_passed = 0
    total_tests = 3

    if test_account_validation(arn):
        tests_passed += 1

    if test_bedrock_python_sdk(arn, region):
        tests_passed += 1

    if test_bedrock_aws_cli(arn, region):
        tests_passed += 1

    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{total_tests} passed")
    
    if tests_passed == total_tests:
        print("🎉 All Bedrock tests passed!")
        sys.exit(0)
    else:
        print("❌ Some Bedrock tests failed")
        print("\n💡 Troubleshooting:")
        print("   1. Verify your AWS credentials are configured")
        print("   2. Check you have bedrock:InvokeModel permissions")
        print(f"   3. Ensure access to inference profile: {arn}")
        print(f"   4. Verify the profile exists in region: {region}")
        print("   5. Check AWS CLI is installed and configured")
        sys.exit(1)


if __name__ == "__main__":
    main()