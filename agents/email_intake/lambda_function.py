"""Enhanced AWS Lambda handler with multi-turn conversation support.

This version includes:
- Thread-safe conversation management with optimistic locking
- Enhanced email threading following RFC 5322
- Support for outbound reply tracking
- TTL-based conversation expiry
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

# Import modules using absolute imports for Lambda
from conversation_state import ConversationStateManager
from conversational_responder import ConversationalResponder
from email_parser import EmailParser
from requirement_extractor import RequirementExtractor
from pdf_generator import ProposalPDFGenerator
from utils import EmailThreadingUtils

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3_client = boto3.client("s3")
ses_client = boto3.client("ses")
sqs_client = boto3.client("sqs")

# Environment variables
QUEUE_URL = os.environ.get("REQUIREMENT_QUEUE_URL", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@solopilot.ai")
DYNAMO_TABLE = os.environ.get("DYNAMO_TABLE", "conversations")
ENABLE_OUTBOUND_TRACKING = (
    os.environ.get("ENABLE_OUTBOUND_TRACKING", "true").lower() == "true"
)
CALENDLY_LINK = os.environ.get("CALENDLY_LINK", "https://calendly.com/your-link")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Enhanced Lambda handler for processing incoming emails with thread safety.

    Args:
        event: Lambda event containing S3 bucket/key info
        context: Lambda context

    Returns:
        Response dict with status code and message
    """
    try:
        # Extract S3 info from SES event
        record = event["Records"][0]
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        logger.info(f"Processing email from S3: {bucket}/{key}")

        # Download email from S3
        email_obj = s3_client.get_object(Bucket=bucket, Key=key)
        email_content = email_obj["Body"].read().decode("utf-8")

        # Initialize managers first
        state_manager = ConversationStateManager(table_name=DYNAMO_TABLE)
        extractor = RequirementExtractor()
        
        # Parse email with state manager for conversation lookups
        parser = EmailParser(state_manager=state_manager)
        parsed_email = parser.parse(email_content)

        # Get conversation ID and original message ID
        conversation_id = parsed_email["conversation_id"]
        original_message_id = parsed_email.get("original_message_id", "")
        
        # Fetch or create conversation (conversation ID is now stable from message mapping)
        conversation = state_manager.fetch_or_create_conversation(
            conversation_id, original_message_id, parsed_email
        )

        # Check if this is an automated response
        if EmailThreadingUtils.is_automated_response(
            parsed_email["body"], parsed_email["subject"]
        ):
            logger.info(
                f"Skipping automated response for conversation {conversation_id}"
            )
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Automated response ignored"}),
            }

        # Append email with retry for concurrent access
        conversation = state_manager.append_email_with_retry(
            conversation_id,
            {
                "message_id": parsed_email["message_id"],
                "in_reply_to": parsed_email.get("in_reply_to", ""),
                "references": parsed_email.get("references", ""),
                "from": parsed_email["from"],
                "to": parsed_email.get("to", []),
                "cc": parsed_email.get("cc", []),
                "subject": parsed_email["subject"],
                "body": parsed_email["body"],
                "timestamp": parsed_email["timestamp"],
                "attachments": parsed_email.get("attachments", []),
                "direction": "inbound",
                "metadata": {
                    "s3_bucket": bucket,
                    "s3_key": key,
                    "is_reply": parsed_email["is_reply"],
                },
            },
            max_retries=2,  # Allow up to 2 retries for concurrent access
        )
        
        # Store message ID mapping for future thread lookups
        if parsed_email.get("message_id"):
            raw_msg_id = parsed_email["message_id"]
            canonical_msg_id = EmailThreadingUtils.canonicalize_message_id(raw_msg_id)
            logger.info(f"Storing incoming Message-ID mapping: raw='{raw_msg_id}' canonical='{canonical_msg_id}' -> {conversation_id}")
            if canonical_msg_id:
                state_manager.store_message_id_mapping(canonical_msg_id, conversation_id)
                logger.info(f"Successfully stored Message-ID mapping: {canonical_msg_id} -> {conversation_id}")
        
        # Also store our custom Message-ID if present (for replies to our emails)
        if parsed_email.get("x_solopilot_message_id"):
            custom_msg_id = EmailThreadingUtils.canonicalize_message_id(parsed_email["x_solopilot_message_id"])
            if custom_msg_id:
                logger.info(f"Storing custom SoloPilot Message-ID: {custom_msg_id} -> {conversation_id}")
                state_manager.store_message_id_mapping(custom_msg_id, conversation_id)

        # Extract/update requirements with version control
        current_version = conversation.get("requirements_version", 0)
        updated_requirements = extractor.extract(
            conversation["email_history"], conversation.get("requirements", {})
        )

        # Update requirements atomically
        try:
            conversation = state_manager.update_requirements_atomic(
                conversation_id, updated_requirements, expected_version=current_version
            )
        except ValueError as e:
            # Requirements were updated by another Lambda - refetch and retry once
            logger.warning(f"Requirements version conflict, retrying: {str(e)}")
            conversation = state_manager.fetch_or_create_conversation(
                conversation_id, original_message_id, parsed_email
            )
            updated_requirements = extractor.extract(
                conversation["email_history"], conversation.get("requirements", {})
            )
            conversation = state_manager.update_requirements_atomic(
                conversation_id, updated_requirements
            )

        # Always send to SQS after successful DynamoDB update
        _send_to_queue_enhanced(conversation_id, updated_requirements, conversation)

        # Use ConversationalResponder to generate appropriate response
        responder = ConversationalResponder(calendly_link=CALENDLY_LINK)
        response_text, response_metadata, llm_prompt = responder.generate_response_with_tracking(
            conversation, parsed_email
        )
        
        # Check reply mode (default to manual if not set)
        reply_mode = conversation.get("reply_mode", "manual")
        
        if reply_mode == "manual":
            # Queue response for manual approval
            logger.info(f"Manual mode - queuing response for approval")
            
            # Add pending reply
            metadata_to_store = {
                "recipient": parsed_email["from"],
                "subject": f"Re: {parsed_email['subject']}",
                "in_reply_to": parsed_email.get("message_id", ""),
                "references": conversation.get("thread_references", []),
                "should_send_pdf": response_metadata.get("should_send_proposal", False)
            }
            
            # If we have structured email_body and proposal_content, include them
            if "email_body" in response_metadata:
                metadata_to_store["email_body"] = response_metadata["email_body"]
            if "proposal_content" in response_metadata:
                metadata_to_store["proposal_content"] = response_metadata["proposal_content"]
            
            # Extract client name from conversation for better personalization
            email_history = conversation.get("email_history", [])
            client_name = "Client"  # Default
            for email in email_history:
                if email.get("direction") == "inbound" and email.get("from"):
                    # Try to extract name from email address
                    from_email = email["from"]
                    if "@" in from_email:
                        client_name = from_email.split("@")[0].replace(".", " ").replace("_", " ").title()
                        break
            
            metadata_to_store["client_name"] = client_name
            metadata_to_store["sender_name"] = responder.sender_name
            
            state_manager.add_pending_reply(
                conversation_id,
                llm_prompt,
                response_text,
                response_metadata.get("phase", "unknown"),
                metadata_to_store
            )
            
            logger.info(f"Response queued for manual approval in conversation {conversation_id}")
        else:
            # Auto mode - send immediately
            logger.info(f"Auto mode - sending response immediately")
            
            # Determine email type and send
            if response_metadata.get("phase") == "proposal_draft":
                # Send proposal email
                result = _send_confirmation_email_v2(
                    parsed_email["from"], updated_requirements, conversation_id
                )
            else:
                # Send follow-up email
                result = _send_followup_email_v2(
                    parsed_email["from"],
                    parsed_email["subject"],
                    response_text,
                    conversation_id,
                    parsed_email.get("message_id", ""),
                    conversation.get("original_message_id", ""),
                    conversation.get("thread_references", []),
                )
            
            # Track outbound reply if enabled
            if ENABLE_OUTBOUND_TRACKING and result:
                _track_outbound_reply(
                    state_manager,
                    conversation_id,
                    result,  # Pass the full tuple (ses_message_id, generated_message_id)
                    response_metadata.get("phase", "followup"),
                    parsed_email["from"],
                )
            
            logger.info(f"Sent {response_metadata.get('phase', 'followup')} email for {conversation_id}")
        
        # Update conversation phase
        if "phase" in response_metadata:
            new_phase = responder.determine_phase_transition(
                conversation.get("phase", "understanding"),
                response_metadata,
                conversation,
                parsed_email
            )
            if new_phase:
                state_manager.update_phase(conversation_id, new_phase)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Email processed successfully",
                    "conversation_id": conversation_id,
                    "email_count": len(conversation.get("email_history", [])),
                    "status": conversation.get("status"),
                }
            ),
        }

    except ClientError as e:
        logger.error(f"AWS error processing email: {str(e)}")
        return {
            "statusCode": 503,
            "body": json.dumps({"error": "Service temporarily unavailable"}),
        }
    except Exception as e:
        logger.error(f"Error processing email: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def _send_to_queue_enhanced(
    conversation_id: str, requirements: Dict[str, Any], conversation: Dict[str, Any]
) -> None:
    """Send enhanced message to SQS with conversation metadata."""
    message = {
        "conversation_id": conversation_id,
        "requirements": requirements,
        "requirements_version": conversation.get("requirements_version", 0),
        "status": conversation.get("status", "active"),
        "email_count": len(conversation.get("email_history", [])),
        "participants": list(conversation.get("participants", [])),
        "subject": conversation.get("subject", ""),
        "created_at": conversation.get("created_at"),
        "updated_at": conversation.get("updated_at"),
        "source": "email_intake_v2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        response = sqs_client.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(message),
            MessageAttributes={
                "conversation_id": {
                    "StringValue": conversation_id,
                    "DataType": "String",
                },
                "status": {
                    "StringValue": conversation.get("status", "active"),
                    "DataType": "String",
                },
            },
        )

        if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            raise Exception(
                f"SQS send_message returned status {response['ResponseMetadata']['HTTPStatusCode']}"
            )

        logger.info(
            f"Sent enhanced message to SQS: queue_url={QUEUE_URL}, "
            f"conversation_id={conversation_id}, message_id={response['MessageId']}"
        )

    except Exception as e:
        logger.error(f"Failed to send message to SQS: {str(e)}")
        raise


def _send_followup_email_v2(
    to_email: str, 
    subject: str, 
    questions: str, 
    conversation_id: str, 
    in_reply_to: str,
    original_message_id: str,
    thread_references: List[str]
) -> Optional[str]:
    """Send follow-up email with proper threading headers."""
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import email.utils
    from email_sender import format_followup_email_body
    
    # Use the formatted email body that includes conversation ID
    body = format_followup_email_body(questions, conversation_id)

    try:
        # Create MIME message with proper headers
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = f"Re: {subject}"
        
        # Don't set Message-ID - let SES handle it
        # But add our custom tracking ID
        our_tracking_id = email.utils.make_msgid(domain="solopilot.abdulkhurram.com")
        msg["X-SoloPilot-Message-ID"] = our_tracking_id
        msg["X-Conversation-ID"] = conversation_id
        
        # Set In-Reply-To to the message we're replying to
        msg["In-Reply-To"] = f"<{in_reply_to}>"
        
        # Build References header with proper chain
        # Start with original message ID if available
        reference_ids = []
        if original_message_id and original_message_id not in reference_ids:
            reference_ids.append(f"<{original_message_id}>")
        
        # Add any existing thread references
        for ref in thread_references:
            if ref and f"<{ref}>" not in reference_ids:
                reference_ids.append(f"<{ref}>")
        
        # Add the message we're replying to if not already included
        if in_reply_to and f"<{in_reply_to}>" not in reference_ids:
            reference_ids.append(f"<{in_reply_to}>")
        
        # Join all references
        references_chain = " ".join(reference_ids)
        msg["References"] = references_chain
        
        msg["Reply-To"] = SENDER_EMAIL
        
        # Add body
        msg.attach(MIMEText(body, "plain"))
        
        # Send raw email
        response = ses_client.send_raw_email(
            Source=SENDER_EMAIL,
            Destinations=[to_email],
            RawMessage={"Data": msg.as_string()},
            Tags=[
                {"Name": "conversation_id", "Value": conversation_id},
                {"Name": "email_type", "Value": "followup"},
            ],
        )

        # Extract the message ID without angle brackets for storage
        ses_message_id = response.get("MessageId")
        if ses_message_id:
            # Return tuple of (SES message ID, our tracking ID)
            logger.info(f"Sent follow-up email - SES: {ses_message_id}, Tracking: {our_tracking_id}")
            return (ses_message_id, our_tracking_id.strip("<>"))
        
        return None

    except Exception as e:
        logger.error(f"Error sending follow-up email: {str(e)}")
        return None


def _send_confirmation_email_v2(
    to_email: str, requirements: Dict[str, Any], conversation_id: str
) -> Optional[str]:
    """Send confirmation email with scope summary and threading headers."""
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import email.utils
    
    features = "\n".join(
        [f"- {f['name']}: {f['desc']}" for f in requirements.get("features", [])]
    )

    body = f"""Thank you for providing all the information!

Here's what we understand about your project:

**Project:** {requirements.get('title', 'Your Project')}
**Type:** {requirements.get('project_type', 'N/A')}
**Timeline:** {requirements.get('timeline', 'To be discussed')}
**Budget:** {requirements.get('budget', 'To be discussed')}

**Key Features:**
{features}

We'll begin working on your project plan and development roadmap. You'll receive our detailed proposal within 24 hours.

Best regards,
The SoloPilot Team

--
Conversation ID: {conversation_id}
"""

    try:
        # Create MIME message with proper headers
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = "Project Scope Confirmed - SoloPilot"
        our_message_id = email.utils.make_msgid(domain="solopilot.abdulkhurram.com")
        msg["Message-ID"] = our_message_id
        # Note: No In-Reply-To for confirmation as it starts a new thread
        msg["Reply-To"] = SENDER_EMAIL
        
        # Add body
        msg.attach(MIMEText(body, "plain"))
        
        # Send raw email
        response = ses_client.send_raw_email(
            Source=SENDER_EMAIL,
            Destinations=[to_email],
            RawMessage={"Data": msg.as_string()},
            Tags=[
                {"Name": "conversation_id", "Value": conversation_id},
                {"Name": "email_type", "Value": "confirmation"},
            ],
        )

        ses_message_id = response.get("MessageId")
        if ses_message_id:
            # CRITICAL: SES replaces our Message-ID with its own format
            # We need to store BOTH for proper threading
            logger.info(f"Sent confirmation email - Generated: {our_message_id}, SES: {ses_message_id}")
            # Return tuple of (SES message ID, our generated message ID for dual tracking)
            return (ses_message_id, our_message_id.strip("<>"))
        
        return None

    except Exception as e:
        logger.error(f"Error sending confirmation email: {str(e)}")
        return None


def _track_outbound_reply(
    state_manager: ConversationStateManager,
    conversation_id: str,
    message_ids: Tuple[str, str],
    email_type: str,
    to_email: str,
) -> None:
    """Track outbound email in conversation history and store message ID mapping.
    
    Args:
        state_manager: Conversation state manager
        conversation_id: Conversation ID
        message_ids: Tuple of (ses_message_id, our_generated_message_id)
        email_type: Type of email sent
        to_email: Recipient email
    """
    try:
        ses_message_id, our_message_id = message_ids
        
        state_manager.add_outbound_reply(
            conversation_id,
            {
                "message_id": ses_message_id,  # Store SES ID in history
                "generated_message_id": our_message_id,  # Also store our ID
                "from": SENDER_EMAIL,
                "to": [to_email],
                "subject": f"{email_type.title()} Email",
                "body": f"[System generated {email_type} email]",
                "metadata": {
                    "email_type": email_type,
                    "generated_by": "lambda_function",
                },
            },
        )
        
        # Store SES Message ID mapping - this is what appears in email headers!
        if ses_message_id:
            # Store the SES Message-ID in the format email clients will use
            ses_formatted_id = f"{ses_message_id}@us-east-2.amazonses.com"
            canonical_ses_id = EmailThreadingUtils.canonicalize_message_id(ses_formatted_id)
            state_manager.store_message_id_mapping(canonical_ses_id, conversation_id)
            logger.info(f"Stored SES Message-ID mapping: {canonical_ses_id} -> {conversation_id}")
            
            # Also store without domain for robustness
            canonical_ses_id_no_domain = EmailThreadingUtils.canonicalize_message_id(ses_message_id)
            state_manager.store_message_id_mapping(canonical_ses_id_no_domain, conversation_id)
            logger.info(f"Stored SES Message-ID (no domain) mapping: {canonical_ses_id_no_domain} -> {conversation_id}")
        
        # Also store our custom tracking ID if present
        if our_message_id:
            canonical_tracking_id = EmailThreadingUtils.canonicalize_message_id(our_message_id)
            if canonical_tracking_id:
                state_manager.store_message_id_mapping(canonical_tracking_id, conversation_id)
                logger.info(f"Stored custom tracking ID mapping: {canonical_tracking_id} -> {conversation_id}")
        
        logger.info(
            f"Tracked outbound {email_type} email for conversation {conversation_id}"
        )
    except Exception as e:
        logger.warning(f"Failed to track outbound email: {str(e)}")
