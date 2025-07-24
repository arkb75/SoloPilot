#!/usr/bin/env python3
"""
AI Provider Factory for SoloPilot

Creates and manages AI provider instances based on configuration and environment variables.
Supports switching between providers via AI_PROVIDER environment variable.
"""

import os
from typing import Any, Dict, Optional

from src.providers.base import BaseProvider, ProviderError, ProviderUnavailableError
from src.providers.bedrock import BedrockProvider
from src.providers.fake import FakeProvider


class ProviderFactory:
    """Factory for creating AI provider instances."""

    @staticmethod
    def create_provider(
        config: Dict[str, Any], provider_override: Optional[str] = None
    ) -> BaseProvider:
        """
        Create an AI provider instance based on configuration and environment.

        Args:
            config: Configuration dictionary
            provider_override: Optional provider name to override environment/config

        Returns:
            Initialized provider instance

        Raises:
            ProviderError: If provider creation fails
        """
        # Determine provider to use (priority: override > env var > config > default)
        provider_name = (
            provider_override
            or os.getenv("AI_PROVIDER")
            or config.get("llm", {}).get("primary", "bedrock")
        ).lower()

        # Handle offline mode
        if os.getenv("NO_NETWORK") == "1":
            print("🚫 NO_NETWORK=1 detected, forcing fake provider for offline mode")
            provider_name = "fake"

        # Create provider based on name
        if provider_name == "bedrock":
            return ProviderFactory._create_bedrock_provider(config)
        elif provider_name == "fake":
            return ProviderFactory._create_fake_provider(config)
        elif provider_name == "codewhisperer":
            return ProviderFactory._create_codewhisperer_provider(config)
        else:
            raise ProviderError(
                f"Unknown provider: {provider_name}. "
                f"Supported providers: bedrock, fake, codewhisperer"
            )

    @staticmethod
    def _create_bedrock_provider(config: Dict[str, Any]) -> BedrockProvider:
        """Create Bedrock provider instance."""
        try:
            provider = BedrockProvider(config)
            if not provider.is_available():
                raise ProviderUnavailableError(
                    "Bedrock provider is not available. Check AWS credentials and configuration.",
                    provider_name="bedrock",
                )
            return provider
        except Exception as e:
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(
                f"Failed to create Bedrock provider: {e}", provider_name="bedrock", original_error=e
            )

    @staticmethod
    def _create_fake_provider(config: Dict[str, Any]) -> FakeProvider:
        """Create fake provider instance."""
        try:
            return FakeProvider(config)
        except Exception as e:
            raise ProviderError(
                f"Failed to create fake provider: {e}", provider_name="fake", original_error=e
            )

    @staticmethod
    def _create_codewhisperer_provider(config: Dict[str, Any]) -> BaseProvider:
        """Create CodeWhisperer provider instance (PoC placeholder)."""
        # Import here to avoid dependency issues if not installed
        try:
            from src.providers.codewhisperer import CodeWhispererProvider

            return CodeWhispererProvider(config)
        except ImportError:
            raise ProviderError(
                "CodeWhisperer provider not available. Missing dependencies or implementation.",
                provider_name="codewhisperer",
            )

    @staticmethod
    def get_available_providers() -> Dict[str, bool]:
        """
        Get information about available providers.

        Returns:
            Dictionary mapping provider names to availability status
        """
        providers = {}

        # Check Bedrock availability
        try:
            # Quick availability check without full initialization
            providers["bedrock"] = os.getenv("NO_NETWORK") != "1" and (
                all(os.getenv(k) for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"))
                or os.path.exists(os.path.expanduser("~/.aws/credentials"))
            )
        except Exception:
            providers["bedrock"] = False

        # Fake provider is always available
        providers["fake"] = True

        # Check CodeWhisperer availability
        try:
            from src.providers.codewhisperer import CodeWhispererProvider

            providers["codewhisperer"] = True
        except ImportError:
            providers["codewhisperer"] = False

        return providers

    @staticmethod
    def get_default_provider() -> str:
        """
        Get the default provider based on environment and availability.

        Returns:
            Default provider name
        """
        # Force fake in offline mode
        if os.getenv("NO_NETWORK") == "1":
            return "fake"

        # Check if AI_PROVIDER is set
        env_provider = os.getenv("AI_PROVIDER")
        if env_provider:
            return env_provider.lower()

        # Check availability and return best option
        available = ProviderFactory.get_available_providers()

        if available.get("bedrock", False):
            return "bedrock"
        elif available.get("codewhisperer", False):
            return "codewhisperer"
        else:
            return "fake"


def create_ai_provider(
    config: Dict[str, Any], provider_override: Optional[str] = None
) -> BaseProvider:
    """
    Convenience function to create an AI provider.

    Args:
        config: Configuration dictionary
        provider_override: Optional provider name override

    Returns:
        Initialized provider instance
    """
    return ProviderFactory.create_provider(config, provider_override)


def get_provider(provider_name: Optional[str] = None, **config_kwargs) -> BaseProvider:
    """
    Get an AI provider instance with simplified interface for dev agent.

    Args:
        provider_name: Optional provider name (falls back to AI_PROVIDER env var)
        **config_kwargs: Configuration parameters

    Returns:
        Initialized provider instance
    """
    # Build config from kwargs or use minimal default
    config = config_kwargs or {
        "llm": {
            "primary": provider_name or "bedrock",
            "bedrock": {
                "inference_profile_arn": os.getenv("BEDROCK_IP_ARN", ""),
                "region": "us-east-2",
                "model_kwargs": {"temperature": 0.1, "max_tokens": 2048},
            },
        }
    }

    return ProviderFactory.create_provider(config, provider_name)
