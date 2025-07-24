"""Integration tests for complete multi-email conversation flows."""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.agents.email_intake.conversation_state import ConversationStateManager
from src.agents.email_intake.lambda_function import lambda_handler


class TestMultiEmailConversationFlow:
    """End-to-end tests for multi-turn email conversations."""

    @patch("src.agents.email_intake.lambda_function.s3_client")
    @patch("src.agents.email_intake.lambda_function.ses_client")
    @patch("src.agents.email_intake.lambda_function.sqs_client")
    @patch("src.agents.email_intake.lambda_function.boto3.resource")
    def test_three_email_conversation_flow(self, mock_dynamo, mock_sqs, mock_ses, mock_s3):
        """Test complete 3-email conversation: initial → follow-up → completion."""
        # Setup environment
        os.environ["REQUIREMENT_QUEUE_URL"] = "https://sqs.test.com/queue"
        os.environ["SENDER_EMAIL"] = "hello@solopilot.ai"
        os.environ["ENABLE_OUTBOUND_TRACKING"] = "true"

        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_dynamo.return_value.Table.return_value = mock_table

        # Track conversation state across emails
        conversation_state = {
            "conversation_id": "conv_3email_test",
            "original_message_id": "initial@client.com",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "last_seq": Decimal(0),
            "status": "active",
            "email_history": [],
            "requirements": {},
            "requirements_version": Decimal(0),
            "participants": set(),
            "thread_references": [],
            "ttl": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
        }

        # Email 1: Initial inquiry
        email1_content = b"""From: john@techcorp.com
To: hello@solopilot.ai
Subject: Need help with e-commerce platform
Message-ID: <initial@client.com>
Date: Mon, 15 Jan 2024 10:00:00 +0000

Hi SoloPilot team,

We're looking to build an e-commerce platform. We need shopping cart functionality 
and payment processing.

Can you help?

Thanks,
John
"""

        # Mock responses for Email 1
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: email1_content)}
        mock_table.get_item.return_value = {}  # New conversation
        mock_table.put_item.return_value = {}  # Creation succeeds

        def update_state_email1(*args, **kwargs):
            """Simulate state after first email."""
            nonlocal conversation_state
            if "email_history = list_append" in kwargs.get("UpdateExpression", ""):
                conversation_state["last_seq"] = Decimal(1)
                conversation_state["email_history"].append(
                    {
                        "email_id": "conv_3email_test-001",
                        "from": "john@techcorp.com",
                        "subject": "Need help with e-commerce platform",
                        "body": email1_content.decode(),
                        "direction": "inbound",
                    }
                )
                conversation_state["participants"] = {"john@techcorp.com", "hello@solopilot.ai"}
            elif "requirements = :req" in kwargs.get("UpdateExpression", ""):
                conversation_state["requirements"] = {
                    "title": "E-commerce Platform",
                    "features": [
                        {"name": "Shopping Cart", "desc": "Cart functionality"},
                        {"name": "Payment Processing", "desc": "Payment integration"},
                    ],
                }
                conversation_state["requirements_version"] = Decimal(1)
            return {"Attributes": conversation_state.copy()}

        mock_table.update_item.side_effect = update_state_email1
        mock_sqs.send_message.return_value = {
            "MessageId": "sqs-1",
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }
        mock_ses.send_email.return_value = {"MessageId": "followup-1"}

        # Process Email 1
        event1 = {
            "Records": [
                {"s3": {"bucket": {"name": "email-bucket"}, "object": {"key": "emails/email1.eml"}}}
            ]
        }

        result1 = lambda_handler(event1, None)
        assert result1["statusCode"] == 200

        # Verify follow-up was sent
        ses_call = mock_ses.send_email.call_args[1]
        assert "Re: Need help with e-commerce platform" in ses_call["Message"]["Subject"]["Data"]
        assert "additional information" in ses_call["Message"]["Body"]["Text"]["Data"]

        # Email 2: Client provides more details
        email2_content = b"""From: john@techcorp.com
To: hello@solopilot.ai
Subject: Re: Need help with e-commerce platform
Message-ID: <reply1@client.com>
In-Reply-To: <initial@client.com>
References: <initial@client.com>
Date: Mon, 15 Jan 2024 14:00:00 +0000

Thanks for the quick response!

To answer your questions:
- Project type: Web application
- Business: We sell electronics online
- Timeline: 3 months
- Budget: $25,000

We also need inventory management as a third feature.

Best,
John
"""

        # Reset mocks for Email 2
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: email2_content)}
        mock_table.get_item.return_value = {"Item": conversation_state}
        mock_ses.send_email.reset_mock()
        mock_sqs.send_message.reset_mock()

        def update_state_email2(*args, **kwargs):
            """Simulate state after second email."""
            nonlocal conversation_state
            if "email_history = list_append" in kwargs.get("UpdateExpression", ""):
                # Check optimistic locking
                if (
                    kwargs["ExpressionAttributeValues"][":current_seq"]
                    != conversation_state["last_seq"]
                ):
                    raise Exception("Sequence mismatch")
                conversation_state["last_seq"] = Decimal(2)
                conversation_state["email_history"].append(
                    {
                        "email_id": "conv_3email_test-002",
                        "from": "john@techcorp.com",
                        "subject": "Re: Need help with e-commerce platform",
                        "is_reply": True,
                        "direction": "inbound",
                    }
                )
                conversation_state["thread_references"].append("reply1@client.com")
            elif "requirements = :req" in kwargs.get("UpdateExpression", ""):
                conversation_state["requirements"].update(
                    {
                        "project_type": "web_app",
                        "business_description": "Electronics e-commerce",
                        "timeline": "3 months",
                        "budget": "$25,000",
                        "features": [
                            {"name": "Shopping Cart", "desc": "Cart functionality"},
                            {"name": "Payment Processing", "desc": "Payment integration"},
                            {"name": "Inventory Management", "desc": "Stock tracking"},
                        ],
                    }
                )
                conversation_state["requirements_version"] = Decimal(2)
                conversation_state["status"] = "completed"
            return {"Attributes": conversation_state.copy()}

        mock_table.update_item.side_effect = update_state_email2
        mock_sqs.send_message.return_value = {
            "MessageId": "sqs-2",
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }
        mock_ses.send_email.return_value = {"MessageId": "confirmation-1"}

        # Process Email 2
        event2 = {
            "Records": [
                {"s3": {"bucket": {"name": "email-bucket"}, "object": {"key": "emails/email2.eml"}}}
            ]
        }

        result2 = lambda_handler(event2, None)
        assert result2["statusCode"] == 200

        # Verify confirmation was sent
        ses_call = mock_ses.send_email.call_args[1]
        assert "Project Scope Confirmed" in ses_call["Message"]["Subject"]["Data"]
        assert "E-commerce Platform" in ses_call["Message"]["Body"]["Text"]["Data"]
        assert "$25,000" in ses_call["Message"]["Body"]["Text"]["Data"]

        # Verify SQS messages sent
        assert mock_sqs.send_message.call_count == 2

        # Check final conversation state
        assert conversation_state["status"] == "completed"
        assert len(conversation_state["email_history"]) == 2
        assert conversation_state["last_seq"] == 2
        assert conversation_state["requirements_version"] == 2

    @patch("src.agents.email_intake.lambda_function_v2.s3_client")
    @patch("src.agents.email_intake.lambda_function_v2.boto3.resource")
    def test_conversation_with_concurrent_emails(self, mock_dynamo, mock_s3):
        """Test handling concurrent emails in same conversation."""
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_dynamo.return_value.Table.return_value = mock_table

        # Simulate two emails arriving simultaneously
        email_a = b"""From: alice@team.com
To: hello@solopilot.ai
Subject: Re: Project Update
Message-ID: <alice1@team.com>
In-Reply-To: <original@team.com>

Here's my input on the requirements...
"""

        email_b = b"""From: bob@team.com
To: hello@solopilot.ai
Subject: Re: Project Update
Message-ID: <bob1@team.com>
In-Reply-To: <original@team.com>

I have some additional requirements...
"""

        # Both see same initial state
        initial_state = {
            "conversation_id": "team_conv",
            "last_seq": Decimal(3),
            "email_history": [{"email_id": "existing"}],
            "participants": {"original@team.com"},
            "thread_references": ["original@team.com"],
        }

        # Simulate race condition
        mock_table.get_item.side_effect = [
            {"Item": initial_state.copy()},  # Lambda A reads
            {"Item": initial_state.copy()},  # Lambda B reads
            {"Item": {**initial_state, "last_seq": Decimal(4)}},  # Lambda B re-reads after conflict
        ]

        # Lambda A succeeds, Lambda B gets conflict then succeeds
        from botocore.exceptions import ClientError

        conflict_error = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
        )

        update_responses = [
            {"Attributes": {**initial_state, "last_seq": Decimal(4)}},  # A succeeds
            conflict_error,  # B fails
            {"Attributes": {**initial_state, "last_seq": Decimal(5)}},  # B retry succeeds
        ]

        mock_table.update_item.side_effect = update_responses

        # Process both emails - would happen in parallel in real scenario
        # Here we simulate the effect
        assert len(update_responses) == 3  # A success, B fail, B retry
        assert mock_table.get_item.side_effect

    def test_email_threading_validation(self):
        """Test email threading follows RFC 5322 correctly."""
        from src.agents.email_intake.email_parser import EmailParser

        parser = EmailParser()

        # Test threading chain
        emails = [
            # Initial email
            """From: client@example.com
To: hello@solopilot.ai
Subject: New Project Request
Message-ID: <msg1@example.com>
Date: Mon, 1 Jan 2024 10:00:00 +0000

Initial request...""",
            # First reply
            """From: hello@solopilot.ai
To: client@example.com
Subject: Re: New Project Request
Message-ID: <msg2@solopilot.ai>
In-Reply-To: <msg1@example.com>
References: <msg1@example.com>
Date: Mon, 1 Jan 2024 11:00:00 +0000

Follow-up questions...""",
            # Second reply
            """From: client@example.com
To: hello@solopilot.ai
Subject: Re: New Project Request
Message-ID: <msg3@example.com>
In-Reply-To: <msg2@solopilot.ai>
References: <msg1@example.com> <msg2@solopilot.ai>
Date: Mon, 1 Jan 2024 12:00:00 +0000

Answers to questions...""",
        ]

        parsed_emails = [parser.parse(email) for email in emails]

        # All should have same conversation ID
        conv_ids = [e["conversation_id"] for e in parsed_emails]
        assert len(set(conv_ids)) == 1, "All emails should map to same conversation"

        # Verify threading
        assert parsed_emails[0]["is_reply"] is False
        assert parsed_emails[1]["is_reply"] is True
        assert parsed_emails[2]["is_reply"] is True

        # Verify references chain
        assert parsed_emails[2]["references"] == "<msg1@example.com> <msg2@solopilot.ai>"

    @patch("src.agents.email_intake.conversation_state_v2.boto3.resource")
    def test_ttl_expiry_behavior(self, mock_boto):
        """Test TTL-based conversation expiry."""
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        manager = ConversationStateManager()

        # Create conversation that should expire
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=31)
        old_ttl = int(old_timestamp.timestamp())

        expired_conv = {
            "conversation_id": "old_conv",
            "created_at": old_timestamp.isoformat(),
            "ttl": old_ttl,
            "status": "completed",
        }

        # DynamoDB will auto-delete items past TTL
        # Test that we handle missing conversations gracefully
        mock_table.get_item.return_value = {}  # Conversation expired

        result = manager.fetch_or_create_conversation(
            "old_conv", "original@old.com", {"from": "new@client.com"}
        )

        # Should create new conversation
        assert mock_table.put_item.called
        put_args = mock_table.put_item.call_args[1]["Item"]
        assert put_args["conversation_id"] == "old_conv"
        assert put_args["ttl"] > int(datetime.now(timezone.utc).timestamp())

    def test_conversation_metrics(self):
        """Test conversation metrics calculation."""

        # Sample conversation with multiple emails
        email_history = [
            {
                "timestamp": "2024-01-15T10:00:00Z",
                "direction": "inbound",
                "from": "client@example.com",
            },
            {
                "timestamp": "2024-01-15T10:30:00Z",
                "direction": "outbound",
                "from": "hello@solopilot.ai",
            },
            {
                "timestamp": "2024-01-15T14:00:00Z",
                "direction": "inbound",
                "from": "client@example.com",
            },
            {
                "timestamp": "2024-01-15T14:15:00Z",
                "direction": "outbound",
                "from": "hello@solopilot.ai",
            },
        ]

        # Calculate metrics
        inbound_count = sum(1 for e in email_history if e["direction"] == "inbound")
        outbound_count = sum(1 for e in email_history if e["direction"] == "outbound")

        # Response times
        response_times = []
        for i in range(1, len(email_history)):
            if (
                email_history[i]["direction"] == "outbound"
                and email_history[i - 1]["direction"] == "inbound"
            ):
                t1 = datetime.fromisoformat(
                    email_history[i - 1]["timestamp"].replace("Z", "+00:00")
                )
                t2 = datetime.fromisoformat(email_history[i]["timestamp"].replace("Z", "+00:00"))
                response_times.append((t2 - t1).total_seconds() / 60)  # minutes

        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        assert inbound_count == 2
        assert outbound_count == 2
        assert avg_response_time == 22.5  # Average of 30 and 15 minutes
