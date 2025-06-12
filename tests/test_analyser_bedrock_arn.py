#!/usr/bin/env python3
"""
Unit tests for SoloPilot Analyser Bedrock ARN usage.
Tests that analyser properly uses inference profile ARNs.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_analyser_uses_bedrock_arn():
    """Test that analyser uses inference profile ARN correctly via standardized client."""
    # Create a temporary config file with ARN
    config_data = {
        "llm": {
            "primary": "bedrock",
            "bedrock": {
                "inference_profile_arn": "arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0",
                "region": "us-east-2",
            },
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        # Mock standardized client to verify it gets initialized with correct config
        with patch("agents.analyser.parser.create_bedrock_client") as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            # Clear NO_NETWORK to allow Bedrock initialization
            with patch.dict(os.environ, {"NO_NETWORK": "0"}, clear=False):
                # Import and initialize TextParser
                from agents.analyser.parser import TextParser

                parser = TextParser(config_path=config_path)

                # Verify standardized client was created with the config
                mock_create_client.assert_called_once()
                config_arg = mock_create_client.call_args[0][0]
                assert (
                    config_arg["llm"]["bedrock"]["inference_profile_arn"]
                    == "arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0"
                )

                # Verify the parser has the standardized client initialized
                assert parser.standardized_client == mock_client

    finally:
        os.unlink(config_path)


def test_analyser_respects_no_network():
    """Test that analyser skips Bedrock initialization when NO_NETWORK=1."""
    config_data = {
        "llm": {
            "primary": "bedrock",
            "bedrock": {
                "inference_profile_arn": "arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0",
                "region": "us-east-2",
            },
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        # Mock ChatBedrock to ensure it's never called
        with patch("agents.analyser.parser.ChatBedrock") as mock_chatbedrock:
            with patch.dict(os.environ, {"NO_NETWORK": "1"}):
                # Import and initialize TextParser
                from agents.analyser.parser import TextParser

                parser = TextParser(config_path=config_path)

                # Verify ChatBedrock was never called
                mock_chatbedrock.assert_not_called()

                # Verify the parser has no LLM initialized
                assert parser.primary_llm is None
                assert parser.fallback_llm is None

    finally:
        os.unlink(config_path)


def test_analyser_fallback_config():
    """Test that analyser uses fallback config when no config file exists."""
    # Use a non-existent config path
    with patch("agents.analyser.parser.create_bedrock_client") as mock_create_client:
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Clear NO_NETWORK to allow Bedrock initialization
        with patch.dict(os.environ, {"NO_NETWORK": "0"}, clear=False):
            # Import and initialize TextParser with non-existent config
            from agents.analyser.parser import TextParser

            TextParser(config_path="non_existent_config.yaml")

            # Verify standardized client was created with fallback config
            mock_create_client.assert_called_once()
            config_arg = mock_create_client.call_args[0][0]
            assert (
                config_arg["llm"]["bedrock"]["inference_profile_arn"]
                == "arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0"
            )


def test_analyser_env_var_substitution():
    """Test that analyser properly substitutes environment variables in config."""
    # Create config with environment variable
    config_data = {
        "llm": {
            "primary": "bedrock",
            "bedrock": {
                "inference_profile_arn": "${BEDROCK_IP_ARN:-arn:aws:bedrock:us-east-2:392894085110:inference-profile/default}",
                "region": "${BEDROCK_REGION:-us-east-2}",
            },
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        with patch("agents.analyser.parser.create_bedrock_client") as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            # Set environment variables including clearing NO_NETWORK
            test_arn = "arn:aws:bedrock:us-west-2:123456789012:inference-profile/test"
            with patch.dict(
                os.environ,
                {"BEDROCK_IP_ARN": test_arn, "BEDROCK_REGION": "us-west-2", "NO_NETWORK": "0"},
            ):
                from agents.analyser.parser import TextParser

                TextParser(config_path=config_path)

                # Verify standardized client was created with env var substituted values
                mock_create_client.assert_called_once()
                config_arg = mock_create_client.call_args[0][0]
                assert config_arg["llm"]["bedrock"]["inference_profile_arn"] == test_arn
                assert config_arg["llm"]["bedrock"]["region"] == "us-west-2"

    finally:
        os.unlink(config_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
