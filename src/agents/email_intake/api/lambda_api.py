"""
Lambda function for Email Agent Management API

This provides REST API endpoints for managing conversations,
approving/rejecting replies, and viewing conversation history.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError

from src.agents.email_intake.conversation_state import (  # Needed to append sent email to history
    ConversationStateManager,
)
from src.agents.email_intake.email_sender import (
    extract_email_metadata,
    format_proposal_email_body,
    send_proposal_email,
    send_reply_email,
)

# Initialize services
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

# Configuration
TABLE_NAME = os.environ.get("CONVERSATIONS_TABLE", "conversations")
S3_BUCKET = os.environ.get("ATTACHMENTS_BUCKET", "solopilot-attachments")
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Outbound sender address (keep in sync with Lambda sender config)
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@solopilot.ai")

# Type deserializer for DynamoDB
deserializer = TypeDeserializer()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler for API requests."""
    try:
        # Log request
        logger.info(f"Request: {json.dumps(event)}")

        # Parse request
        http_method = event.get("httpMethod", "")
        path = event.get("path", "")
        path_params = event.get("pathParameters", {})
        query_params = event.get("queryStringParameters", {})
        body = json.loads(event.get("body", "{}")) if event.get("body") else {}

        # If pathParameters is empty but we have a path, try to extract IDs manually
        # This handles direct Lambda invocations (not through API Gateway)
        if not path_params and path:
            # Extract reply ID from paths like /replies/{id}/approve
            if "/replies/" in path:
                parts = path.split("/")
                if len(parts) >= 3:
                    path_params["id"] = parts[2]
            # Extract conversation ID from paths like /conversations/{id}
            elif "/conversations/" in path:
                parts = path.split("/")
                if len(parts) >= 3:
                    path_params["id"] = parts[2]

        # Route request
        if path == "/conversations" and http_method == "GET":
            response = list_conversations(query_params)
        elif (
            path.startswith("/conversations/") and path.endswith("/mode") and http_method == "PATCH"
        ):
            conversation_id = path_params.get("id")
            response = update_conversation_mode(conversation_id, body)
        elif (
            path.startswith("/conversations/")
            and path.endswith("/pending-replies")
            and http_method == "GET"
        ):
            conversation_id = path_params.get("id")
            response = get_pending_replies(conversation_id)
        elif path.startswith("/conversations/") and http_method == "GET":
            conversation_id = path_params.get("id")
            response = get_conversation_detail(conversation_id)
        elif path.startswith("/replies/") and path.endswith("/approve") and http_method == "POST":
            reply_id = path_params.get("id")
            response = approve_reply(reply_id, body)
        elif path.startswith("/replies/") and path.endswith("/reject") and http_method == "POST":
            reply_id = path_params.get("id")
            response = reject_reply(reply_id, body)
        elif path.startswith("/replies/") and path.endswith("/prompt") and http_method == "GET":
            reply_id = path_params.get("id")
            response = get_reply_prompt(reply_id)
        elif path.startswith("/replies/") and http_method == "PATCH":
            reply_id = path_params.get("id")
            response = amend_reply(reply_id, body)
        elif path.startswith("/attachments/") and http_method == "GET":
            attachment_id = path_params.get("id")
            response = get_attachment_url(attachment_id)
        else:
            response = {"statusCode": 404, "body": json.dumps({"error": "Not found"})}

        # Add CORS headers
        if "statusCode" in response:
            response["headers"] = {
                "Access-Control-Allow-Origin": CORS_ORIGIN,
                "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
                "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS",
            }

        return response

    except Exception as e:
        logger.error(f"Error handling request: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": CORS_ORIGIN,
                "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
                "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS",
            },
            "body": json.dumps({"error": "Internal server error"}),
        }


def list_conversations(query_params: Dict[str, str]) -> Dict[str, Any]:
    """List all conversations with pagination."""
    try:
        table = dynamodb.Table(TABLE_NAME)

        # Pagination parameters
        limit = int(query_params.get("limit", "20"))
        last_evaluated_key = query_params.get("nextToken")

        # Build scan parameters
        scan_params = {
            "Limit": limit,
            "ProjectionExpression": "conversation_id, subject, participants, phase, reply_mode, created_at, updated_at",
        }

        if last_evaluated_key:
            scan_params["ExclusiveStartKey"] = json.loads(last_evaluated_key)

        # Scan table
        response = table.scan(**scan_params)

        # Process items
        conversations = []
        for item in response.get("Items", []):
            # Check for pending replies
            pending_count = 0
            if "pending_replies" in item:
                pending_count = sum(
                    1 for r in item["pending_replies"] if r.get("status") == "pending"
                )

            conversations.append(
                {
                    "conversation_id": item["conversation_id"],
                    "subject": item.get("subject", "No subject"),
                    "client_email": _extract_client_email(item.get("participants", [])),
                    "phase": item.get("phase", "unknown"),
                    "reply_mode": item.get("reply_mode", "manual"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                    "pending_replies": pending_count,
                }
            )

        # Sort by updated_at descending
        conversations.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        # Build response
        result = {"conversations": conversations, "count": len(conversations)}

        if "LastEvaluatedKey" in response:
            result["nextToken"] = json.dumps(response["LastEvaluatedKey"], default=str)

        return {"statusCode": 200, "body": json.dumps(result, default=str)}

    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to list conversations"})}


def get_conversation_detail(conversation_id: str) -> Dict[str, Any]:
    """Get full conversation details including email history."""
    try:
        table = dynamodb.Table(TABLE_NAME)

        # Get conversation
        response = table.get_item(Key={"conversation_id": conversation_id})

        if "Item" not in response:
            return {"statusCode": 404, "body": json.dumps({"error": "Conversation not found"})}

        conversation = response["Item"]

        # Convert Decimal to int/float for JSON serialization
        conversation = _convert_decimals(conversation)

        # Add computed fields
        conversation["client_email"] = _extract_client_email(conversation.get("participants", []))
        conversation["email_count"] = len(conversation.get("email_history", []))

        return {"statusCode": 200, "body": json.dumps(conversation, default=str)}

    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id}: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to get conversation"})}


def update_conversation_mode(conversation_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Update conversation reply mode (auto/manual)."""
    try:
        table = dynamodb.Table(TABLE_NAME)

        # Validate mode
        mode = body.get("mode")
        if mode not in ["auto", "manual"]:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid mode. Must be 'auto' or 'manual'"}),
            }

        # Update conversation
        response = table.update_item(
            Key={"conversation_id": conversation_id},
            UpdateExpression="SET reply_mode = :mode, updated_at = :updated",
            ExpressionAttributeValues={
                ":mode": mode,
                ":updated": datetime.now(timezone.utc).isoformat(),
            },
            ReturnValues="ALL_NEW",
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "conversation_id": conversation_id,
                    "reply_mode": mode,
                    "updated_at": response["Attributes"]["updated_at"],
                }
            ),
        }

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return {"statusCode": 404, "body": json.dumps({"error": "Conversation not found"})}
        raise
    except Exception as e:
        logger.error(f"Error updating conversation mode: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to update conversation mode"}),
        }


def get_pending_replies(conversation_id: str) -> Dict[str, Any]:
    """Get pending replies for a conversation."""
    try:
        table = dynamodb.Table(TABLE_NAME)

        # Get conversation
        response = table.get_item(
            Key={"conversation_id": conversation_id}, ProjectionExpression="pending_replies"
        )

        if "Item" not in response:
            return {"statusCode": 404, "body": json.dumps({"error": "Conversation not found"})}

        # Filter pending replies
        pending_replies = []
        for reply in response["Item"].get("pending_replies", []):
            if reply.get("status") == "pending":
                pending_replies.append(_convert_decimals(reply))

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "conversation_id": conversation_id,
                    "pending_replies": pending_replies,
                    "count": len(pending_replies),
                },
                default=str,
            ),
        }

    except Exception as e:
        logger.error(f"Error getting pending replies: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to get pending replies"})}


def approve_reply(reply_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Approve a pending reply and send it."""
    try:
        conversation_id = body.get("conversation_id")
        if not conversation_id:
            return {"statusCode": 400, "body": json.dumps({"error": "conversation_id is required"})}

        table = dynamodb.Table(TABLE_NAME)

        # Get conversation
        response = table.get_item(Key={"conversation_id": conversation_id})

        if "Item" not in response:
            return {"statusCode": 404, "body": json.dumps({"error": "Conversation not found"})}

        conversation = response["Item"]
        pending_replies = conversation.get("pending_replies", [])

        # Find the reply
        reply_index = None
        reply_data = None
        for i, reply in enumerate(pending_replies):
            if reply.get("reply_id") == reply_id:
                reply_index = i
                reply_data = reply
                break

        if reply_index is None:
            return {"statusCode": 404, "body": json.dumps({"error": "Reply not found"})}

        if reply_data.get("status") != "pending":
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Reply is already {reply_data.get('status')}"}),
            }

        # Extract email metadata from the pending reply BEFORE updating status
        email_meta = extract_email_metadata(reply_data)

        # Store timestamp for later use
        now = datetime.now(timezone.utc).isoformat()

        # Check if we should send a PDF proposal
        if email_meta.get("should_send_pdf") and email_meta.get("phase") == "proposal_draft":
            # Generate PDF proposal
            try:
                from src.agents.email_intake.pdf_generator import ProposalPDFGenerator

                # Get PDF Lambda ARN from environment
                pdf_lambda_arn = os.environ.get("PDF_LAMBDA_ARN", "")
                if not pdf_lambda_arn:
                    # FAIL LOUDLY - no fallback email
                    error_details = {
                        "error": "PDF_LAMBDA_ARN not configured",
                        "error_type": "ConfigurationError",
                        "conversation_id": conversation_id,
                        "client_email": email_meta["recipient"],
                    }
                    logger.error(f"PDF_GENERATION_FAILED: {json.dumps(error_details)}")

                    return {
                        "statusCode": 500,
                        "body": json.dumps(
                            {
                                "error": "PDF generation service not configured",
                                "details": error_details,
                                "message": "Please configure PDF_LAMBDA_ARN environment variable",
                            }
                        ),
                    }
                else:
                    # Initialize PDF generator
                    pdf_generator = ProposalPDFGenerator(pdf_lambda_arn)

                    # Generate PDF
                    pdf_bytes, pdf_error = pdf_generator.generate_proposal_pdf(conversation)

                    if pdf_bytes:
                        # Extract client name and project title
                        proposal_data = pdf_generator.extract_proposal_data(conversation)
                        client_name = proposal_data.get("clientName", "Client")
                        project_title = proposal_data.get("projectTitle", "Your Project")

                        # Use the actual LLM-generated email body from metadata
                        # This ensures what the user sees in frontend is what gets sent
                        email_body_to_send = email_meta.get("body", "")

                        # Fallback to formatted template only if no body exists (shouldn't happen)
                        if not email_body_to_send:
                            logger.warning("No email body in metadata, using template fallback")
                            email_body_to_send = format_proposal_email_body(
                                client_name=client_name,
                                project_title=project_title,
                                conversation_id=conversation_id,
                            )

                        # Send email with PDF attachment
                        success, ses_message_id, error_msg = send_proposal_email(
                            to_email=email_meta["recipient"],
                            subject=email_meta["subject"],
                            body=email_body_to_send,
                            conversation_id=conversation_id,
                            pdf_content=pdf_bytes,
                            pdf_filename=f"{client_name.replace(' ', '_')}_proposal.pdf",
                            in_reply_to=email_meta.get("in_reply_to"),
                            references=email_meta.get("references", []),
                        )
                    else:
                        # PDF generation failed - FAIL LOUDLY
                        error_details = {
                            "error": "PDF generation failed",
                            "error_type": "PdfGenerationError",
                            "conversation_id": conversation_id,
                            "client_email": email_meta["recipient"],
                            "pdf_error": pdf_error,
                        }
                        logger.error(f"PDF_GENERATION_FAILED: {json.dumps(error_details)}")

                        # DO NOT update conversation state
                        # DO NOT send any emails
                        return {
                            "statusCode": 500,
                            "body": json.dumps(
                                {
                                    "error": "Failed to generate PDF proposal",
                                    "details": error_details,
                                    "message": "Please check CloudWatch logs and fix the issue before retrying",
                                }
                            ),
                        }
            except Exception as pdf_e:
                # Any exception during PDF generation - FAIL LOUDLY
                error_details = {
                    "error": "PDF generation exception",
                    "error_type": "PdfGenerationException",
                    "conversation_id": conversation_id,
                    "client_email": email_meta["recipient"],
                    "exception": str(pdf_e),
                }
                logger.error(f"PDF_GENERATION_FAILED: {json.dumps(error_details)}", exc_info=True)

                # DO NOT update conversation state
                # DO NOT send any emails
                return {
                    "statusCode": 500,
                    "body": json.dumps(
                        {
                            "error": "PDF generation service error",
                            "details": error_details,
                            "message": "An error occurred during PDF generation. Please check logs and retry.",
                        }
                    ),
                }
        else:
            # Send regular text email
            success, ses_message_id, error_msg = send_reply_email(
                to_email=email_meta["recipient"],
                subject=email_meta["subject"],
                body=email_meta["body"],
                conversation_id=conversation_id,
                in_reply_to=email_meta.get("in_reply_to"),
                references=email_meta.get("references", []),
            )

        if not success:
            logger.error(f"Failed to send email: {error_msg}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Failed to send email: {error_msg}"}),
            }

        # Only NOW update the reply status after successful email sending
        pending_replies[reply_index]["status"] = "approved"
        pending_replies[reply_index]["reviewed_at"] = now
        pending_replies[reply_index]["reviewed_by"] = body.get("reviewed_by", "admin")
        pending_replies[reply_index]["sent_at"] = now
        pending_replies[reply_index]["ses_message_id"] = ses_message_id

        # Store message ID mapping for proper threading
        # SES uses the MessageId as the actual Message-ID in format: <MessageId@us-east-2.amazonses.com>
        if ses_message_id:
            try:
                # Import canonicalization function
                from src.agents.email_intake.utils import EmailThreadingUtils

                message_map_table = dynamodb.Table("email_message_map")
                # Store the SES Message-ID in the format email clients will use
                ses_formatted_id = f"{ses_message_id}@us-east-2.amazonses.com"
                canonical_ses_id = EmailThreadingUtils.canonicalize_message_id(ses_formatted_id)

                # Store with full format (canonical)
                message_map_table.put_item(
                    Item={
                        "message_id": canonical_ses_id,
                        "conversation_id": conversation_id,
                        "created_at": now,
                        "ttl": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
                    }
                )
                logger.info(
                    f"Stored SES Message-ID mapping: {canonical_ses_id} -> {conversation_id}"
                )

                # Also store without domain for robustness (canonical)
                canonical_ses_id_no_domain = EmailThreadingUtils.canonicalize_message_id(
                    ses_message_id
                )
                message_map_table.put_item(
                    Item={
                        "message_id": canonical_ses_id_no_domain,
                        "conversation_id": conversation_id,
                        "created_at": now,
                        "ttl": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
                    }
                )
                logger.info(
                    f"Stored SES Message-ID (no domain) mapping: {canonical_ses_id_no_domain} -> {conversation_id}"
                )
            except Exception as map_error:
                logger.error(f"Failed to store message ID mapping: {str(map_error)}")
                # Don't fail the operation if mapping storage fails

        # ------------------------------------------------------------------
        #  Add the outbound email to email_history so the frontend sees it
        # ------------------------------------------------------------------
        try:
            state_mgr = ConversationStateManager(table_name=TABLE_NAME)
            state_mgr.add_outbound_reply(
                conversation_id,
                {
                    "message_id": ses_message_id,
                    "from": SENDER_EMAIL,
                    "to": [email_meta["recipient"]],
                    "subject": email_meta["subject"],
                    "body": email_meta["body"],
                    "timestamp": now,
                    "direction": "outbound",
                    "metadata": {
                        "approved_by": body.get("reviewed_by", "admin"),
                        "pending_reply_id": reply_id,
                        "email_type": email_meta.get("phase", "reply"),
                    },
                },
            )
        except Exception as hist_err:
            # Log but don’t fail approval if history append fails
            logger.warning(f"Failed to append outbound email to history: {hist_err}")

        # Update conversation
        table.update_item(
            Key={"conversation_id": conversation_id},
            UpdateExpression="SET pending_replies = :replies, updated_at = :updated",
            ExpressionAttributeValues={":replies": pending_replies, ":updated": now},
        )

        return {
            "statusCode": 200,
            "body": json.dumps({"reply_id": reply_id, "status": "approved", "sent_at": now}),
        }

    except Exception as e:
        logger.error(f"Error approving reply: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to approve reply"})}


def reject_reply(reply_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Reject a pending reply."""
    try:
        conversation_id = body.get("conversation_id")
        if not conversation_id:
            return {"statusCode": 400, "body": json.dumps({"error": "conversation_id is required"})}

        table = dynamodb.Table(TABLE_NAME)

        # Get conversation
        response = table.get_item(Key={"conversation_id": conversation_id})

        if "Item" not in response:
            return {"statusCode": 404, "body": json.dumps({"error": "Conversation not found"})}

        conversation = response["Item"]
        pending_replies = conversation.get("pending_replies", [])

        # Find and update the reply
        reply_found = False
        for i, reply in enumerate(pending_replies):
            if reply.get("reply_id") == reply_id:
                if reply.get("status") != "pending":
                    return {
                        "statusCode": 400,
                        "body": json.dumps({"error": f"Reply is already {reply.get('status')}"}),
                    }

                now = datetime.now(timezone.utc).isoformat()
                pending_replies[i]["status"] = "rejected"
                pending_replies[i]["reviewed_at"] = now
                pending_replies[i]["reviewed_by"] = body.get("reviewed_by", "admin")
                pending_replies[i]["rejection_reason"] = body.get("reason", "")
                reply_found = True
                break

        if not reply_found:
            return {"statusCode": 404, "body": json.dumps({"error": "Reply not found"})}

        # Update conversation
        table.update_item(
            Key={"conversation_id": conversation_id},
            UpdateExpression="SET pending_replies = :replies, updated_at = :updated",
            ExpressionAttributeValues={
                ":replies": pending_replies,
                ":updated": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {"statusCode": 200, "body": json.dumps({"reply_id": reply_id, "status": "rejected"})}

    except Exception as e:
        logger.error(f"Error rejecting reply: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to reject reply"})}


def amend_reply(reply_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Amend a pending reply's content."""
    try:
        conversation_id = body.get("conversation_id")
        amended_content = body.get("content")

        if not conversation_id or not amended_content:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "conversation_id and content are required"}),
            }

        table = dynamodb.Table(TABLE_NAME)

        # Get conversation
        response = table.get_item(Key={"conversation_id": conversation_id})

        if "Item" not in response:
            return {"statusCode": 404, "body": json.dumps({"error": "Conversation not found"})}

        conversation = response["Item"]
        pending_replies = conversation.get("pending_replies", [])

        # Find and update the reply
        reply_found = False
        for i, reply in enumerate(pending_replies):
            if reply.get("reply_id") == reply_id:
                if reply.get("status") != "pending":
                    return {
                        "statusCode": 400,
                        "body": json.dumps({"error": f"Reply is already {reply.get('status')}"}),
                    }

                pending_replies[i]["amended_content"] = amended_content
                pending_replies[i]["amended_at"] = datetime.now(timezone.utc).isoformat()
                pending_replies[i]["amended_by"] = body.get("amended_by", "admin")
                reply_found = True
                break

        if not reply_found:
            return {"statusCode": 404, "body": json.dumps({"error": "Reply not found"})}

        # Update conversation
        table.update_item(
            Key={"conversation_id": conversation_id},
            UpdateExpression="SET pending_replies = :replies, updated_at = :updated",
            ExpressionAttributeValues={
                ":replies": pending_replies,
                ":updated": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {"statusCode": 200, "body": json.dumps({"reply_id": reply_id, "status": "amended"})}

    except Exception as e:
        logger.error(f"Error amending reply: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to amend reply"})}


def get_reply_prompt(reply_id: str) -> Dict[str, Any]:
    """Get the LLM prompt used for a specific reply."""
    try:
        # This would require searching through all conversations
        # For now, return a placeholder
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "reply_id": reply_id,
                    "prompt": "Prompt retrieval not yet implemented",
                    "note": "This will require scanning conversations for the specific reply",
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error getting reply prompt: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to get reply prompt"})}


def get_attachment_url(attachment_id: str) -> Dict[str, Any]:
    """Generate presigned URL for attachment download."""
    try:
        # This would require finding the attachment in conversations
        # and generating a presigned S3 URL
        # For now, return a placeholder
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "attachment_id": attachment_id,
                    "url": "https://example.com/placeholder.pdf",
                    "expires_in": 3600,
                    "note": "Attachment retrieval not yet implemented",
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error getting attachment URL: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to get attachment URL"})}


def _extract_client_email(participants: List[str]) -> str:
    """Extract client email from participants list."""
    for email in participants:
        if "solopilot" not in email.lower() and "abdul" not in email.lower():
            return email
    return "Unknown"


def _convert_decimals(obj: Any) -> Any:
    """Convert DynamoDB Decimals to int/float for JSON serialization."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals(item) for item in obj]
    return obj
