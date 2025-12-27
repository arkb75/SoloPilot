"""Email sender module for sending replies via AWS SES."""

import email.utils
import html
import logging
import os
import re
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# AWS SES client
ses_client = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-2"))

# Email configuration
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "intake@solopilot.abdulkhurram.com")
SENDER_NAME = os.environ.get("SENDER_NAME", "SoloPilot")

_ALLOWED_HTML_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "u",
    "s",
    "ol",
    "ul",
    "li",
    "a",
    "hr",
}
_ALLOWED_HTML_ATTRS = {"a": {"href", "target", "rel"}}
_SELF_CLOSING_TAGS = {"br", "hr"}


def _append_conversation_id(body: str, conversation_id: str) -> str:
    if f"Conversation ID: {conversation_id}" in body:
        return body
    return f"{body}\n\n--\nConversation ID: {conversation_id}"


def _append_conversation_id_html(body: str, conversation_id: str) -> str:
    if f"Conversation ID: {conversation_id}" in body:
        return body
    return f"{body}<hr><p>Conversation ID: {conversation_id}</p>"


def _strip_markdown(text: str) -> str:
    stripped = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    stripped = re.sub(r"\*([^*]+)\*", r"\1", stripped)
    stripped = re.sub(r"_([^_]+)_", r"\1", stripped)
    return stripped


def _is_html_body(text: str) -> bool:
    return bool(re.search(r"</?(p|br|strong|em|u|s|ol|ul|li|a|hr)\b", text, re.IGNORECASE))


class _HTMLSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        if tag_lower not in _ALLOWED_HTML_TAGS:
            return
        if tag_lower in _SELF_CLOSING_TAGS:
            self.parts.append(f"<{tag_lower}>")
            return
        safe_attrs = []
        allowed_attrs = _ALLOWED_HTML_ATTRS.get(tag_lower, set())
        for key, value in attrs:
            if key not in allowed_attrs or value is None:
                continue
            cleaned_value = value.strip()
            if key == "href" and cleaned_value.lower().startswith("javascript:"):
                continue
            safe_attrs.append(f'{key}="{html.escape(cleaned_value, quote=True)}"')
        attr_text = f" {' '.join(safe_attrs)}" if safe_attrs else ""
        self.parts.append(f"<{tag_lower}{attr_text}>")

    def handle_startendtag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in _ALLOWED_HTML_TAGS:
            self.parts.append(f"<{tag_lower}>")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in _ALLOWED_HTML_TAGS and tag_lower not in _SELF_CLOSING_TAGS:
            self.parts.append(f"</{tag_lower}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(html.escape(data))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(html.escape(html.unescape(f"&{name};")))

    def handle_charref(self, name: str) -> None:
        self.parts.append(html.escape(html.unescape(f"&#{name};")))

    def get_html(self) -> str:
        return "".join(self.parts)


def _sanitize_html(text: str) -> str:
    sanitizer = _HTMLSanitizer()
    sanitizer.feed(text or "")
    sanitizer.close()
    return sanitizer.get_html()


def _html_to_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<\s*hr\s*/?\s*>", "\n\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</\s*p\s*>", "\n\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<\s*p[^>]*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<\s*li[^>]*>", "- ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</\s*li\s*>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</\s*(ul|ol)\s*>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    return html.unescape(cleaned).strip()


def _markdown_to_html(text: str) -> str:
    escaped = html.escape(text or "", quote=False)
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"_([^_]+)_", r"<em>\1</em>", escaped)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", escaped) if p.strip()]
    rendered = []
    for paragraph in paragraphs:
        rendered.append(f"<p>{paragraph.replace(chr(10), '<br>')}</p>")
    return "\n".join(rendered) if rendered else escaped.replace("\n", "<br>")


def send_reply_email(
    to_email: str,
    subject: str,
    body: str,
    conversation_id: str,
    body_format: Optional[str] = None,
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
        body_format: Optional hint for body format ("html" or "markdown")
        in_reply_to: Message-ID of the email being replied to
        references: List of Message-IDs in the thread
        attachments: Optional list of attachments

    Returns:
        Tuple of (success, ses_message_id, error_message)
    """
    # Guard clause: Prevent sending proposal emails without PDFs
    # Check if the body indicates this should be a proposal with attachment
    logger.info(f"[INVARIANT_CHECK] Body mentions attachment: {'Please find the proposal attached' in body or 'Please find attached' in body}")
    logger.info(f"[INVARIANT_CHECK] Has attachments: {bool(attachments)}")
    
    if (
        "Please find the proposal attached" in body or "Please find attached" in body
    ) and not attachments:
        error_msg = f"Invariant violated: Attempted to send proposal email without PDF attachment for conversation {conversation_id}"
        logger.error(f"[INVARIANT_VIOLATION] {error_msg}")
        logger.error(f"[INVARIANT_VIOLATION] Body preview: {body[:200]}...")
        raise RuntimeError(error_msg)

    try:
        # Create MIME message
        msg = MIMEMultipart("mixed" if attachments else "alternative")
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
        format_hint = (body_format or "").lower().strip()
        if format_hint == "html" or (not format_hint and _is_html_body(body)):
            html_body = _append_conversation_id_html(body, conversation_id)
            html_body = _sanitize_html(html_body)
            plain_body = _html_to_text(html_body)
        else:
            body_with_tracking = _append_conversation_id(body, conversation_id)
            plain_body = _strip_markdown(body_with_tracking)
            html_body = _markdown_to_html(body_with_tracking)

        if attachments:
            alternative = MIMEMultipart("alternative")
            alternative.attach(MIMEText(plain_body, "plain"))
            alternative.attach(MIMEText(html_body, "html"))
            msg.attach(alternative)
        else:
            msg.attach(MIMEText(plain_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

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
    body_format: Optional[str] = None,
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
        body_format=body_format,
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

    # Primary source: email_body from metadata (may be edited via amend_reply)
    email_body = metadata.get("email_body", "")

    # Backward compatibility: Check for legacy amended_content field
    # This handles existing data where edits were stored separately
    if not email_body and pending_reply.get("amended_content"):
        email_body = pending_reply["amended_content"]
        logger.info(f"Using legacy amended_content for reply {pending_reply.get('reply_id', 'unknown')}")
    
    # Log error if email_body is still missing (this should never happen with standardized data model)
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
        "body_format": metadata.get("email_body_format"),
        "proposal_content": metadata.get("proposal_content", ""),  # For PDF generation
        "client_name": metadata.get("client_name", "Client"),
        "sender_name": metadata.get("sender_name", "The SoloPilot Team"),
    }
