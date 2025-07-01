"""AWS Lambda handler for email intake agent.

Processes incoming emails from Apollo.io, maintains conversation state,
extracts requirements, and pushes to SQS when ready.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3

from .conversation_state import ConversationStateManager
from .email_parser import EmailParser
from .requirement_extractor import RequirementExtractor

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


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler for processing incoming emails.

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

        # Parse email
        parser = EmailParser()
        parsed_email = parser.parse(email_content)

        # Initialize managers
        state_manager = ConversationStateManager(table_name=DYNAMO_TABLE)
        extractor = RequirementExtractor()

        # Get or create conversation state
        conversation_id = parsed_email["thread_id"]
        conversation = state_manager.get_or_create(conversation_id)

        # Add new email to history
        conversation = state_manager.add_email(
            conversation_id,
            {
                "from": parsed_email["from"],
                "subject": parsed_email["subject"],
                "body": parsed_email["body"],
                "timestamp": parsed_email["timestamp"],
            },
        )

        # Extract/update requirements
        updated_requirements = extractor.extract(
            conversation["email_history"], conversation.get("requirements", {})
        )

        # Update conversation with new requirements
        conversation = state_manager.update_requirements(conversation_id, updated_requirements)

        # Always send to SQS after DynamoDB update
        _send_to_queue(conversation_id, updated_requirements, conversation)

        # Check if requirements are complete
        if extractor.is_complete(updated_requirements):
            # Update status
            state_manager.update_status(conversation_id, "completed")

            # Send confirmation email
            _send_confirmation_email(parsed_email["from"], updated_requirements)

            logger.info(f"Requirements complete for {conversation_id}")
        else:
            # Generate follow-up questions
            questions = extractor.generate_questions(updated_requirements)

            # Send follow-up email
            _send_followup_email(parsed_email["from"], parsed_email["subject"], questions)

            # Update status
            state_manager.update_status(conversation_id, "pending_info")

            logger.info(f"Sent follow-up questions for {conversation_id}")

        return {"statusCode": 200, "body": json.dumps({"message": "Email processed successfully"})}

    except Exception as e:
        logger.error(f"Error processing email: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def _send_to_queue(conversation_id: str, requirements: Dict[str, Any], conversation: Dict[str, Any]) -> None:
    """Send requirements to SQS queue after DynamoDB update.
    
    Args:
        conversation_id: Unique conversation identifier
        requirements: Current requirements state
        conversation: Full conversation data from DynamoDB
        
    Raises:
        Exception: If SQS send_message fails
    """
    message = {
        "conversation_id": conversation_id,
        "requirements": requirements,
        "status": conversation.get("status", "active"),
        "email_count": len(conversation.get("email_history", [])),
        "source": "email_intake",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        response = sqs_client.send_message(
            QueueUrl=QUEUE_URL, 
            MessageBody=json.dumps(message)
        )
        
        # Check for successful send
        if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            raise Exception(f"SQS send_message returned status {response['ResponseMetadata']['HTTPStatusCode']}")
        
        logger.info(f"Sent message to SQS: queue_url={QUEUE_URL}, conversation_id={conversation_id}, message_id={response['MessageId']}")
        
    except Exception as e:
        logger.error(f"Failed to send message to SQS: {str(e)}")
        raise


def _send_followup_email(to_email: str, subject: str, questions: str) -> None:
    """Send follow-up email with questions."""
    body = f"""Thank you for your interest in our development services!

To better understand your project needs, could you please provide some additional information:

{questions}

Looking forward to your response!

Best regards,
The SoloPilot Team
"""

    ses_client.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [to_email]},
        Message={"Subject": {"Data": f"Re: {subject}"}, "Body": {"Text": {"Data": body}}},
    )


def _send_confirmation_email(to_email: str, requirements: Dict[str, Any]) -> None:
    """Send confirmation email with scope summary."""
    features = "\n".join([f"- {f['name']}: {f['desc']}" for f in requirements.get("features", [])])

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
"""

    ses_client.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": "Project Scope Confirmed - SoloPilot"},
            "Body": {"Text": {"Data": body}},
        },
    )
