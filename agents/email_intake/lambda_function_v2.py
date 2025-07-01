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
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Import modules using absolute imports for Lambda
from conversation_state_v2 import ConversationStateManagerV2
from email_parser import EmailParser
from requirement_extractor import RequirementExtractor
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

        # Parse email with enhanced threading support
        parser = EmailParser()
        parsed_email = parser.parse(email_content)

        # Initialize managers
        state_manager = ConversationStateManagerV2(table_name=DYNAMO_TABLE)
        extractor = RequirementExtractor()

        # Get conversation ID and original message ID
        conversation_id = parsed_email["conversation_id"]
        original_message_id = parsed_email.get("original_message_id", "")

        # Fetch or create conversation atomically
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

        # Check if requirements are complete
        if extractor.is_complete(updated_requirements):
            # Update status
            state_manager.update_status(conversation_id, "completed")

            # Send confirmation email
            confirmation_message_id = _send_confirmation_email_v2(
                parsed_email["from"], updated_requirements, conversation_id
            )

            # Track outbound reply if enabled
            if ENABLE_OUTBOUND_TRACKING and confirmation_message_id:
                _track_outbound_reply(
                    state_manager,
                    conversation_id,
                    confirmation_message_id,
                    "confirmation",
                    parsed_email["from"],
                )

            logger.info(f"Requirements complete for {conversation_id}")
        else:
            # Generate follow-up questions
            questions = extractor.generate_questions(updated_requirements)

            # Send follow-up email
            followup_message_id = _send_followup_email_v2(
                parsed_email["from"],
                parsed_email["subject"],
                questions,
                conversation_id,
                parsed_email.get("message_id", ""),
            )

            # Update status
            state_manager.update_status(conversation_id, "pending_info")

            # Track outbound reply if enabled
            if ENABLE_OUTBOUND_TRACKING and followup_message_id:
                _track_outbound_reply(
                    state_manager,
                    conversation_id,
                    followup_message_id,
                    "followup",
                    parsed_email["from"],
                )

            logger.info(f"Sent follow-up questions for {conversation_id}")

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
    to_email: str, subject: str, questions: str, conversation_id: str, in_reply_to: str
) -> Optional[str]:
    """Send follow-up email with proper threading headers."""
    body = f"""Thank you for your interest in our development services!

To better understand your project needs, could you please provide some additional information:

{questions}

Looking forward to your response!

Best regards,
The SoloPilot Team

--
Conversation ID: {conversation_id}
"""

    try:
        response = ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": f"Re: {subject}"},
                "Body": {"Text": {"Data": body}},
            },
            ReplyToAddresses=[SENDER_EMAIL],
            MessageTags=[
                {"Name": "conversation_id", "Value": conversation_id},
                {"Name": "email_type", "Value": "followup"},
            ],
            ConfigurationSetName=os.environ.get("SES_CONFIGURATION_SET", ""),
        )

        return response.get("MessageId")

    except Exception as e:
        logger.error(f"Error sending follow-up email: {str(e)}")
        return None


def _send_confirmation_email_v2(
    to_email: str, requirements: Dict[str, Any], conversation_id: str
) -> Optional[str]:
    """Send confirmation email with scope summary and threading headers."""
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
        response = ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": "Project Scope Confirmed - SoloPilot"},
                "Body": {"Text": {"Data": body}},
            },
            ReplyToAddresses=[SENDER_EMAIL],
            MessageTags=[
                {"Name": "conversation_id", "Value": conversation_id},
                {"Name": "email_type", "Value": "confirmation"},
            ],
            ConfigurationSetName=os.environ.get("SES_CONFIGURATION_SET", ""),
        )

        return response.get("MessageId")

    except Exception as e:
        logger.error(f"Error sending confirmation email: {str(e)}")
        return None


def _track_outbound_reply(
    state_manager: ConversationStateManagerV2,
    conversation_id: str,
    message_id: str,
    email_type: str,
    to_email: str,
) -> None:
    """Track outbound email in conversation history."""
    try:
        state_manager.add_outbound_reply(
            conversation_id,
            {
                "message_id": message_id,
                "from": SENDER_EMAIL,
                "to": [to_email],
                "subject": f"{email_type.title()} Email",
                "body": f"[System generated {email_type} email]",
                "metadata": {
                    "email_type": email_type,
                    "generated_by": "lambda_function_v2",
                },
            },
        )
        logger.info(
            f"Tracked outbound {email_type} email for conversation {conversation_id}"
        )
    except Exception as e:
        logger.warning(f"Failed to track outbound email: {str(e)}")
