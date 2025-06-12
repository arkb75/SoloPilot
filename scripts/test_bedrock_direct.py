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
import pytest
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


@pytest.fixture
def bedrock_config():
    """Load Bedrock configuration for tests."""
    # Skip tests if NO_NETWORK is set
    if os.getenv("NO_NETWORK") == "1":
        pytest.skip("Skipping Bedrock tests due to NO_NETWORK=1")

    arn, region = load_config()
    return {"arn": arn, "region": region}


@pytest.fixture
def arn(bedrock_config):
    """Get inference profile ARN."""
    return bedrock_config["arn"]


@pytest.fixture
def region(bedrock_config):
    """Get AWS region."""
    return bedrock_config["region"]


def test_bedrock_python_sdk(arn, region):
    """Test Bedrock access using Python SDK (boto3)."""
    print("\n🐍 Testing Python SDK (boto3)...")

    # Create Bedrock client
    client = boto3.client("bedrock-runtime", region_name=region)
    acct = boto3.client("sts").get_caller_identity()["Account"]
    print(f"   🔑 AWS Account: {acct}")

    # Test payload
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 5,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": "Hi"}],
    }

    success = False
    try:
        # Try modern signature first (ARN as modelId)
        response = client.invoke_model(
            modelId=arn,
            body=json.dumps(body),
            contentType="application/json",
        )
        response_body = json.loads(response["body"].read())
        tokens_used = response_body.get("usage", {})
        print("   ✅ Modern signature successful")
        print(
            f"   📊 Tokens used: {tokens_used.get('input_tokens', '?')} input, {tokens_used.get('output_tokens', '?')} output"
        )
        success = True

    except ParamValidationError as e:
        if "inferenceProfileArn" not in str(e):
            pytest.fail(f"Parameter validation error: {e}")

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
            print("   ✅ Legacy signature successful")
            print(
                f"   📊 Tokens used: {tokens_used.get('input_tokens', '?')} input, {tokens_used.get('output_tokens', '?')} output"
            )
            success = True

        except (ClientError, BotoCoreError) as e:
            pytest.fail(f"Legacy signature failed: {e}")

    except (ClientError, BotoCoreError) as e:
        pytest.fail(f"Modern signature failed: {e}")

    assert success, "Neither modern nor legacy signature worked"


def test_bedrock_aws_cli(arn, region):
    """Test Bedrock access using AWS CLI."""
    print("\n🔧 Testing AWS CLI...")

    # Check if AWS CLI is available
    try:
        result = subprocess.run(["aws", "--version"], capture_output=True, text=True)
        assert result.returncode == 0, "AWS CLI not available"
        print(f"   📦 {result.stdout.strip()}")
    except FileNotFoundError:
        pytest.skip("AWS CLI not installed")

    # Create temporary files for request and response
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as body_file:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 5,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": "Hi"}],
        }
        json.dump(body, body_file)
        body_file_path = body_file.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as output_file:
        output_file_path = output_file.name

    try:
        # Run AWS CLI command
        cmd = [
            "aws",
            "bedrock-runtime",
            "invoke-model",
            "--model-id",
            arn,
            "--body",
            f"file://{body_file_path}",
            "--cli-binary-format",
            "raw-in-base64-out",
            "--region",
            region,
            output_file_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        assert result.returncode == 0, f"AWS CLI failed: {result.stderr.strip()}"

        # Read response
        with open(output_file_path, "r") as f:
            response_data = json.load(f)

        tokens_used = response_data.get("usage", {})
        print("   ✅ AWS CLI successful")
        print(
            f"   📊 Tokens used: {tokens_used.get('input_tokens', '?')} input, {tokens_used.get('output_tokens', '?')} output"
        )

        # Basic response validation
        assert "content" in response_data, "Response should contain content"

    finally:
        # Clean up temporary files
        try:
            os.unlink(body_file_path)
            os.unlink(output_file_path)
        except OSError:
            pass


def test_account_validation(arn):
    """Validate that the ARN contains the expected account ID."""
    print("\n🔍 Validating account ID...")

    expected_account = "392894085110"
    if expected_account in arn:
        print(f"   ✅ ARN contains expected account ID: {expected_account}")
    else:
        print(f"   ⚠️  ARN does not contain expected account ID: {expected_account}")
        print(f"   📝 ARN: {arn}")
        # Don't fail for this in CI - just warn

    # Basic ARN format validation
    assert arn.startswith("arn:aws:bedrock:"), "ARN should start with arn:aws:bedrock:"
    assert "inference-profile" in arn, "ARN should contain inference-profile"


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
