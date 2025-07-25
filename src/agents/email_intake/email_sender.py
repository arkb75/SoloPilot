"""Email sender module for sending replies via AWS SES."""

import email.utils
import logging
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# AWS SES client
ses_client = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-2"))

# Email configuration
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "intake@solopilot.abdulkhurram.com")
SENDER_NAME = os.environ.get("SENDER_NAME", "SoloPilot")


def send_reply_email(
    to_email: str,
    subject: str,
    body: str,
    conversation_id: str,
    in_reply_to: Optional[str] = None,
    references: Optional[List[str]] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Send a reply email with proper threading headers.

    Args:
        to_email: Recipient email address
        subject: Email subject (should include Re: prefix)
        body: Email body content
        conversation_id: Conversation ID for tracking
        in_reply_to: Message-ID of the email being replied to
        references: List of Message-IDs in the thread
        attachments: Optional list of attachments

    Returns:
        Tuple of (success, ses_message_id, error_message)
    """
    # Guard clause: Prevent sending proposal emails without PDFs
    # Check if the body indicates this should be a proposal with attachment
    if (
        "Please find the proposal attached" in body or "Please find attached" in body
    ) and not attachments:
        error_msg = f"Invariant violated: Attempted to send proposal email without PDF attachment for conversation {conversation_id}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    try:
        # Create MIME message
        msg = MIMEMultipart()
        msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Don't set Message-ID - let SES handle it
        # SES will generate its own Message-ID regardless of what we set

        # Set threading headers
        if in_reply_to:
            msg["In-Reply-To"] = (
                f"<{in_reply_to}>" if not in_reply_to.startswith("<") else in_reply_to
            )

        if references:
            # Build proper references chain
            ref_list = []
            for ref in references:
                if ref and not ref.startswith("<"):
                    ref_list.append(f"<{ref}>")
                elif ref:
                    ref_list.append(ref)
            msg["References"] = " ".join(ref_list)

        msg["Reply-To"] = SENDER_EMAIL

        # Add conversation tracking headers
        msg["X-Conversation-ID"] = conversation_id
        # Add a unique tracking ID that we control
        msg["X-SoloPilot-Message-ID"] = email.utils.make_msgid(domain="solopilot.abdulkhurram.com")

        # Add body - ensure conversation ID is visible
        # If conversation ID not already in body, append it
        if f"Conversation ID: {conversation_id}" not in body:
            body = f"{body}\n\n--\nConversation ID: {conversation_id}"
        msg.attach(MIMEText(body, "plain"))

        # Add attachments if any
        if attachments:
            for attachment in attachments:
                part = MIMEApplication(
                    attachment.get("content", b""), Name=attachment.get("filename", "attachment")
                )
                part["Content-Disposition"] = (
                    f'attachment; filename="{attachment.get("filename", "attachment")}"'
                )
                msg.attach(part)

        # Send raw email
        response = ses_client.send_raw_email(
            Source=SENDER_EMAIL,
            Destinations=[to_email],
            RawMessage={"Data": msg.as_string()},
            Tags=[
                {"Name": "conversation_id", "Value": conversation_id},
                {"Name": "email_type", "Value": "reply"},
            ],
        )

        ses_message_id = response.get("MessageId")
        logger.info(f"Sent reply email successfully. SES MessageId: {ses_message_id}")

        return True, ses_message_id, None

    except ClientError as e:
        error_msg = f"AWS SES error: {str(e)}"
        logger.error(error_msg)
        return False, None, error_msg
    except Exception as e:
        error_msg = f"Error sending reply email: {str(e)}"
        logger.error(error_msg)
        return False, None, error_msg


def send_proposal_email(
    to_email: str,
    subject: str,
    body: str,
    conversation_id: str,
    pdf_content: bytes,
    pdf_filename: str,
    in_reply_to: Optional[str] = None,
    references: Optional[List[str]] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Send a proposal email with PDF attachment.

    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body content
        conversation_id: Conversation ID for tracking
        pdf_content: PDF file content as bytes
        pdf_filename: Name for the PDF attachment
        in_reply_to: Message-ID of the email being replied to
        references: List of Message-IDs in the thread

    Returns:
        Tuple of (success, ses_message_id, error_message)
    """
    # Create attachment structure
    attachments = [{"content": pdf_content, "filename": pdf_filename}]

    # Use the regular send_reply_email with attachment
    return send_reply_email(
        to_email=to_email,
        subject=subject,
        body=body,
        conversation_id=conversation_id,
        in_reply_to=in_reply_to,
        references=references,
        attachments=attachments,
    )


def format_followup_email_body(questions: str, conversation_id: str) -> str:
    """Format a follow-up email body.

    Args:
        questions: The questions or content to include
        conversation_id: Conversation ID for tracking

    Returns:
        Formatted email body
    """
    return f"""Thank you for your interest in our development services!

To better understand your project needs, could you please provide some additional information:

{questions}

Looking forward to your response!

Best regards,
The {SENDER_NAME} Team

--
Conversation ID: {conversation_id}
"""


def format_proposal_email_body(client_name: str, project_title: str, conversation_id: str) -> str:
    """Format a proposal email body.

    Args:
        client_name: Client's name
        project_title: Project title
        conversation_id: Conversation ID for tracking

    Returns:
        Formatted email body
    """
    return f"""Dear {client_name},

Thank you for discussing your project with us. We're excited about the opportunity to work on {project_title}.

Please find attached our detailed proposal for your review. The proposal includes:

• Project scope and deliverables
• Technical approach and architecture
• Timeline and milestones
• Investment details
• Terms and next steps

We believe this solution will effectively address your requirements and deliver significant value to your business.

Please review the proposal at your convenience, and feel free to reach out if you have any questions or would like to discuss any aspects in more detail.

Looking forward to partnering with you on this exciting project!

Best regards,
The {SENDER_NAME} Team

--
Conversation ID: {conversation_id}
"""


def extract_email_metadata(pending_reply: Dict[str, Any]) -> Dict[str, Any]:
    """Extract email metadata from a pending reply object.

    Args:
        pending_reply: Pending reply object from DynamoDB

    Returns:
        Dictionary with email metadata
    """
    metadata = pending_reply.get("metadata", {})

    # Always use email_body from metadata - it should always be present
    email_body = metadata.get("email_body", "")

    # Log error if email_body is missing (this should never happen with standardized data model)
    if not email_body:
        logger.error(
            f"Missing email_body in metadata for reply {pending_reply.get('reply_id', 'unknown')}"
        )

    return {
        "recipient": metadata.get("recipient", ""),
        "subject": metadata.get("subject", ""),
        "in_reply_to": metadata.get("in_reply_to"),
        "references": metadata.get("references", []),
        "should_send_pdf": metadata.get("should_send_pdf", False),
        "phase": pending_reply.get("phase", "unknown"),
        "body": email_body,
        "proposal_content": metadata.get("proposal_content", ""),  # For PDF generation
        "client_name": metadata.get("client_name", "Client"),
        "sender_name": metadata.get("sender_name", "The SoloPilot Team"),
    }
