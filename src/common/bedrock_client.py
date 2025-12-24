#!/usr/bin/env python3
"""
Standardized Bedrock client and error handling for SoloPilot agents.
Provides consistent retry logic, error messages, and debugging across all agents.
"""

import json
import os
import random
import time
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError, ParamValidationError


class BedrockError(Exception):
    """Base exception for Bedrock-related errors."""

    pass


class BedrockAccessError(BedrockError):
    """Raised when Bedrock access is denied or credentials are invalid."""

    pass


class BedrockValidationError(BedrockError):
    """Raised when Bedrock request validation fails."""

    pass


class BedrockNetworkError(BedrockError):
    """Raised when network connectivity to Bedrock fails."""

    pass


class StandardizedBedrockClient:
    """Standardized Bedrock client with consistent error handling and retry logic."""

    def __init__(self, inference_profile_arn: str, region: str = "us-east-2"):
        """Initialize the standardized Bedrock client."""
        self.inference_profile_arn = inference_profile_arn
        self.region = region
        self.client = None

        # Check for offline mode
        if os.getenv("NO_NETWORK") == "1":
            raise BedrockNetworkError(
                "🚫 NO_NETWORK=1 is set. Cannot initialize Bedrock client in offline mode."
            )

        self._initialize_client()

    def _initialize_client(self):
        """Initialize the boto3 Bedrock client with validation."""
        try:
            # Validate credentials first
            self._validate_credentials()

            # Initialize client
            self.client = boto3.client("bedrock-runtime", region_name=self.region)

            # Validate inference profile access
            self._validate_inference_profile()

        except (ClientError, BotoCoreError) as e:
            raise BedrockAccessError(f"Failed to initialize Bedrock client: {e}") from e

    def _validate_credentials(self):
        """Validate AWS credentials are available."""
        has_env = all(os.getenv(k) for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"))
        has_profile = os.path.exists(os.path.expanduser("~/.aws/credentials"))

        if not (has_env or has_profile):
            raise BedrockAccessError(
                "❌ AWS credentials not found. "
                "Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or configure ~/.aws/credentials"
            )

    def _validate_inference_profile(self):
        """Validate inference profile ARN format."""
        if not self.inference_profile_arn:
            raise BedrockValidationError("❌ Inference profile ARN is required")

        if not self.inference_profile_arn.startswith("arn:aws:bedrock:"):
            raise BedrockValidationError(
                f"❌ Invalid inference profile ARN format: {self.inference_profile_arn}. "
                "Expected format: arn:aws:bedrock:region:account:inference-profile/profile-id"
            )

    def _model_id_from_arn(self) -> str:
        """Extract model ID from inference profile ARN."""
        return self.inference_profile_arn.split("/")[-1]

    def _invoke_with_signature(
        self, model_id: str, inference_profile_arn: Optional[str], body: dict
    ) -> tuple[str, dict]:
        """Helper to invoke Bedrock with conditional parameters.

        Returns:
            Tuple of (response_text, response_metadata) where metadata includes headers.
        """
        kwargs = {
            "modelId": model_id,
            "body": json.dumps(body),
            "contentType": "application/json",
        }
        if inference_profile_arn:
            kwargs["inferenceProfileArn"] = inference_profile_arn

        response = self.client.invoke_model(**kwargs)
        response_body = json.loads(response["body"].read())

        # Extract cost-related headers
        response_metadata = {
            "ResponseMetadata": response.get("ResponseMetadata", {}),
            "model_id": model_id,
            "inference_profile_arn": inference_profile_arn,
        }

        return response_body["content"][0]["text"], response_metadata

    def invoke_model(
        self, messages: list, max_tokens: int = 2048, temperature: float = 0.1, max_retries: int = 3
    ) -> str:
        """
        Invoke Bedrock model with standardized retry logic and error handling.

        Args:
            messages: List of message objects in Anthropic format
            max_tokens: Maximum tokens to generate
            temperature: Temperature for response generation
            max_retries: Maximum number of retry attempts

        Returns:
            Generated text response

        Raises:
            BedrockError: For various Bedrock-related failures
        """
        if not self.client:
            raise BedrockError("Bedrock client not initialized")

        model_id = self._model_id_from_arn()
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        last_exception = None

        for attempt in range(max_retries):
            try:
                # Try modern signature first (ARN as modelId)
                response_text, _ = self._invoke_with_signature(
                    self.inference_profile_arn, None, body
                )
                return response_text

            except ParamValidationError as e:
                if "inferenceProfileArn" not in str(e):
                    raise BedrockValidationError(f"Parameter validation failed: {e}") from e

                # Try legacy signature (modelId + inferenceProfileArn)
                try:
                    response_text, _ = self._invoke_with_signature(
                        model_id, self.inference_profile_arn, body
                    )
                    return response_text
                except (ClientError, BotoCoreError) as legacy_e:
                    last_exception = legacy_e

            except (ClientError, BotoCoreError) as e:
                last_exception = e

            # Handle retry logic
            if attempt < max_retries - 1:
                # Determine if this is a retryable error
                error_str = str(last_exception)
                if any(
                    err in error_str for err in ["AccessDeniedException", "ValidationException"]
                ):
                    # Don't retry access/validation errors
                    break

                # Exponential backoff with jitter
                wait_time = (2**attempt) + random.uniform(0, 1)
                print(
                    f"🔄 Bedrock call failed (attempt {attempt + 1}/{max_retries}): {last_exception}"
                )
                print(f"   Retrying in {wait_time:.1f} seconds...")
                time.sleep(wait_time)
            else:
                print(f"❌ Final Bedrock attempt failed: {last_exception}")

        # Classify and re-raise the final exception
        error_str = str(last_exception)
        if "AccessDeniedException" in error_str:
            raise BedrockAccessError(
                f"❌ Bedrock access denied. ARN: {self.inference_profile_arn}. "
                "Verify you have bedrock:InvokeModel permissions and profile access."
            ) from last_exception
        elif "ValidationException" in error_str:
            raise BedrockValidationError(
                f"❌ Bedrock validation error: {last_exception}"
            ) from last_exception
        elif any(
            network_err in error_str
            for network_err in ["ConnectionError", "TimeoutError", "EndpointConnectionError"]
        ):
            raise BedrockNetworkError(
                f"❌ Bedrock network error: {last_exception}"
            ) from last_exception
        else:
            raise BedrockError(f"❌ Bedrock API error: {last_exception}") from last_exception

    def invoke_model_with_metadata(
        self,
        messages: list,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        max_retries: int = 3,
        timeout: Optional[int] = None,
    ) -> tuple[str, dict]:
        """
        Invoke Bedrock model and return both response and metadata for cost tracking.

        Args:
            messages: List of message objects in Anthropic format
            max_tokens: Maximum tokens to generate
            temperature: Temperature for response generation
            max_retries: Maximum number of retry attempts

        Returns:
            Tuple of (response_text, metadata_dict)

        Raises:
            BedrockError: For various Bedrock-related failures
        """
        if not self.client:
            raise BedrockError("Bedrock client not initialized")

        model_id = self._model_id_from_arn()
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        last_exception = None

        for attempt in range(max_retries):
            try:
                # Try modern signature first (ARN as modelId)
                return self._invoke_with_signature(self.inference_profile_arn, None, body)

            except ParamValidationError as e:
                if "inferenceProfileArn" not in str(e):
                    raise BedrockValidationError(f"Parameter validation failed: {e}") from e

                # Try legacy signature (modelId + inferenceProfileArn)
                try:
                    return self._invoke_with_signature(model_id, self.inference_profile_arn, body)
                except (ClientError, BotoCoreError) as legacy_e:
                    last_exception = legacy_e

            except (ClientError, BotoCoreError) as e:
                last_exception = e

            # Handle retry logic (same as invoke_model)
            if attempt < max_retries - 1:
                error_str = str(last_exception)
                if any(
                    err in error_str for err in ["AccessDeniedException", "ValidationException"]
                ):
                    break

                wait_time = (2**attempt) + random.uniform(0, 1)
                print(
                    f"🔄 Bedrock call failed (attempt {attempt + 1}/{max_retries}): {last_exception}"
                )
                print(f"   Retrying in {wait_time:.1f} seconds...")
                time.sleep(wait_time)
            else:
                print(f"❌ Final Bedrock attempt failed: {last_exception}")

        # Same error handling as invoke_model
        error_str = str(last_exception)
        if "AccessDeniedException" in error_str:
            raise BedrockAccessError(
                f"❌ Bedrock access denied. ARN: {self.inference_profile_arn}. "
                "Verify you have bedrock:InvokeModel permissions and profile access."
            ) from last_exception
        elif "ValidationException" in error_str:
            raise BedrockValidationError(
                f"❌ Bedrock validation error: {last_exception}"
            ) from last_exception
        elif any(
            network_err in error_str
            for network_err in ["ConnectionError", "TimeoutError", "EndpointConnectionError"]
        ):
            raise BedrockNetworkError(
                f"❌ Bedrock network error: {last_exception}"
            ) from last_exception
        else:
            raise BedrockError(f"❌ Bedrock API error: {last_exception}") from last_exception

    def simple_invoke(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.1) -> str:
        """Simple single-message invoke for convenience."""
        messages = [{"role": "user", "content": prompt}]
        return self.invoke_model(messages, max_tokens, temperature)

    def simple_invoke_with_metadata(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        timeout: Optional[int] = None,
    ) -> tuple[str, dict]:
        """Simple single-message invoke with metadata for cost tracking."""
        messages = [{"role": "user", "content": prompt}]
        return self.invoke_model_with_metadata(messages, max_tokens, temperature, timeout=timeout)


def create_bedrock_client(config: Dict[str, Any]) -> StandardizedBedrockClient:
    """
    Factory function to create a standardized Bedrock client from config.

    Args:
        config: Configuration dictionary containing bedrock settings

    Returns:
        Initialized StandardizedBedrockClient

    Raises:
        BedrockError: If client creation fails
    """
    bedrock_config = config.get("llm", {}).get("bedrock", {})

    inference_profile_arn = bedrock_config.get("inference_profile_arn")
    region = bedrock_config.get("region", "us-east-2")

    if not inference_profile_arn:
        raise BedrockValidationError(
            "❌ No inference_profile_arn found in config. "
            "Update config/model_config.yaml with a valid ARN."
        )

    return StandardizedBedrockClient(inference_profile_arn, region)


def get_standardized_error_message(error: Exception, context: str = "") -> str:
    """
    Generate standardized error messages with troubleshooting guidance.

    Args:
        error: The exception that occurred
        context: Additional context (e.g., "analyser", "planner", "dev")

    Returns:
        Formatted error message with troubleshooting steps
    """
    context_prefix = f"[{context}] " if context else ""

    if isinstance(error, BedrockAccessError):
        return f"""
{context_prefix}❌ Bedrock Access Error: {error}

💡 Troubleshooting:
   1. Verify AWS credentials: aws sts get-caller-identity
   2. Check IAM permissions: bedrock:InvokeModel
   3. Verify inference profile exists and is accessible
   4. Check region configuration matches profile region
"""

    elif isinstance(error, BedrockValidationError):
        return f"""
{context_prefix}❌ Bedrock Validation Error: {error}

💡 Troubleshooting:
   1. Check inference profile ARN format
   2. Verify model is available in the specified region
   3. Check request parameters (max_tokens, temperature, etc.)
"""

    elif isinstance(error, BedrockNetworkError):
        return f"""
{context_prefix}❌ Bedrock Network Error: {error}

💡 Troubleshooting:
   1. Check internet connectivity
   2. Verify region endpoints are accessible
   3. Check VPC/firewall settings if using private networking
   4. Try setting NO_NETWORK=1 for offline development
"""

    else:
        return f"""
{context_prefix}❌ Bedrock Error: {error}

💡 Troubleshooting:
   1. Check AWS service status: https://status.aws.amazon.com/
   2. Verify your AWS account has Bedrock access
   3. Try different model or region if available
   4. Contact AWS support if issue persists
"""
