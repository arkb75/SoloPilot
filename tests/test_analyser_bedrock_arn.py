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
    """Test that analyser uses inference profile ARN as model_id."""
    # Create a temporary config file with ARN
    config_data = {
        "llm": {
            "primary": "bedrock",
            "bedrock": {
                "inference_profile_arn": "arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-3-5-haiku-20241022-v1:0",
                "region": "us-east-2",
            },
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        # Mock ChatBedrock to capture initialization parameters
        with patch("agents.analyser.parser.ChatBedrock") as mock_chatbedrock:
            mock_instance = MagicMock()
            mock_chatbedrock.return_value = mock_instance

            # Clear NO_NETWORK to allow Bedrock initialization
            with patch.dict(os.environ, {"NO_NETWORK": "0"}, clear=False):
                # Import and initialize TextParser
                from agents.analyser.parser import TextParser

                parser = TextParser(config_path=config_path)

                # Verify ChatBedrock was called with the ARN as model_id
                mock_chatbedrock.assert_called_once_with(
                    model_id="arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-3-5-haiku-20241022-v1:0",
                    region_name="us-east-2",
                    model_kwargs={"temperature": 0.1, "max_tokens": 2048},
                )

                # Verify the parser has the LLM initialized
                assert parser.primary_llm == mock_instance

    finally:
        os.unlink(config_path)


def test_analyser_respects_no_network():
    """Test that analyser skips Bedrock initialization when NO_NETWORK=1."""
    config_data = {
        "llm": {
            "primary": "bedrock",
            "bedrock": {
                "inference_profile_arn": "arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-3-5-haiku-20241022-v1:0",
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
    with patch("agents.analyser.parser.ChatBedrock") as mock_chatbedrock:
        mock_instance = MagicMock()
        mock_chatbedrock.return_value = mock_instance

        # Clear NO_NETWORK to allow Bedrock initialization
        with patch.dict(os.environ, {"NO_NETWORK": "0"}, clear=False):
            # Import and initialize TextParser with non-existent config
            from agents.analyser.parser import TextParser

            TextParser(config_path="non_existent_config.yaml")

            # Verify ChatBedrock was called with the fallback ARN
            mock_chatbedrock.assert_called_once_with(
                model_id="arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-3-5-haiku-20241022-v1:0",
                region_name="us-east-2",
                model_kwargs={"temperature": 0.1, "max_tokens": 2048},
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
        with patch("agents.analyser.parser.ChatBedrock") as mock_chatbedrock:
            mock_instance = MagicMock()
            mock_chatbedrock.return_value = mock_instance

            # Set environment variables including clearing NO_NETWORK
            test_arn = "arn:aws:bedrock:us-west-2:123456789012:inference-profile/test"
            with patch.dict(
                os.environ,
                {"BEDROCK_IP_ARN": test_arn, "BEDROCK_REGION": "us-west-2", "NO_NETWORK": "0"},
            ):
                from agents.analyser.parser import TextParser

                TextParser(config_path=config_path)

                # Verify ChatBedrock was called with the env var values
                mock_chatbedrock.assert_called_once_with(
                    model_id=test_arn,
                    region_name="us-west-2",
                    model_kwargs={"temperature": 0.1, "max_tokens": 2048},
                )

    finally:
        os.unlink(config_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
