#!/usr/bin/env python3
"""
Base AI Provider Interface for SoloPilot

Defines the standard interface that all AI providers must implement.
Enables swapping between different LLM providers (Bedrock, OpenAI, CodeWhisperer, etc.)
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class BaseProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def generate_code(self, prompt: str, files: Optional[List[Path]] = None) -> str:
        """
        Generate code based on prompt and optional file context.
        
        Args:
            prompt: The instruction prompt for code generation
            files: Optional list of file paths to include as context
            
        Returns:
            Generated code as a string
            
        Raises:
            ProviderError: If code generation fails
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
    
    def __init__(self, message: str, provider_name: str = "unknown", original_error: Optional[Exception] = None):
        self.provider_name = provider_name
        self.original_error = original_error
        super().__init__(message)


class ProviderUnavailableError(ProviderError):
    """Raised when a provider is not available or misconfigured."""
    pass


class ProviderTimeoutError(ProviderError):
    """Raised when a provider request times out."""
    pass


class ProviderQuotaError(ProviderError):
    """Raised when a provider quota is exceeded."""
    pass