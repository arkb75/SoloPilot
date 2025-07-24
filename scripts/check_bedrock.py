#!/usr/bin/env python3
"""
Bedrock preflight checker for SoloPilot.
Exit non-zero if the configured inference profile ARN cannot be invoked.
For CI (NO_NETWORK=1) it exits 0 immediately.
"""

import json
import os
import re
import sys
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

    with open(config_path) as f:
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

    # Apply environment variable substitution
    bedrock_config = config["llm"]["bedrock"]

    # Override ARN and region from environment if provided
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


def check_bedrock_access():
    """Test Bedrock access with a minimal ping call."""
    # Skip network checks in CI
    if os.getenv("NO_NETWORK") == "1":
        print("🚫 NO_NETWORK=1, skipping Bedrock check")
        sys.exit(0)

    print("🔍 Checking Bedrock access...")

    arn, region = load_config()
    model_id = model_id_from_arn(arn)

    print(f"📍 Region: {region}")
    print(f"🏷️  Model ID: {model_id}")
    print(f"🔗 ARN: {arn}")

    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        acct = boto3.client("sts").get_caller_identity()["Account"]
        print(f"🔑 Using AWS account: {acct}")
    except Exception as e:
        print(f"❌ Failed to create Bedrock client: {e}")
        print("💡 Check your AWS credentials and region configuration")
        sys.exit(1)

    # Minimal test payload (5 tokens max)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 5,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": "Hi"}],
    }

    try:
        # Try modern signature first (ARN as modelId)
        client.invoke_model(
            modelId=arn,
            body=json.dumps(body),
            contentType="application/json",
        )
        print("✅ Bedrock access confirmed (modern signature)")
        return True

    except ParamValidationError as e:
        if "inferenceProfileArn" not in str(e):
            print(f"❌ Parameter validation error: {e}")
            sys.exit(1)

        # Try legacy signature
        try:
            client.invoke_model(
                modelId=model_id,
                inferenceProfileArn=arn,
                body=json.dumps(body),
                contentType="application/json",
            )
            print("✅ Bedrock access confirmed (legacy signature)")
            return True

        except (ClientError, BotoCoreError) as e:
            print(f"❌ Bedrock access failed: {e}")
            if "AccessDeniedException" in str(e):
                print("\n💡 Troubleshooting:")
                print("   1. Verify your AWS credentials are configured")
                print("   2. Check you have bedrock:InvokeModel permissions")
                print(f"   3. Ensure access to inference profile: {arn}")
                print(f"   4. Verify the profile exists in region: {region}")
            sys.exit(1)

    except (ClientError, BotoCoreError) as e:
        print(f"❌ Bedrock access failed: {e}")
        if "AccessDeniedException" in str(e):
            print("\n💡 Troubleshooting:")
            print("   1. Verify your AWS credentials are configured")
            print("   2. Check you have bedrock:InvokeModel permissions")
            print(f"   3. Ensure access to inference profile: {arn}")
            print(f"   4. Verify the profile exists in region: {region}")
        sys.exit(1)


if __name__ == "__main__":
    check_bedrock_access()
    print("🎉 Bedrock preflight check passed!")
