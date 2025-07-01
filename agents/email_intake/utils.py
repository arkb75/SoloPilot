"""Email threading utilities for RFC 5322 compliant conversation tracking."""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class EmailThreadingUtils:
    """Utilities for email thread management following RFC 5322."""

    @staticmethod
    def extract_message_id(message_id: str) -> str:
        """Extract clean Message-ID from header value.

        Args:
            message_id: Raw Message-ID header value

        Returns:
            Cleaned Message-ID without angle brackets
        """
        if not message_id:
            return ""

        # Remove angle brackets and whitespace
        cleaned = message_id.strip()
        if cleaned.startswith("<") and cleaned.endswith(">"):
            cleaned = cleaned[1:-1]

        return cleaned

    @staticmethod
    def parse_references(references: str) -> List[str]:
        """Parse References header into list of Message-IDs.

        Args:
            references: Raw References header value

        Returns:
            List of cleaned Message-IDs
        """
        if not references:
            return []

        # Split by whitespace and extract Message-IDs
        ids = []
        for ref in references.split():
            cleaned = EmailThreadingUtils.extract_message_id(ref)
            if cleaned:
                ids.append(cleaned)

        return ids

    @staticmethod
    def hash_conversation_id(identifier: str) -> str:
        """Create consistent 16-character hash for conversation ID.

        Args:
            identifier: String to hash (Message-ID, subject, etc.)

        Returns:
            16-character hex hash
        """
        return hashlib.md5(identifier.encode()).hexdigest()[:16]

    @staticmethod
    def determine_conversation_id(
        message_id: str,
        in_reply_to: str,
        references: List[str],
        subject: str,
        from_addr: str,
        date: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Determine conversation ID from email headers.

        Uses the following precedence:
        1. If replying (In-Reply-To exists), use the original message as conversation
        2. If references exist, use the first reference
        3. For new conversations, use current Message-ID
        4. Fallback: hash of from+subject+date

        Args:
            message_id: Current email's Message-ID
            in_reply_to: In-Reply-To header value
            references: List of Message-IDs from References header
            subject: Email subject (cleaned)
            from_addr: Sender email address
            date: Email date for fallback hashing

        Returns:
            Tuple of (conversation_id, original_message_id)
        """
        # Extract clean IDs
        clean_message_id = EmailThreadingUtils.extract_message_id(message_id)
        clean_in_reply_to = EmailThreadingUtils.extract_message_id(in_reply_to)

        # Case 1: This is a reply - use the parent message
        if clean_in_reply_to:
            original_id = clean_in_reply_to
            conv_id = EmailThreadingUtils.hash_conversation_id(original_id)
            logger.info(
                f"Reply detected: conversation={conv_id}, original={original_id}"
            )
            return conv_id, original_id

        # Case 2: Has references - use the first one (root of thread)
        if references and references[0]:
            original_id = references[0]
            conv_id = EmailThreadingUtils.hash_conversation_id(original_id)
            logger.info(
                f"Thread with references: conversation={conv_id}, original={original_id}"
            )
            return conv_id, original_id

        # Case 3: New conversation - use current Message-ID
        if clean_message_id:
            conv_id = EmailThreadingUtils.hash_conversation_id(clean_message_id)
            logger.info(
                f"New conversation: conversation={conv_id}, original={clean_message_id}"
            )
            return conv_id, clean_message_id

        # Case 4: Fallback - hash from+subject+date
        fallback_data = (
            f"{from_addr}:{subject}:{date or datetime.now(timezone.utc).isoformat()}"
        )
        conv_id = EmailThreadingUtils.hash_conversation_id(fallback_data)
        logger.warning(f"Fallback conversation ID: {conv_id} from {fallback_data}")
        return conv_id, ""

    @staticmethod
    def extract_participants(email_data: Dict[str, Any]) -> Set[str]:
        """Extract all participant email addresses from email data.

        Args:
            email_data: Email data with from, to, cc fields

        Returns:
            Set of lowercase email addresses
        """
        participants = set()

        # Add sender
        if email_data.get("from"):
            participants.add(email_data["from"].lower())

        # Add recipients
        for field in ["to", "cc", "bcc"]:
            recipients = email_data.get(field, [])
            if isinstance(recipients, str):
                recipients = [recipients]
            for addr in recipients:
                if addr:
                    participants.add(addr.lower())

        return participants

    @staticmethod
    def merge_thread_references(
        existing_refs: List[str], new_message_id: str, new_references: List[str]
    ) -> List[str]:
        """Merge thread references maintaining chronological order.

        Args:
            existing_refs: Current list of references
            new_message_id: New email's Message-ID to add
            new_references: New email's References header

        Returns:
            Updated list of unique references in order
        """
        # Use ordered dict to maintain order while removing duplicates
        refs_dict = {}

        # Add existing references
        for ref in existing_refs:
            refs_dict[ref] = None

        # Add new references
        for ref in new_references:
            refs_dict[ref] = None

        # Add new message ID at the end
        clean_id = EmailThreadingUtils.extract_message_id(new_message_id)
        if clean_id:
            refs_dict[clean_id] = None

        return list(refs_dict.keys())

    @staticmethod
    def generate_email_id(conversation_id: str, message_id: str, timestamp: str) -> str:
        """Generate unique email ID within conversation.

        Args:
            conversation_id: Conversation identifier
            message_id: Email Message-ID
            timestamp: Email timestamp

        Returns:
            Unique email identifier
        """
        # Create hash from message ID and timestamp
        data = f"{message_id}:{timestamp}"
        hash_suffix = hashlib.md5(data.encode()).hexdigest()[:8]
        return f"{conversation_id}-{hash_suffix}"

    @staticmethod
    def calculate_ttl(days: int = 30) -> int:
        """Calculate TTL timestamp for DynamoDB.

        Args:
            days: Number of days until expiry

        Returns:
            Unix timestamp for TTL
        """
        expiry_time = datetime.now(timezone.utc).timestamp() + (days * 86400)
        return int(expiry_time)

    @staticmethod
    def is_automated_response(email_body: str, subject: str) -> bool:
        """Detect if email is an automated response.

        Args:
            email_body: Email body content
            subject: Email subject

        Returns:
            True if likely automated
        """
        auto_patterns = [
            r"auto.?reply",
            r"out of (the )?office",
            r"vacation",
            r"away from (my )?desk",
            r"automatic response",
            r"delivery status notification",
            r"mail delivery subsystem",
            r"undeliverable",
            r"bounce",
        ]

        combined_text = f"{subject} {email_body}".lower()

        for pattern in auto_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                logger.info(f"Detected automated response: pattern={pattern}")
                return True

        return False

    @staticmethod
    def extract_quoted_text(email_body: str) -> Tuple[str, str]:
        """Separate new content from quoted text in email.

        Args:
            email_body: Full email body

        Returns:
            Tuple of (new_content, quoted_content)
        """
        # Common quote markers
        quote_patterns = [
            r"On .+ wrote:",  # Gmail/Outlook style
            r"From:.*Sent:.*To:.*Subject:",  # Outlook forward
            r"-{3,} Original Message -{3,}",  # Various clients
            r"_{3,}",  # Underscores
            r">{1,}",  # Traditional email quotes
        ]

        lines = email_body.split("\n")
        quote_start = len(lines)

        for i, line in enumerate(lines):
            for pattern in quote_patterns:
                if re.search(pattern, line):
                    quote_start = i
                    break
            if quote_start != len(lines):
                break

        new_content = "\n".join(lines[:quote_start]).strip()
        quoted_content = (
            "\n".join(lines[quote_start:]).strip() if quote_start < len(lines) else ""
        )

        return new_content, quoted_content
