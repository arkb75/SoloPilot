"""Adapter for client-only simulation with real email delivery.

This adapter sends real emails via SES to the intake address and polls
DynamoDB for your manual responses.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_INTAKE_EMAIL = "intake@abdulkhurram.com"
DEFAULT_SENDER_DOMAIN = "abdulkhurram.com"


@dataclass
class SystemResponse:
    """Represents a response from the email intake system."""

    conversation_id: str
    phase: str
    response_body: str
    subject: str
    requirements: Dict[str, Any]
    pending_reply: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class IntakeAdapter:
    """Bridges client simulator to real email intake via SES.
    
    In client-only mode, this adapter:
    1. Sends real emails via SES to the intake address
    2. Polls DynamoDB to find the created conversation
    3. Waits for your manual response through the dashboard
    4. Detects outbound replies and returns them
    """

    def __init__(
        self,
        aws_profile: str = "root",
        aws_region: str = "us-east-2",
        intake_email: str = DEFAULT_INTAKE_EMAIL,
        dynamodb_table: str = "conversations",
        sender_domain: str = DEFAULT_SENDER_DOMAIN,
    ):
        """Initialize adapter with AWS clients.
        
        Args:
            aws_profile: AWS profile to use
            aws_region: AWS region
            intake_email: Email address that receives client emails
            dynamodb_table: Name of the DynamoDB conversations table
            sender_domain: Domain to use for simulated client emails
        """
        self.aws_profile = aws_profile
        self.aws_region = aws_region
        self.intake_email = intake_email
        self.dynamodb_table = dynamodb_table
        self.sender_domain = sender_domain
        
        # Initialize AWS clients with profile
        session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
        self.ses = session.client("ses")
        self.dynamodb = session.resource("dynamodb")
        self.table = self.dynamodb.Table(dynamodb_table)
        
        # Track simulated client emails for threading
        self._client_emails: Dict[str, str] = {}  # conversation_id -> client_email

    def send_client_email(
        self,
        client_email: str,
        subject: str,
        body: str,
        in_reply_to: Optional[str] = None,
        references: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Send a client email via real SES.
        
        Args:
            client_email: Simulated client's email address
            subject: Email subject
            body: Email body content
            in_reply_to: Message-ID to reply to (for threading)
            references: List of Message-IDs for thread references
        
        Returns:
            Dict with message_id and status
        """
        try:
            # Build the email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = client_email
            msg['To'] = self.intake_email
            
            # Add threading headers if this is a reply
            if in_reply_to:
                msg['In-Reply-To'] = in_reply_to
            if references:
                msg['References'] = ' '.join(references)
            
            # Add text body
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Send via SES
            response = self.ses.send_raw_email(
                Source=client_email,
                Destinations=[self.intake_email],
                RawMessage={'Data': msg.as_string()},
            )
            
            message_id = response['MessageId']
            logger.info(f"Sent email from {client_email} to {self.intake_email}, MessageId: {message_id}")
            
            return {
                "success": True,
                "message_id": message_id,
                "ses_message_id": f"{message_id}@{self.aws_region}.amazonses.com",
            }
            
        except ClientError as e:
            logger.error(f"Failed to send email: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def wait_for_conversation(
        self,
        client_email: str,
        subject: str,
        timeout_seconds: int = 60,
        poll_interval: int = 3,
    ) -> Optional[str]:
        """Poll DynamoDB to find the conversation created from our email.
        
        Args:
            client_email: The client email we sent from
            subject: The email subject
            timeout_seconds: How long to wait for conversation to appear
            poll_interval: Seconds between polls
        
        Returns:
            Conversation ID if found, None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            # Scan for conversations with this client email
            try:
                response = self.table.scan(
                    FilterExpression="contains(participants, :email)",
                    ExpressionAttributeValues={":email": client_email},
                    Limit=10,
                )
                
                for item in response.get("Items", []):
                    # Check if this is our conversation (by subject or recency)
                    conv_subject = item.get("subject", "")
                    if subject.lower() in conv_subject.lower() or conv_subject.lower() in subject.lower():
                        conversation_id = item["conversation_id"]
                        logger.info(f"Found conversation: {conversation_id}")
                        return conversation_id
                    
            except ClientError as e:
                logger.warning(f"Error scanning for conversation: {e}")
            
            time.sleep(poll_interval)
        
        logger.warning(f"Timeout waiting for conversation from {client_email}")
        return None

    def wait_for_response(
        self,
        conversation_id: str,
        last_email_count: int,
        interactive: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Wait for the freelancer to respond to the conversation.
        
        In interactive mode, prompts user to press Enter after responding.
        
        Args:
            conversation_id: Conversation to monitor
            last_email_count: Number of emails before we expect a response
            interactive: If True, prompt user instead of polling
        
        Returns:
            The freelancer's response email dict, or None if not found
        """
        if interactive:
            input("\n📧 Email sent! Respond via your dashboard, then press Enter to continue...")
        
        # Poll for new outbound email
        try:
            conversation = self.get_conversation_state(conversation_id)
            if not conversation:
                return None
            
            email_history = conversation.get("email_history", [])
            
            # Look for new outbound emails
            for email in email_history[last_email_count:]:
                if email.get("direction") == "outbound":
                    logger.info(f"Found freelancer response in conversation {conversation_id}")
                    return email
            
            # Also check pending replies that were approved
            pending_replies = conversation.get("pending_replies", [])
            for reply in pending_replies:
                if reply.get("status") == "approved":
                    return {
                        "body": reply.get("metadata", {}).get("email_body", reply.get("llm_response", "")),
                        "subject": reply.get("metadata", {}).get("subject", f"Re: {conversation.get('subject', '')}"),
                        "direction": "outbound",
                    }
            
            logger.warning("No new outbound email found after prompt")
            return None
            
        except Exception as e:
            logger.error(f"Error checking for response: {e}")
            return None

    def get_conversation_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Fetch current conversation state from DynamoDB.
        
        Args:
            conversation_id: Conversation ID
        
        Returns:
            Conversation state dict or None if not found
        """
        try:
            response = self.table.get_item(Key={"conversation_id": conversation_id})
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Failed to get conversation: {e}")
            return None

    def get_latest_response(self, conversation_id: str) -> Optional[str]:
        """Get the latest freelancer response body from a conversation.
        
        Args:
            conversation_id: Conversation ID
        
        Returns:
            Response body text, or None if not found
        """
        conversation = self.get_conversation_state(conversation_id)
        if not conversation:
            return None
        
        email_history = conversation.get("email_history", [])
        
        # Find the latest outbound email
        for email in reversed(email_history):
            if email.get("direction") == "outbound":
                return email.get("body", "")
        
        return None

    def generate_client_email(self, persona_name: str) -> str:
        """Generate a realistic client email address.
        
        Args:
            persona_name: Client's name (e.g., "John Smith")
        
        Returns:
            Email address like "john.smith@simclient.abdulkhurram.com"
        """
        # Clean name and generate email
        name_parts = persona_name.lower().replace("'", "").split()
        if len(name_parts) >= 2:
            local = f"{name_parts[0]}.{name_parts[-1]}"
        else:
            local = name_parts[0] if name_parts else "client"
        
        # Add random suffix to ensure uniqueness
        suffix = uuid.uuid4().hex[:4]
        
        return f"{local}.{suffix}@simclient.{self.sender_domain}"

    def cleanup_conversation(self, conversation_id: str) -> bool:
        """Delete a simulation conversation (cleanup).
        
        Args:
            conversation_id: Conversation ID to delete
        
        Returns:
            True if deletion succeeded
        """
        try:
            self.table.delete_item(Key={"conversation_id": conversation_id})
            logger.info(f"Deleted simulation conversation: {conversation_id}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False


# Legacy compatibility - SystemResponse for dry-run mode
def create_mock_response(
    conversation_id: str,
    phase: str = "understanding",
    response_body: str = "",
    subject: str = "",
) -> SystemResponse:
    """Create a mock SystemResponse for dry-run mode."""
    return SystemResponse(
        conversation_id=conversation_id,
        phase=phase,
        response_body=response_body,
        subject=subject,
        requirements={},
    )
