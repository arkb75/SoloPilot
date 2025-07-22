#!/usr/bin/env python3
"""Test conversation ID stability across email threads."""

import os

# Import the modules we're testing
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_parser import EmailParser

from src.utils import EmailThreadingUtils


class MockStateManager:
    """Mock state manager for testing."""

    def __init__(self):
        self.message_map = {}  # message_id -> conversation_id
        self.conversations = {}  # conversation_id -> conversation data

    def get_conversation_by_message_id(self, message_id):
        """Mock lookup."""
        return self.message_map.get(message_id)

    def store_message_id_mapping(self, message_id, conversation_id):
        """Mock store."""
        self.message_map[message_id] = conversation_id

    def lookup_conversation_from_references(self, in_reply_to, references):
        """Mock lookup from references."""
        if in_reply_to and in_reply_to in self.message_map:
            return self.message_map[in_reply_to]

        for ref in references:
            if ref in self.message_map:
                return self.message_map[ref]

        return None


class TestConversationThreading(unittest.TestCase):
    """Test cases for conversation threading stability."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_state_manager = MockStateManager()

    def test_new_conversation_creates_stable_id(self):
        """Test that a new conversation gets a stable ID."""
        # First email in thread
        message_id = "msg-001@example.com"

        conv_id, original_id = EmailThreadingUtils.determine_conversation_id(
            message_id=message_id,
            in_reply_to="",
            references=[],
            subject="Test Subject",
            from_addr="sender@example.com",
            state_manager=self.mock_state_manager,
        )

        # Store the mapping
        self.mock_state_manager.store_message_id_mapping(message_id, conv_id)

        # Verify conversation ID is based on message ID
        expected_conv_id = EmailThreadingUtils.hash_conversation_id(message_id)
        self.assertEqual(conv_id, expected_conv_id)
        self.assertEqual(original_id, message_id)

    def test_reply_maintains_same_conversation_id(self):
        """Test that replies maintain the same conversation ID."""
        # First email
        msg1_id = "msg-001@example.com"
        conv_id1, _ = EmailThreadingUtils.determine_conversation_id(
            message_id=msg1_id,
            in_reply_to="",
            references=[],
            subject="Test Subject",
            from_addr="sender@example.com",
            state_manager=self.mock_state_manager,
        )
        self.mock_state_manager.store_message_id_mapping(msg1_id, conv_id1)

        # Reply to first email
        msg2_id = "msg-002@example.com"
        conv_id2, _ = EmailThreadingUtils.determine_conversation_id(
            message_id=msg2_id,
            in_reply_to=msg1_id,
            references=[msg1_id],
            subject="Re: Test Subject",
            from_addr="recipient@example.com",
            state_manager=self.mock_state_manager,
        )
        self.mock_state_manager.store_message_id_mapping(msg2_id, conv_id2)

        # Verify same conversation ID
        self.assertEqual(conv_id1, conv_id2)

    def test_deep_thread_maintains_conversation_id(self):
        """Test that deep threads maintain the same conversation ID."""
        # Create a chain of 5 emails
        conversation_id = None
        previous_msg_id = None

        for i in range(5):
            msg_id = f"msg-{i:03d}@example.com"
            references = []

            # Build references list (all previous messages)
            if i > 0:
                references = [f"msg-{j:03d}@example.com" for j in range(i)]

            conv_id, _ = EmailThreadingUtils.determine_conversation_id(
                message_id=msg_id,
                in_reply_to=previous_msg_id or "",
                references=references,
                subject=f"{'Re: ' * i}Test Subject",
                from_addr=f"user{i}@example.com",
                state_manager=self.mock_state_manager,
            )

            # Store mapping
            self.mock_state_manager.store_message_id_mapping(msg_id, conv_id)

            # First iteration sets the conversation ID
            if conversation_id is None:
                conversation_id = conv_id
            else:
                # All subsequent messages should have same ID
                self.assertEqual(
                    conv_id, conversation_id, f"Message {i} has different conversation ID"
                )

            previous_msg_id = msg_id

    def test_reply_to_unknown_message_creates_new_thread(self):
        """Test that replying to an unknown message creates a new thread."""
        # Reply to a message we haven't seen
        unknown_msg_id = "external-msg@other.com"
        msg_id = "msg-reply@example.com"

        conv_id, original_id = EmailThreadingUtils.determine_conversation_id(
            message_id=msg_id,
            in_reply_to=unknown_msg_id,
            references=[unknown_msg_id],
            subject="Re: External Thread",
            from_addr="sender@example.com",
            state_manager=self.mock_state_manager,
        )

        # Should create new conversation based on the parent message ID
        expected_conv_id = EmailThreadingUtils.hash_conversation_id(unknown_msg_id)
        self.assertEqual(conv_id, expected_conv_id)
        self.assertEqual(original_id, unknown_msg_id)

    def test_references_fallback_works(self):
        """Test that References header is used when In-Reply-To is missing."""
        # First email
        msg1_id = "msg-001@example.com"
        conv_id1, _ = EmailThreadingUtils.determine_conversation_id(
            message_id=msg1_id,
            in_reply_to="",
            references=[],
            subject="Test Subject",
            from_addr="sender@example.com",
            state_manager=self.mock_state_manager,
        )
        self.mock_state_manager.store_message_id_mapping(msg1_id, conv_id1)

        # Reply with only References header (no In-Reply-To)
        msg2_id = "msg-002@example.com"
        conv_id2, _ = EmailThreadingUtils.determine_conversation_id(
            message_id=msg2_id,
            in_reply_to="",  # Missing In-Reply-To
            references=[msg1_id],  # But has References
            subject="Re: Test Subject",
            from_addr="recipient@example.com",
            state_manager=self.mock_state_manager,
        )

        # Should still find the same conversation
        self.assertEqual(conv_id1, conv_id2)


class TestEmailParserIntegration(unittest.TestCase):
    """Test email parser with conversation state manager."""

    def test_parser_with_state_manager(self):
        """Test that parser correctly uses state manager for lookups."""
        mock_state_manager = MockStateManager()
        parser = EmailParser(state_manager=mock_state_manager)

        # First email
        email1 = """From: sender@example.com
To: recipient@example.com
Subject: Test Thread
Message-ID: <msg-001@example.com>
Date: Mon, 1 Jan 2024 10:00:00 +0000

This is the first message.
"""
        parsed1 = parser.parse(email1)
        conv_id1 = parsed1["conversation_id"]
        mock_state_manager.store_message_id_mapping("msg-001@example.com", conv_id1)

        # Reply
        email2 = """From: recipient@example.com
To: sender@example.com
Subject: Re: Test Thread
Message-ID: <msg-002@example.com>
In-Reply-To: <msg-001@example.com>
References: <msg-001@example.com>
Date: Mon, 1 Jan 2024 11:00:00 +0000

This is a reply.
"""
        parsed2 = parser.parse(email2)
        conv_id2 = parsed2["conversation_id"]

        # Should have same conversation ID
        self.assertEqual(conv_id1, conv_id2)


if __name__ == "__main__":
    unittest.main()
