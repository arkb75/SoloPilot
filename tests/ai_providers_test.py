#!/usr/bin/env python3
"""
Unit tests for SoloPilot AI Providers

Tests the provider interface, fake provider, and provider factory functionality.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.ai_providers.base import ProviderError, ProviderUnavailableError
from agents.ai_providers.factory import ProviderFactory, create_ai_provider
from agents.ai_providers.fake import FakeProvider


class TestFakeProvider:
    """Test cases for FakeProvider."""

    def test_initialization(self):
        """Test fake provider initialization."""
        provider = FakeProvider()
        assert provider is not None
        assert provider.call_count == 0
        assert provider.is_available() is True

    def test_initialization_with_config(self):
        """Test fake provider initialization with config."""
        config = {"test": "value"}
        provider = FakeProvider(config)
        assert provider.config == config

    def test_generate_code_javascript(self):
        """Test JavaScript code generation."""
        provider = FakeProvider()
        prompt = "Implement user authentication using React and Node.js"

        result = provider.generate_code(prompt)

        assert provider.call_count == 1
        assert "```javascript" in result
        assert "class" in result
        assert "describe(" in result
        assert "test(" in result
        assert "authentication" in result.lower() or "user" in result.lower()

    def test_generate_code_typescript(self):
        """Test TypeScript code generation."""
        provider = FakeProvider()
        prompt = "Create a TypeScript service for API calls"

        result = provider.generate_code(prompt)

        assert "```typescript" in result
        assert "interface" in result
        assert "class" in result
        assert "Promise" in result

    def test_generate_code_python(self):
        """Test Python code generation."""
        provider = FakeProvider()
        prompt = "Build a Python FastAPI endpoint for user management"

        result = provider.generate_code(prompt)

        assert "```python" in result
        assert "class" in result
        assert "def " in result
        assert "async def" in result
        assert "pytest" in result

    def test_generate_code_java(self):
        """Test Java code generation."""
        provider = FakeProvider()
        prompt = "Create a Java Spring Boot controller"

        result = provider.generate_code(prompt)

        assert "```java" in result
        assert "class" in result
        assert "public" in result
        assert "@Test" in result

    def test_generate_code_with_files(self):
        """Test code generation with file context."""
        provider = FakeProvider()

        # Create temporary files
        with tempfile.TemporaryDirectory() as temp_dir:
            js_file = Path(temp_dir) / "test.js"
            js_file.write_text("console.log('test');")

            py_file = Path(temp_dir) / "test.py"
            py_file.write_text("print('test')")

            # Test with JavaScript file (should infer JavaScript)
            result = provider.generate_code("Implement feature", [js_file])
            assert "```javascript" in result

            # Test with Python file (should infer Python)
            result = provider.generate_code("Implement feature", [py_file])
            assert "```python" in result

    def test_provider_info(self):
        """Test provider information."""
        provider = FakeProvider()
        info = provider.get_provider_info()

        assert info["name"] == "fake"
        assert info["display_name"] == "Fake Provider (Testing)"
        assert info["available"] is True
        assert info["model"] == "fake-model-v1"
        assert info["call_count"] == 0
        assert "testing" in info["description"].lower()

    def test_cost_info(self):
        """Test cost information tracking."""
        provider = FakeProvider()

        # Before any calls
        cost_info = provider.get_cost_info()
        assert cost_info["cost_usd"] == 0.0
        assert cost_info["model"] == "fake-model-v1"

        # After a call
        provider.generate_code("test prompt")
        cost_info = provider.get_cost_info()
        assert cost_info["tokens_in"] > 0
        assert cost_info["tokens_out"] == 100
        assert cost_info["latency_ms"] == 50

    def test_language_inference(self):
        """Test language inference logic."""
        provider = FakeProvider()

        # Test prompt-based inference
        assert provider._infer_language("Use React components", None) == "javascript"
        assert provider._infer_language("Build with Django", None) == "python"
        assert provider._infer_language("Create Spring Boot app", None) == "java"
        assert provider._infer_language("Use TypeScript interfaces", None) == "typescript"

        # Test file-based inference
        with tempfile.TemporaryDirectory() as temp_dir:
            ts_file = Path(temp_dir) / "test.ts"
            rs_file = Path(temp_dir) / "test.rs"
            go_file = Path(temp_dir) / "test.go"

            assert provider._infer_language("test", [ts_file]) == "typescript"
            assert provider._infer_language("test", [rs_file]) == "rust"
            assert provider._infer_language("test", [go_file]) == "go"

    def test_task_name_extraction(self):
        """Test task name extraction from prompts."""
        provider = FakeProvider()

        assert "User Authentication" in provider._extract_task_name("Implement user authentication")
        assert "Api Service" in provider._extract_task_name("Create API service endpoint")
        assert "Database Connection" in provider._extract_task_name("Build database connection")
        result = provider._extract_task_name("xyz")
        assert result == "Xyz" or "Generic Task" in result


class TestProviderFactory:
    """Test cases for ProviderFactory."""

    def test_create_fake_provider(self):
        """Test creating fake provider through factory."""
        config = {"llm": {"primary": "fake"}}
        provider = ProviderFactory.create_provider(config)

        assert isinstance(provider, FakeProvider)
        assert provider.is_available()

    def test_create_fake_provider_with_override(self):
        """Test creating fake provider with override."""
        config = {"llm": {"primary": "bedrock"}}  # Config says bedrock
        provider = ProviderFactory.create_provider(config, provider_override="fake")

        assert isinstance(provider, FakeProvider)

    @patch.dict(os.environ, {"AI_PROVIDER": "fake"})
    def test_create_provider_with_env_var(self):
        """Test creating provider with environment variable."""
        config = {"llm": {"primary": "bedrock"}}  # Config says bedrock
        provider = ProviderFactory.create_provider(config)  # But env says fake

        assert isinstance(provider, FakeProvider)

    @patch.dict(os.environ, {"NO_NETWORK": "1"})
    def test_create_provider_offline_mode(self):
        """Test provider creation in offline mode."""
        config = {"llm": {"primary": "bedrock"}}
        provider = ProviderFactory.create_provider(config)

        # Should force fake provider in offline mode
        assert isinstance(provider, FakeProvider)

    @patch.dict(os.environ, {}, clear=True)  # Clear NO_NETWORK to avoid fake override
    def test_create_unknown_provider(self):
        """Test creating unknown provider raises error."""
        config = {"llm": {"primary": "unknown"}}

        with pytest.raises(ProviderError) as exc_info:
            ProviderFactory.create_provider(config, provider_override="unknown")

        assert "Unknown provider" in str(exc_info.value)
        assert "unknown" in str(exc_info.value)

    def test_get_available_providers(self):
        """Test getting available providers."""
        providers = ProviderFactory.get_available_providers()

        assert isinstance(providers, dict)
        assert "fake" in providers
        assert providers["fake"] is True  # Fake is always available

    @patch.dict(os.environ, {"NO_NETWORK": "1"})
    def test_get_default_provider_offline(self):
        """Test getting default provider in offline mode."""
        default = ProviderFactory.get_default_provider()
        assert default == "fake"

    @patch.dict(os.environ, {"AI_PROVIDER": "fake"})
    def test_get_default_provider_with_env(self):
        """Test getting default provider with env var."""
        default = ProviderFactory.get_default_provider()
        assert default == "fake"

    def test_convenience_function(self):
        """Test convenience function create_ai_provider."""
        config = {"llm": {"primary": "fake"}}
        provider = create_ai_provider(config)

        assert isinstance(provider, FakeProvider)


class TestProviderIntegration:
    """Integration tests for provider system."""

    def test_provider_interface_compliance(self):
        """Test that FakeProvider implements BaseProvider interface correctly."""
        provider = FakeProvider()

        # Check interface methods exist and work
        assert hasattr(provider, "generate_code")
        assert hasattr(provider, "is_available")
        assert hasattr(provider, "get_provider_info")
        assert hasattr(provider, "get_cost_info")

        # Test method signatures
        result = provider.generate_code("test prompt")
        assert isinstance(result, str)

        available = provider.is_available()
        assert isinstance(available, bool)

        info = provider.get_provider_info()
        assert isinstance(info, dict)

        cost = provider.get_cost_info()
        assert cost is None or isinstance(cost, dict)

    def test_provider_error_handling(self):
        """Test provider error handling."""
        # Test ProviderError creation
        error = ProviderError("Test error", "test_provider")
        assert error.provider_name == "test_provider"
        assert "Test error" in str(error)

        # Test ProviderUnavailableError
        error = ProviderUnavailableError("Not available", "test_provider")
        assert error.provider_name == "test_provider"
        assert isinstance(error, ProviderError)

    def test_end_to_end_code_generation(self):
        """Test end-to-end code generation workflow."""
        # Create provider through factory
        config = {"llm": {"primary": "fake"}}
        provider = create_ai_provider(config)

        # Generate code
        prompt = "Create a REST API endpoint for user registration"
        result = provider.generate_code(prompt)

        # Verify result
        assert len(result) > 100  # Should be substantial
        assert (
            "API" in result or "api" in result or "Rest" in result or "endpoint" in result.lower()
        )
        # The fake provider extracts task names heuristically, so we just check for reasonable content
        assert "Implementation" in result or "class" in result  # Should have some implementation
        assert "```" in result  # Should have code blocks

        # Check provider info
        info = provider.get_provider_info()
        assert info["available"] is True

        # Check cost info
        cost = provider.get_cost_info()
        assert cost["cost_usd"] == 0.0  # Fake provider is free

    @patch.dict(os.environ, {"AI_PROVIDER": "fake"}, clear=True)
    def test_environment_based_selection(self):
        """Test provider selection based on environment."""
        config = {}  # Empty config

        provider = create_ai_provider(config)
        assert isinstance(provider, FakeProvider)

        # Verify it works
        result = provider.generate_code("test")
        assert len(result) > 0

    def test_multiple_provider_instances(self):
        """Test creating multiple provider instances."""
        config = {"llm": {"primary": "fake"}}

        provider1 = create_ai_provider(config)
        provider2 = create_ai_provider(config)

        # Should be separate instances
        assert provider1 is not provider2

        # Both should work independently
        provider1.generate_code("test 1")
        provider2.generate_code("test 2")

        assert provider1.call_count == 1
        assert provider2.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
