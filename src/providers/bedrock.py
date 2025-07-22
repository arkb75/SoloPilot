#!/usr/bin/env python3
"""
AWS Bedrock AI Provider for SoloPilot

Implements the BaseProvider interface using AWS Bedrock Claude models.
Provides standardized code generation with retry logic and cost tracking.
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.ai_providers.base import (
    BaseProvider,
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    log_call,
)
from agents.common.bedrock_client import (
    BedrockError,
    create_bedrock_client,
    get_standardized_error_message,
)
from agents.dev.context_packer import build_context


class BedrockProvider(BaseProvider):
    """AWS Bedrock provider for code generation."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Bedrock provider with configuration.

        Args:
            config: Configuration dictionary containing bedrock settings
        """
        self.config = config
        self.client = None
        self.last_cost_info = None

        # Try to initialize the client
        try:
            self.client = create_bedrock_client(config)
        except BedrockError as e:
            # Store error but don't raise - let is_available() handle it
            self._init_error = e

    @log_call
    def generate_code(
        self, prompt: str, files: Optional[List[Path]] = None, timeout: Optional[int] = None
    ) -> str:
        """
        Generate code using AWS Bedrock Claude models.

        Args:
            prompt: The instruction prompt for code generation
            files: Optional list of file paths to include as context
            timeout: Optional timeout in seconds (default: 30s)

        Returns:
            Generated code as a string

        Raises:
            ProviderError: If code generation fails
            ProviderTimeoutError: If request times out
        """
        if not self.is_available():
            raise ProviderUnavailableError(
                "Bedrock provider is not available. Check configuration and credentials.",
                provider_name="bedrock",
            )

        # Build enhanced prompt with file context
        enhanced_prompt = self._build_enhanced_prompt(prompt, files)

        try:
            # Get model configuration
            model_config = self.config.get("llm", {}).get("bedrock", {}).get("model_kwargs", {})
            max_tokens = model_config.get("max_tokens", 2048)
            temperature = model_config.get("temperature", 0.1)

            # Set timeout (default 30s, fail fast at 15s for validation)
            request_timeout = timeout or model_config.get("timeout", 30)

            # Add performance guard for complex prompts
            prompt_size = len(enhanced_prompt)
            if prompt_size > 50000 and request_timeout < 60:
                print(f"⚠️ Large prompt ({prompt_size} chars), extending timeout to 60s")
                request_timeout = 60

            # Capture timing and use metadata-enabled invoke with timeout
            start_time = time.time()
            try:
                response_text, metadata = self.client.simple_invoke_with_metadata(
                    enhanced_prompt, max_tokens, temperature, timeout=request_timeout
                )
            except Exception as e:
                if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                    raise ProviderTimeoutError(
                        f"Bedrock request timed out after {request_timeout}s (prompt: {prompt_size} chars)",
                        provider_name="bedrock",
                        timeout_seconds=request_timeout,
                        original_error=e,
                    )
                raise
            end_time = time.time()

            # Store cost information
            self._extract_cost_info(start_time, end_time, metadata)

            return response_text

        except BedrockError as e:
            error_msg = get_standardized_error_message(e, "bedrock-provider")
            raise ProviderError(error_msg, provider_name="bedrock", original_error=e)
        except Exception as e:
            raise ProviderError(
                f"Unexpected error during code generation: {e}",
                provider_name="bedrock",
                original_error=e,
            )

    def is_available(self) -> bool:
        """
        Check if Bedrock provider is available and properly configured.

        Returns:
            True if provider can be used, False otherwise
        """
        return self.client is not None and not hasattr(self, "_init_error")

    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about the Bedrock provider.

        Returns:
            Dictionary with provider metadata
        """
        bedrock_config = self.config.get("llm", {}).get("bedrock", {})

        info = {
            "name": "bedrock",
            "display_name": "AWS Bedrock Claude",
            "available": self.is_available(),
            "region": bedrock_config.get("region", "us-east-2"),
        }

        if self.client:
            info["inference_profile_arn"] = self.client.inference_profile_arn
            info["model_id"] = self.client._model_id_from_arn()
        else:
            info["error"] = str(getattr(self, "_init_error", "Unknown initialization error"))

        return info

    def get_cost_info(self) -> Optional[Dict[str, Any]]:
        """
        Get cost information for the last request.

        Returns:
            Dictionary with cost data or None if not available
        """
        return self.last_cost_info

    def _build_enhanced_prompt(self, prompt: str, files: Optional[List[Path]] = None) -> str:
        """
        Build enhanced prompt with file context.

        Args:
            prompt: Base prompt
            files: Optional list of file paths to include as context

        Returns:
            Enhanced prompt with context
        """
        if not files:
            return prompt

        context_parts = []

        # Add file contents as context
        for file_path in files:
            if file_path.exists() and file_path.is_file():
                try:
                    # For milestone paths, use context_packer
                    if "milestone-" in str(file_path):
                        context = build_context(file_path)
                        if context.strip():
                            context_parts.append(context)
                    else:
                        # For regular files, include content directly
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        if content.strip():
                            context_parts.append(f"## File: {file_path}\n```\n{content}\n```\n")
                except (IOError, UnicodeDecodeError) as e:
                    context_parts.append(f"## File: {file_path}\n(Error reading file: {e})\n")

        # Combine context with prompt
        if context_parts:
            enhanced_prompt = "\n".join(context_parts) + "\n---\n\n" + prompt
            return enhanced_prompt
        else:
            return prompt

    def _extract_cost_info(
        self, start_time: float, end_time: float, metadata: Dict[str, Any]
    ) -> None:
        """
        Extract and store cost information from response metadata.

        Args:
            start_time: Request start time
            end_time: Request end time
            metadata: Response metadata from Bedrock
        """
        # Extract token counts from headers
        headers = metadata.get("ResponseMetadata", {}).get("HTTPHeaders", {})
        tokens_in = headers.get("x-amzn-bedrock-tokens-in")
        tokens_out = headers.get("x-amzn-bedrock-tokens-out")

        # Convert to int if available
        try:
            tokens_in = int(tokens_in) if tokens_in else None
            tokens_out = int(tokens_out) if tokens_out else None
        except (ValueError, TypeError):
            tokens_in = None
            tokens_out = None

        self.last_cost_info = {
            "timestamp": time.time(),
            "model": metadata.get("model_id", "unknown"),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": int((end_time - start_time) * 1000),
            "inference_profile_arn": metadata.get("inference_profile_arn"),
        }
