"""Comprehensive tests for enhanced email intake with race condition handling."""

import json
import threading
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from agents.email_intake.conversation_state_v2 import ConversationStateManagerV2
from agents.email_intake.lambda_function_v2 import lambda_handler
from agents.email_intake.utils import EmailThreadingUtils


class TestEmailThreadingUtils:
    """Test RFC 5322 compliant email threading utilities."""

    def test_extract_message_id(self):
        """Test Message-ID extraction."""
        assert (
            EmailThreadingUtils.extract_message_id("<abc123@example.com>") == "abc123@example.com"
        )
        assert EmailThreadingUtils.extract_message_id("abc123@example.com") == "abc123@example.com"
        assert (
            EmailThreadingUtils.extract_message_id("  <abc123@example.com>  ")
            == "abc123@example.com"
        )
        assert EmailThreadingUtils.extract_message_id("") == ""

    def test_parse_references(self):
        """Test References header parsing."""
        refs = "<msg1@example.com> <msg2@example.com> <msg3@example.com>"
        parsed = EmailThreadingUtils.parse_references(refs)
        assert parsed == ["msg1@example.com", "msg2@example.com", "msg3@example.com"]

        # Test with angle brackets and whitespace
        refs = "  <msg1@example.com>   <msg2@example.com>  "
        parsed = EmailThreadingUtils.parse_references(refs)
        assert parsed == ["msg1@example.com", "msg2@example.com"]

    def test_determine_conversation_id_new_thread(self):
        """Test conversation ID for new thread."""
        conv_id, orig_id = EmailThreadingUtils.determine_conversation_id(
            message_id="<new123@example.com>",
            in_reply_to="",
            references=[],
            subject="New Project",
            from_addr="client@example.com",
        )

        assert len(conv_id) == 16  # Hash length
        assert orig_id == "new123@example.com"

    def test_determine_conversation_id_reply(self):
        """Test conversation ID for reply."""
        conv_id, orig_id = EmailThreadingUtils.determine_conversation_id(
            message_id="<reply123@example.com>",
            in_reply_to="<original123@example.com>",
            references=["original123@example.com"],
            subject="Re: Project",
            from_addr="client@example.com",
        )

        expected_hash = EmailThreadingUtils.hash_conversation_id("original123@example.com")
        assert conv_id == expected_hash
        assert orig_id == "original123@example.com"

    def test_determine_conversation_id_fallback(self):
        """Test conversation ID fallback when no headers."""
        conv_id, orig_id = EmailThreadingUtils.determine_conversation_id(
            message_id="",
            in_reply_to="",
            references=[],
            subject="Project Help",
            from_addr="client@example.com",
            date="2024-01-15T10:00:00Z",
        )

        assert len(conv_id) == 16
        assert orig_id == ""  # No original message ID

    def test_extract_participants(self):
        """Test participant extraction."""
        email_data = {
            "from": "Sender@Example.com",
            "to": ["recipient1@example.com", "Recipient2@Example.com"],
            "cc": "cc@example.com",
        }

        participants = EmailThreadingUtils.extract_participants(email_data)
        assert participants == {
            "sender@example.com",
            "recipient1@example.com",
            "recipient2@example.com",
            "cc@example.com",
        }

    def test_is_automated_response(self):
        """Test automated response detection."""
        # Out of office
        assert (
            EmailThreadingUtils.is_automated_response(
                "I am out of office until Monday", "Re: Project Update"
            )
            is True
        )

        # Auto-reply
        assert (
            EmailThreadingUtils.is_automated_response(
                "This is an automatic reply", "Auto-Reply: Your request"
            )
            is True
        )

        # Normal email
        assert (
            EmailThreadingUtils.is_automated_response(
                "Thanks for the update on the project", "Re: Project Update"
            )
            is False
        )

    def test_extract_quoted_text(self):
        """Test quoted text extraction."""
        email_body = """Hi there,

This is my response.

On Jan 15, 2024, John wrote:
> Original message here
> With multiple lines

Thanks!
"""
        new_content, quoted = EmailThreadingUtils.extract_quoted_text(email_body)

        assert "This is my response" in new_content
        assert "Original message here" in quoted
        assert "On Jan 15, 2024, John wrote:" in quoted


class TestConversationStateV2:
    """Test thread-safe conversation state management."""

    @patch("agents.email_intake.conversation_state_v2.boto3.resource")
    def test_fetch_or_create_new_conversation(self, mock_boto):
        """Test creating new conversation atomically."""
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        # Mock get_item returns empty (new conversation)
        mock_table.get_item.return_value = {}

        # Mock successful put_item
        mock_table.put_item.return_value = {}

        manager = ConversationStateManagerV2()
        initial_email = {
            "from": "client@example.com",
            "subject": "New Project",
            "body": "I need help",
        }

        result = manager.fetch_or_create_conversation(
            "conv123", "msg123@example.com", initial_email
        )

        # Verify put_item called with condition
        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args[1]
        assert call_args["ConditionExpression"] == "attribute_not_exists(conversation_id)"

        # Verify conversation structure
        item = call_args["Item"]
        assert item["conversation_id"] == "conv123"
        assert item["original_message_id"] == "msg123@example.com"
        assert item["last_seq"] == Decimal(0)
        assert "ttl" in item

    @patch("agents.email_intake.conversation_state_v2.boto3.resource")
    def test_concurrent_conversation_creation(self, mock_boto):
        """Test handling concurrent conversation creation."""
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        # First get_item returns empty
        mock_table.get_item.side_effect = [
            {},  # First check - not found
            {
                "Item": {"conversation_id": "conv123", "last_seq": Decimal(0)}
            },  # Second check after conflict
        ]

        # put_item raises ConditionalCheckFailedException
        error = ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
        mock_table.put_item.side_effect = error

        manager = ConversationStateManagerV2()
        result = manager.fetch_or_create_conversation(
            "conv123", "msg123@example.com", {"from": "test@example.com"}
        )

        # Should fetch existing after conflict
        assert mock_table.get_item.call_count == 2
        assert result["conversation_id"] == "conv123"

    @patch("agents.email_intake.conversation_state_v2.boto3.resource")
    def test_append_email_with_optimistic_lock_success(self, mock_boto):
        """Test successful email append with optimistic locking."""
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        # Mock current state
        current_state = {
            "conversation_id": "conv123",
            "last_seq": Decimal(5),
            "email_history": [],
            "participants": ["client@example.com"],
            "thread_references": ["msg1@example.com"],
        }
        mock_table.get_item.return_value = {"Item": current_state}

        # Mock successful update
        updated_state = current_state.copy()
        updated_state["last_seq"] = Decimal(6)
        updated_state["email_history"] = [{"email_id": "conv123-abc"}]
        mock_table.update_item.return_value = {"Attributes": updated_state}

        manager = ConversationStateManagerV2()
        result = manager.append_email_with_retry(
            "conv123", {"from": "client@example.com", "body": "Update"}
        )

        # Verify condition expression includes current seq
        update_call = mock_table.update_item.call_args[1]
        assert ":current_seq" in update_call["ExpressionAttributeValues"]
        assert update_call["ExpressionAttributeValues"][":current_seq"] == Decimal(5)
        assert update_call["ExpressionAttributeValues"][":new_seq"] == Decimal(6)

        assert result["last_seq"] == 6

    @patch("agents.email_intake.conversation_state_v2.boto3.resource")
    def test_append_email_with_retry_on_conflict(self, mock_boto):
        """Test email append with retry on optimistic lock conflict."""
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        # Mock two different states (simulating concurrent update)
        state1 = {
            "conversation_id": "conv123",
            "last_seq": Decimal(5),
            "email_history": [],
            "participants": set(),
            "thread_references": [],
        }
        state2 = {
            "conversation_id": "conv123",
            "last_seq": Decimal(6),  # Changed by another process
            "email_history": [{"email_id": "other-email"}],
            "participants": set(),
            "thread_references": [],
        }
        mock_table.get_item.side_effect = [{"Item": state1}, {"Item": state2}]

        # First update fails, second succeeds
        error = ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        success_response = {"Attributes": {"last_seq": Decimal(7)}}
        mock_table.update_item.side_effect = [error, success_response]

        manager = ConversationStateManagerV2()
        result = manager.append_email_with_retry(
            "conv123", {"from": "client@example.com", "body": "Update"}, max_retries=1
        )

        # Should retry once
        assert mock_table.get_item.call_count == 2
        assert mock_table.update_item.call_count == 2
        assert result["last_seq"] == 7

    @patch("agents.email_intake.conversation_state_v2.boto3.resource")
    def test_update_requirements_with_version_control(self, mock_boto):
        """Test requirements update with version control."""
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        # Mock current state
        current_state = {
            "conversation_id": "conv123",
            "requirements_version": Decimal(3),
            "requirements": {"title": "Old Project"},
        }
        mock_table.get_item.return_value = {"Item": current_state}

        # Mock successful update
        mock_table.update_item.return_value = {"Attributes": {"requirements_version": Decimal(4)}}

        manager = ConversationStateManagerV2()
        new_reqs = {"title": "Updated Project", "features": []}

        result = manager.update_requirements_atomic("conv123", new_reqs, expected_version=3)

        # Verify version check in condition
        update_call = mock_table.update_item.call_args[1]
        assert update_call["ExpressionAttributeValues"][":current_version"] == Decimal(3)
        assert update_call["ExpressionAttributeValues"][":new_version"] == Decimal(4)

    def test_email_entry_preparation(self):
        """Test email entry preparation with all fields."""
        manager = ConversationStateManagerV2()

        email_data = {
            "message_id": "<email123@example.com>",
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Project Update",
            "body": "Here's the update\n\nOn Jan 1 wrote:\n> Previous message",
            "timestamp": "2024-01-15T10:00:00Z",
            "attachments": [{"filename": "doc.pdf", "size": 1024}],
        }

        current_state = {"conversation_id": "conv123"}

        entry = manager._prepare_email_entry("conv123", email_data, current_state)

        assert entry["email_id"].startswith("conv123-")
        assert entry["message_id"] == "<email123@example.com>"
        assert entry["new_content"] == "Here's the update"
        assert entry["is_automated"] is False
        assert len(entry["attachments"]) == 1


class TestRaceConditionScenarios:
    """Test specific race condition scenarios."""

    @patch("agents.email_intake.conversation_state_v2.boto3.resource")
    def test_concurrent_email_appends(self, mock_boto):
        """Test handling of concurrent email appends from multiple Lambdas."""
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        manager = ConversationStateManagerV2()

        # Simulate race condition with threading
        results = []
        errors = []

        def append_email(email_num):
            try:
                # Each thread sees seq=5 initially
                mock_table.get_item.return_value = {
                    "Item": {
                        "conversation_id": "conv123",
                        "last_seq": Decimal(5),
                        "email_history": [],
                        "participants": set(),
                        "thread_references": [],
                    }
                }

                # First attempt always fails for threads 2+
                if email_num > 1:
                    error = ClientError(
                        {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
                    )
                    # Second get shows updated seq
                    updated_item = {
                        "Item": {
                            "conversation_id": "conv123",
                            "last_seq": Decimal(5 + email_num - 1),
                            "email_history": [],
                            "participants": set(),
                            "thread_references": [],
                        }
                    }
                    mock_table.get_item.side_effect = [
                        mock_table.get_item.return_value,
                        updated_item,
                    ]
                    mock_table.update_item.side_effect = [
                        error,
                        {"Attributes": {"last_seq": Decimal(5 + email_num)}},
                    ]
                else:
                    mock_table.update_item.return_value = {"Attributes": {"last_seq": Decimal(6)}}

                result = manager.append_email_with_retry(
                    "conv123", {"from": f"sender{email_num}@example.com"}, max_retries=2
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Simulate 3 concurrent Lambda executions
        threads = []
        for i in range(1, 4):
            t = threading.Thread(target=append_email, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        # All should succeed with retries
        assert len(errors) == 0
        assert len(results) == 3

    @patch("agents.email_intake.conversation_state_v2.boto3.resource")
    def test_requirements_update_race_condition(self, mock_boto):
        """Test concurrent requirements updates."""
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        # Initial state
        mock_table.get_item.return_value = {
            "Item": {
                "conversation_id": "conv123",
                "requirements_version": Decimal(1),
                "requirements": {"title": "Initial"},
            }
        }

        # First update succeeds
        mock_table.update_item.return_value = {"Attributes": {"requirements_version": Decimal(2)}}

        manager = ConversationStateManagerV2()

        # Lambda 1 updates successfully
        result1 = manager.update_requirements_atomic(
            "conv123", {"title": "Updated by Lambda 1"}, expected_version=1
        )
        assert result1["requirements_version"] == 2

        # Lambda 2 tries with old version - should fail
        with pytest.raises(ValueError, match="Version mismatch"):
            manager.update_requirements_atomic(
                "conv123", {"title": "Updated by Lambda 2"}, expected_version=1
            )


class TestLambdaHandlerV2Integration:
    """Integration tests for enhanced Lambda handler."""

    @patch("agents.email_intake.lambda_function_v2.s3_client")
    @patch("agents.email_intake.lambda_function_v2.ses_client")
    @patch("agents.email_intake.lambda_function_v2.sqs_client")
    @patch("agents.email_intake.lambda_function_v2.ConversationStateManagerV2")
    @patch("agents.email_intake.lambda_function_v2.RequirementExtractor")
    def test_lambda_handles_new_conversation(
        self, mock_extractor_class, mock_state_class, mock_sqs, mock_ses, mock_s3
    ):
        """Test Lambda handling new conversation thread."""
        # Mock S3 email
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=lambda: b"""From: sarah@startup.com
To: hello@solopilot.ai
Subject: Need help with SaaS platform
Message-ID: <initial123@startup.com>
Date: Mon, 15 Jan 2024 10:00:00 +0000

Hi,

We're building a SaaS platform and need help with:
- User authentication
- Subscription management
- Analytics dashboard

Budget is $15-20k, timeline 3 months.

Thanks,
Sarah
"""
            )
        }

        # Mock state manager
        mock_state = MagicMock()
        mock_state.fetch_or_create_conversation.return_value = {
            "conversation_id": "abc123def456",
            "last_seq": 0,
            "email_history": [],
            "status": "active",
        }
        mock_state.append_email_with_retry.return_value = {
            "conversation_id": "abc123def456",
            "last_seq": 1,
            "email_history": [{"email_id": "abc123def456-001"}],
            "requirements_version": 0,
        }
        mock_state.update_requirements_atomic.return_value = {
            "conversation_id": "abc123def456",
            "requirements_version": 1,
        }
        mock_state_class.return_value = mock_state

        # Mock extractor - incomplete requirements
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {
            "title": "SaaS Platform",
            "features": [
                {"name": "User Auth", "desc": "Authentication system"},
                {"name": "Subscriptions", "desc": "Payment management"},
            ],
        }
        mock_extractor.is_complete.return_value = False
        mock_extractor.generate_questions.return_value = "1. What type of analytics?"
        mock_extractor_class.return_value = mock_extractor

        # Mock SQS/SES
        mock_sqs.send_message.return_value = {
            "MessageId": "sqs-msg-123",
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }
        mock_ses.send_email.return_value = {"MessageId": "ses-msg-123"}

        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "email-bucket"},
                        "object": {"key": "emails/initial123.eml"},
                    }
                }
            ]
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["conversation_id"] == "abc123def456"
        assert body["status"] == "active"

        # Verify proper threading setup
        mock_state.fetch_or_create_conversation.assert_called_once()
        call_args = mock_state.fetch_or_create_conversation.call_args[0]
        assert len(call_args[0]) == 16  # Hashed conversation ID
        assert call_args[1] == "initial123@startup.com"  # Original message ID

    @patch("agents.email_intake.lambda_function_v2.s3_client")
    @patch("agents.email_intake.lambda_function_v2.ConversationStateManagerV2")
    def test_lambda_handles_automated_response(self, mock_state_class, mock_s3):
        """Test Lambda ignores automated responses."""
        # Mock S3 with auto-reply
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=lambda: b"""From: noreply@company.com
Subject: Out of Office Re: Your inquiry
Message-ID: <auto123@company.com>
In-Reply-To: <original@solopilot.ai>

I am currently out of office and will respond when I return.

This is an automatic reply.
"""
            )
        }

        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "email-bucket"},
                        "object": {"key": "emails/auto123.eml"},
                    }
                }
            ]
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "Automated response ignored"

        # Should not process further
        mock_state_class.return_value.append_email_with_retry.assert_not_called()
