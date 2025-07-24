#!/usr/bin/env python3
"""
Unit tests for @log_call decorator
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.providers.base import BaseProvider, log_call


class MockProvider(BaseProvider):
    """Mock provider for testing decorator."""

    def __init__(self):
        pass

    @log_call
    def generate_code(self, prompt: str, files=None) -> str:
        return f"Mock code for: {prompt[:20]}..."

    def is_available(self) -> bool:
        return True

    def get_provider_info(self):
        return {"name": "test_provider", "model": "test-model"}


class TestLogCallDecorator:
    """Test cases for @log_call decorator."""

    def test_log_call_basic_functionality(self):
        """Test that the decorator logs calls correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory for isolated logging
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                provider = MockProvider()
                result = provider.generate_code("Test prompt for logging")

                # Check that result is returned correctly
                assert "Mock code for: Test prompt for logg..." in result

                # Check that log file was created
                log_file = Path("logs/llm_calls.log")
                assert log_file.exists()

                # Read and parse log entry
                with open(log_file, "r") as f:
                    log_line = f.read().strip()

                log_entry = json.loads(log_line)

                # Verify log entry structure
                assert "ts" in log_entry
                assert log_entry["provider"] == "test_provider"
                assert log_entry["latency_ms"] >= 0
                assert log_entry["tokens_in"] > 0
                assert log_entry["tokens_out"] > 0

            finally:
                os.chdir(original_cwd)

    def test_log_call_with_exception(self):
        """Test that the decorator logs failed calls."""

        class FailingProvider(BaseProvider):
            def __init__(self):
                pass

            @log_call
            def generate_code(self, prompt: str, files=None) -> str:
                raise Exception("Test failure")

            def is_available(self) -> bool:
                return True

            def get_provider_info(self):
                return {"name": "failing_provider"}

        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                provider = FailingProvider()

                # Should raise the exception
                with pytest.raises(Exception, match="Test failure"):
                    provider.generate_code("Test prompt")

                # But should still log the failure
                log_file = Path("logs/llm_calls.log")
                assert log_file.exists()

                with open(log_file, "r") as f:
                    log_line = f.read().strip()

                log_entry = json.loads(log_line)

                # Verify failure was logged
                assert log_entry["provider"] == "failing_provider"
                assert log_entry["status"] == "failed"
                assert "Test failure" in log_entry["error"]
                assert log_entry["tokens_in"] is None
                assert log_entry["tokens_out"] is None

            finally:
                os.chdir(original_cwd)

    def test_log_call_multiple_calls(self):
        """Test multiple calls are logged separately."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                provider = MockProvider()

                # Make multiple calls
                provider.generate_code("First call")
                provider.generate_code("Second call")
                provider.generate_code("Third call")

                # Check all calls were logged
                log_file = Path("logs/llm_calls.log")
                with open(log_file, "r") as f:
                    lines = f.read().strip().split("\n")

                assert len(lines) == 3

                # Parse all entries
                entries = [json.loads(line) for line in lines]

                # All should be from same provider
                for entry in entries:
                    assert entry["provider"] == "test_provider"
                    assert entry["latency_ms"] >= 0

            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
