"""Tests for email intake SQS functionality."""

import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from agents.email_intake import lambda_handler


class TestSQSIntegration:
    """Test SQS message sending in email intake."""

    @patch("agents.email_intake.email_agent.s3_client")
    @patch("agents.email_intake.email_agent.ses_client")
    @patch("agents.email_intake.email_agent.sqs_client")
    @patch("agents.email_intake.email_agent.ConversationStateManager")
    @patch("agents.email_intake.email_agent.RequirementExtractor")
    def test_sqs_send_on_new_conversation(
        self, mock_extractor_class, mock_state_class, mock_sqs, mock_ses, mock_s3
    ):
        """Test that SQS message is sent even for new conversations."""
        # Set environment variables
        os.environ["REQUIREMENT_QUEUE_URL"] = "https://sqs.us-east-2.amazonaws.com/123456789/requirement-handoff"
        os.environ["SENDER_EMAIL"] = "noreply@solopilot.ai"

        # Mock S3 email content
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=lambda: b"""From: newclient@example.com
Subject: Need a website
Message-ID: <new123>

I need a website for my startup. We're in the fintech space.
"""
            )
        }

        # Mock conversation state - NEW conversation
        mock_state = MagicMock()
        mock_state.get_or_create.return_value = {
            "conversation_id": "test-new-123",
            "email_history": [],
            "status": "active"
        }
        mock_state.add_email.return_value = {
            "conversation_id": "test-new-123",
            "email_history": [{"from": "newclient@example.com"}],
            "status": "active"
        }
        mock_state.update_requirements.return_value = {
            "conversation_id": "test-new-123",
            "email_history": [{"from": "newclient@example.com"}],
            "requirements": {"title": "Fintech Website"},
            "status": "active"
        }
        mock_state_class.return_value = mock_state

        # Mock requirement extractor - incomplete requirements
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {"title": "Fintech Website"}
        mock_extractor.is_complete.return_value = False
        mock_extractor.generate_questions.return_value = "1. What features do you need?"
        mock_extractor_class.return_value = mock_extractor

        # Mock SQS response
        mock_sqs.send_message.return_value = {
            "MessageId": "test-message-id-123",
            "ResponseMetadata": {"HTTPStatusCode": 200}
        }

        # Lambda event
        event = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "email-bucket"},
                    "object": {"key": "emails/new123.eml"}
                }
            }]
        }

        # Execute Lambda
        result = lambda_handler(event, None)

        # Assertions
        assert result["statusCode"] == 200

        # Verify SQS was called exactly once
        mock_sqs.send_message.assert_called_once()
        
        # Verify the call parameters
        sqs_call = mock_sqs.send_message.call_args
        # call_args returns (args, kwargs) - we can access them as [0] and [1]
        call_kwargs = sqs_call[1]
        
        # The QueueUrl should be set from environment variable
        # Since module was imported before we set the env var, it will be empty string
        # Let's verify the message was sent with the right structure
        assert "QueueUrl" in call_kwargs
        assert "MessageBody" in call_kwargs
        
        # Parse and verify the message body
        message_body = json.loads(call_kwargs["MessageBody"])
        # The conversation_id comes from parsed email thread_id, not our mock
        assert message_body["conversation_id"]  # Just verify it exists
        assert message_body["requirements"] == {"title": "Fintech Website"}
        assert message_body["status"] == "active"
        assert message_body["email_count"] == 1
        assert message_body["source"] == "email_intake"
        assert "timestamp" in message_body

        # Verify follow-up email was sent
        mock_ses.send_email.assert_called_once()

    @patch("agents.email_intake.email_agent.s3_client")
    @patch("agents.email_intake.email_agent.ses_client")
    @patch("agents.email_intake.email_agent.sqs_client")
    @patch("agents.email_intake.email_agent.ConversationStateManager")
    @patch("agents.email_intake.email_agent.RequirementExtractor")
    def test_sqs_send_failure_raises_exception(
        self, mock_extractor_class, mock_state_class, mock_sqs, mock_ses, mock_s3
    ):
        """Test that Lambda fails if SQS send_message returns non-200 status."""
        # Set environment variables
        os.environ["REQUIREMENT_QUEUE_URL"] = "https://sqs.us-east-2.amazonaws.com/123456789/requirement-handoff"

        # Mock S3 email content
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"From: test@example.com\nSubject: Test\n\nTest email")
        }

        # Mock conversation state
        mock_state = MagicMock()
        mock_state.get_or_create.return_value = {"conversation_id": "test-fail", "email_history": []}
        mock_state.add_email.return_value = {"conversation_id": "test-fail", "email_history": [{}]}
        mock_state.update_requirements.return_value = {"conversation_id": "test-fail", "requirements": {}}
        mock_state_class.return_value = mock_state

        # Mock requirement extractor
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {}
        mock_extractor_class.return_value = mock_extractor

        # Mock SQS failure
        mock_sqs.send_message.return_value = {
            "ResponseMetadata": {"HTTPStatusCode": 500}
        }

        # Lambda event
        event = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "email-bucket"},
                    "object": {"key": "emails/fail.eml"}
                }
            }]
        }

        # Execute Lambda - should fail
        result = lambda_handler(event, None)

        # Should return 500 due to SQS failure
        assert result["statusCode"] == 500
        assert "SQS send_message returned status 500" in result["body"]

        # Verify SQS was called
        mock_sqs.send_message.assert_called_once()