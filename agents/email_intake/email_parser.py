"""Email parser for extracting thread information."""

import email
import email.message
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List

from utils import EmailThreadingUtils

logger = logging.getLogger(__name__)


class EmailParser:
    """Parses raw email content to extract relevant information."""

    def __init__(self, state_manager=None):
        """Initialize parser with optional state manager.

        Args:
            state_manager: ConversationStateManager instance for lookups
        """
        self.state_manager = state_manager

    def parse(self, raw_email: str) -> Dict[str, Any]:
        """Parse raw email content.

        Args:
            raw_email: Raw email string (MIME format)

        Returns:
            Parsed email data with thread ID, sender, subject, body
        """
        try:
            # Parse email message
            msg = email.message_from_string(raw_email)
            self.current_msg = msg  # Store for thread ID extraction

            # Extract basic fields
            from_addr = self._extract_email_address(msg.get("From", ""))
            subject = msg.get("Subject", "No Subject")
            message_id = msg.get("Message-ID", "")
            in_reply_to = msg.get("In-Reply-To", "")
            references = msg.get("References", "")

            # Extract recipients
            to_addrs = self._extract_recipients(msg.get("To", ""))
            cc_addrs = self._extract_recipients(msg.get("Cc", ""))

            # Extract thread information
            thread_info = self._extract_thread_id(
                message_id, in_reply_to, references, subject, from_addr
            )

            # Extract timestamp
            date_str = msg.get("Date", "")
            timestamp = self._parse_date(date_str)

            # Extract body
            body = self._extract_body(msg)

            # Clean up subject (remove Re:, Fwd:, etc)
            clean_subject = self._clean_subject(subject)

            parsed = {
                # Legacy field for compatibility
                "thread_id": thread_info["conversation_id"],
                # Enhanced fields
                "conversation_id": thread_info["conversation_id"],
                "original_message_id": thread_info["original_message_id"],
                "message_id": message_id,
                "in_reply_to": in_reply_to,
                "references": references,
                "from": from_addr,
                "to": to_addrs,
                "cc": cc_addrs,
                "subject": clean_subject,
                "original_subject": subject,
                "body": body,
                "timestamp": timestamp,
                "is_reply": bool(in_reply_to or references),
                "attachments": self._extract_attachments(msg),
                # Custom headers for better tracking
                "x_conversation_id": msg.get("X-Conversation-ID", ""),
                "x_solopilot_message_id": msg.get("X-SoloPilot-Message-ID", ""),
            }

            logger.info(f"Parsed email from {from_addr} with thread {thread_info}")
            return parsed

        except Exception as e:
            logger.error(f"Error parsing email: {str(e)}")
            raise

    def _extract_email_address(self, from_header: str) -> str:
        """Extract email address from From header."""
        # Match email pattern
        match = re.search(r"<([^>]+)>", from_header)
        if match:
            return match.group(1).lower()

        # If no angle brackets, assume entire string is email
        email_match = re.search(r"[\w\.-]+@[\w\.-]+", from_header)
        if email_match:
            return email_match.group(0).lower()

        return from_header.lower()

    def _extract_thread_id(
        self, message_id: str, in_reply_to: str, references: str, subject: str, from_addr: str
    ) -> Dict[str, Any]:
        """Extract thread information using RFC 5322 compliant logic.

        Returns:
            Dict with conversation_id, original_message_id, and references list
        """
        # Parse references into list
        ref_list = EmailThreadingUtils.parse_references(references)

        # Determine conversation ID
        conv_id, original_id = EmailThreadingUtils.determine_conversation_id(
            message_id,
            in_reply_to,
            ref_list,
            subject,
            from_addr,
            (
                self._parse_date(self.current_msg.get("Date", ""))
                if hasattr(self, "current_msg")
                else None
            ),
            self.state_manager,  # Pass state manager for lookups
        )

        return {
            "conversation_id": conv_id,
            "original_message_id": original_id,
            "references": ref_list,
        }

    def _extract_recipients(self, header_value: str) -> List[str]:
        """Extract email addresses from To/Cc headers."""
        if not header_value:
            return []

        addresses = []
        # Simple extraction - can be enhanced with email.utils.getaddresses
        for part in header_value.split(","):
            addr = self._extract_email_address(part.strip())
            if addr:
                addresses.append(addr)

        return addresses

    def _extract_attachments(self, msg: email.message.Message) -> List[Dict[str, Any]]:
        """Extract attachment information from email."""
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = part.get("Content-Disposition", "")

                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        attachments.append(
                            {
                                "filename": filename,
                                "content_type": part.get_content_type(),
                                "size": (
                                    len(part.get_payload(decode=True))
                                    if part.get_payload(decode=True)
                                    else 0
                                ),
                            }
                        )

        return attachments

    def _parse_date(self, date_str: str) -> str:
        """Parse email date to ISO format."""
        try:
            if date_str:
                dt = parsedate_to_datetime(date_str)
                return dt.isoformat()
        except Exception as e:
            logger.warning(f"Could not parse date '{date_str}': {str(e)}")

        # Default to current time
        return datetime.now(timezone.utc).isoformat()

    def _extract_body(self, msg: email.message.Message) -> str:
        """Extract plain text body from email."""
        body_parts = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()

                # Get plain text parts
                if content_type == "text/plain":
                    try:
                        text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        body_parts.append(text)
                    except Exception as e:
                        logger.warning(f"Error decoding email part: {str(e)}")
        else:
            # Single part message
            try:
                text = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                body_parts.append(text)
            except Exception as e:
                logger.warning(f"Error decoding email body: {str(e)}")

        # Join all text parts
        full_body = "\n".join(body_parts)

        # Clean up body (remove excessive whitespace, signatures)
        return self._clean_body(full_body)

    def _clean_body(self, body: str) -> str:
        """Clean email body text."""
        # Remove email signatures (simple heuristic)
        signature_markers = ["--", "___", "Sent from", "Get Outlook"]
        lines = body.split("\n")

        cleaned_lines = []
        for line in lines:
            # Stop at signature markers
            if any(line.strip().startswith(marker) for marker in signature_markers):
                break
            cleaned_lines.append(line)

        # Join and clean whitespace
        cleaned = "\n".join(cleaned_lines)

        # Remove excessive blank lines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        return cleaned.strip()

    def _clean_subject(self, subject: str) -> str:
        """Remove Re:, Fwd:, etc from subject."""
        # Remove common prefixes
        prefixes = r"^(Re:|RE:|Fwd:|FWD:|Fw:|FW:)\s*"
        cleaned = re.sub(prefixes, "", subject, flags=re.IGNORECASE)

        # Remove multiple occurrences
        while re.match(prefixes, cleaned, flags=re.IGNORECASE):
            cleaned = re.sub(prefixes, "", cleaned, flags=re.IGNORECASE)

        return cleaned.strip()
