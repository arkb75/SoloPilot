#!/usr/bin/env python3
"""
Base AI Provider Interface for SoloPilot

Defines the standard interface that all AI providers must implement.
Enables swapping between different LLM providers (Bedrock, OpenAI, CodeWhisperer, etc.)
"""

import json
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional


def log_call(func):
    """
    Decorator to log AI provider calls with timing and token usage.

    Logs to logs/llm_calls.log in JSON format:
    {"ts": timestamp, "provider": name, "latency_ms": X, "tokens_in": Y, "tokens_out": Z, ...}
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()

        try:
            # Call the wrapped method
            result = func(self, *args, **kwargs)
            end_time = time.time()

            # Extract metadata if method returns tuple (code, meta)
            if isinstance(result, tuple) and len(result) == 2:
                code, meta = result
                metadata = meta or {}
            else:
                code = result
                metadata = {}

            # Get provider info
            provider_info = self.get_provider_info() if hasattr(self, "get_provider_info") else {}
            provider_name = provider_info.get("name", "unknown")

            # Calculate latency
            latency_ms = int((end_time - start_time) * 1000)

            # Extract token counts with defaults
            tokens_in = metadata.get("tokens_in", len(args[0].split()) if args else 50)
            tokens_out = metadata.get("tokens_out", len(str(code).split()) if code else 100)

            # Create log entry
            log_entry = {
                "ts": datetime.now().isoformat(),
                "provider": provider_name,
                "latency_ms": latency_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            }

            # Add additional metadata
            if "model" in metadata:
                log_entry["model"] = metadata["model"]
            if "cost_usd" in metadata:
                log_entry["cost_usd"] = metadata["cost_usd"]

            log_dir = os.path.join(os.getenv("LLM_LOG_DIR", "logs"))
            if not os.access(log_dir, os.W_OK):
                log_dir = "/tmp/logs"
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "llm_calls.log")

            with open(log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")

            return result

        except Exception as e:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            # Log failed calls too
            provider_info = self.get_provider_info() if hasattr(self, "get_provider_info") else {}
            provider_name = provider_info.get("name", "unknown")

            log_entry = {
                "ts": datetime.now().isoformat(),
                "provider": provider_name,
                "latency_ms": latency_ms,
                "tokens_in": None,
                "tokens_out": None,
                "error": str(e),
                "status": "failed",
            }

            log_dir = os.path.join(os.getenv("LLM_LOG_DIR", "logs"))
            if not os.access(log_dir, os.W_OK):
                log_dir = "/tmp/logs"
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "llm_calls.log")

            with open(log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")

            raise

    return wrapper


class BaseProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    @log_call
    def generate_code(
        self, prompt: str, files: Optional[List[Path]] = None, timeout: Optional[int] = None
    ) -> str:
        """
        Generate code based on prompt and optional file context.

        Args:
            prompt: The instruction prompt for code generation
            files: Optional list of file paths to include as context
            timeout: Optional timeout in seconds (overrides provider default)

        Returns:
            Generated code as a string

        Raises:
            ProviderError: If code generation fails
            ProviderTimeoutError: If request times out
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available and properly configured.

        Returns:
            True if provider can be used, False otherwise
        """
        pass

    @abstractmethod
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about the provider.

        Returns:
            Dictionary with provider metadata (name, model, version, etc.)
        """
        pass

    def get_cost_info(self) -> Optional[Dict[str, Any]]:
        """
        Get cost information for the last request (if supported).

        Returns:
            Dictionary with cost data or None if not supported
        """
        return None


class ProviderError(Exception):
    """Base exception for AI provider errors."""

    def __init__(
        self,
        message: str,
        provider_name: str = "unknown",
        original_error: Optional[Exception] = None,
    ):
        self.provider_name = provider_name
        self.original_error = original_error
        super().__init__(message)


class ProviderUnavailableError(ProviderError):
    """Raised when a provider is not available or misconfigured."""

    pass


class ProviderTimeoutError(ProviderError):
    """Raised when a provider request times out."""

    def __init__(
        self,
        message: str,
        provider_name: str = "unknown",
        timeout_seconds: int = 0,
        original_error: Optional[Exception] = None,
    ):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, provider_name, original_error)


class ProviderQuotaError(ProviderError):
    """Raised when a provider quota is exceeded."""

    pass
