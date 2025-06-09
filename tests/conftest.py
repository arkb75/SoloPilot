#!/usr/bin/env python3
"""
Shared test configuration and fixtures for SoloPilot.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Mock all network calls to prevent actual API calls during testing."""
    monkeypatch.setenv("NO_NETWORK", "1")

    # Mock boto3 client for Bedrock
    def mock_boto3_client(*args, **kwargs):
        mock_client = MagicMock()
        # Mock successful responses for bedrock-runtime client
        mock_response = MagicMock()
        mock_response.__getitem__.return_value.read.return_value = (
            '{"content": [{"text": "Mock LLM response"}]}'
        )
        mock_client.invoke_model.return_value = mock_response
        mock_client.list_foundation_models.return_value = {"modelSummaries": []}
        return mock_client

    monkeypatch.setattr("boto3.client", mock_boto3_client)

    # Mock LangChain ChatBedrock
    def mock_chatbedrock_invoke(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.content = "Mock LangChain response"
        return mock_response

    try:
        from langchain_aws import ChatBedrock  # noqa: F401

        monkeypatch.setattr("langchain_aws.ChatBedrock.invoke", mock_chatbedrock_invoke)
    except ImportError:
        pass  # LangChain not available, skip mock
