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

# Custom JSON encoder for Decimal types from DynamoDB
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            else:
                return float(obj)
        return super(DecimalEncoder, self).default(obj)

from conversation_state import (  # Needed to append sent email to history
    ConversationStateManager,
)
from email_sender import (
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
# Unified bucket: prefer DOCUMENT_BUCKET; keep legacy fallback for now
S3_BUCKET = os.environ.get("DOCUMENT_BUCKET") or os.environ.get("ATTACHMENTS_BUCKET", "solopilot-attachments")
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
        query_params = event.get("queryStringParameters", {}) or {}
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

        # Prefer routing by resource (stage-agnostic). Fallback to path if resource missing.
        resource = event.get("resource", "")

        def route_by_resource(res: str) -> Dict[str, Any]:
            if res == "/conversations" and http_method == "GET":
                return list_conversations(query_params)
            if res == "/conversations/{id}/mode" and http_method == "PATCH":
                return update_conversation_mode(path_params.get("id"), body)
            if res == "/conversations/{id}/pending-replies" and http_method == "GET":
                return get_pending_replies(path_params.get("id"))
            if res == "/conversations/{id}" and http_method == "GET":
                return get_conversation_detail(path_params.get("id"))
            if res == "/conversations/{id}" and http_method == "DELETE":
                return delete_conversation(path_params.get("id"))
            if res == "/replies/{id}/approve" and http_method == "POST":
                return approve_reply(path_params.get("id"), body)
            if res == "/replies/{id}/reject" and http_method == "POST":
                return reject_reply(path_params.get("id"), body)
            if res == "/replies/{id}/prompt" and http_method == "GET":
                return get_reply_prompt(path_params.get("id"))
            if res == "/replies/{id}/review" and http_method == "GET":
                return get_reply_review(path_params.get("id"))
            if res == "/replies/{id}/request-revision" and http_method == "POST":
                return request_reply_revision(path_params.get("id"))
            if res == "/replies/{id}" and http_method == "PATCH":
                return amend_reply(path_params.get("id"), body)
            if res == "/attachments/{id}" and http_method == "GET":
                return get_attachment_url(path_params.get("id"))
            if res == "/conversations/{id}/proposals" and http_method == "GET":
                return list_proposals(path_params.get("id"))
            if res == "/conversations/{id}/proposals/{version}" and http_method == "GET":
                conv_id = path_params.get("id")
                version = path_params.get("version") or ""
                return get_proposal_url(conv_id, version)
            return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}

        if resource:
            response = route_by_resource(resource)
        else:
            # Fallback: attempt to strip stage from path and match
            stage = (event.get("requestContext") or {}).get("stage")
            normalized_path = path or ""
            if stage and normalized_path.startswith(f"/{stage}/"):
                normalized_path = normalized_path[len(stage) + 1 :]
            elif stage and normalized_path == f"/{stage}":
                normalized_path = "/"

            # Minimal fallback for proposals routes
            if normalized_path == "/conversations" and http_method == "GET":
                response = list_conversations(query_params)
            elif normalized_path.endswith("/proposals") and http_method == "GET":
                parts = [s for s in normalized_path.split("/") if s]
                if "conversations" in parts:
                    idx = parts.index("conversations")
                    conversation_id = parts[idx + 1] if idx + 1 < len(parts) else None
                    if conversation_id:
                        response = list_proposals(conversation_id)
                    else:
                        response = {"statusCode": 400, "body": json.dumps({"error": "Invalid path format"})}
                else:
                    response = {"statusCode": 404, "body": json.dumps({"error": "Not found"})}
            elif "/proposals/" in normalized_path and http_method == "GET":
                parts = [s for s in normalized_path.split("/") if s]
                if "conversations" in parts and "proposals" in parts:
                    ci = parts.index("conversations")
                    pi = parts.index("proposals")
                    conversation_id = parts[ci + 1] if ci + 1 < len(parts) else None
                    version = parts[pi + 1] if pi + 1 < len(parts) else None
                    if conversation_id and version:
                        response = get_proposal_url(conversation_id, version)
                    else:
                        response = {"statusCode": 400, "body": json.dumps({"error": "Invalid path format"})}
                else:
                    response = {"statusCode": 404, "body": json.dumps({"error": "Not found"})}
            else:
                response = {"statusCode": 404, "body": json.dumps({"error": "Not found"})}

        # Add CORS headers
        if "statusCode" in response:
            response["headers"] = {
                "Access-Control-Allow-Origin": CORS_ORIGIN,
                "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
                "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS",
            }

        return response

    except Exception as e:
        logger.error(f"Error handling request: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": CORS_ORIGIN,
                "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
                "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS",
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

        # Build scan parameters - include metadata fields
        scan_params = {
            "Limit": limit,
            "ProjectionExpression": "conversation_id, subject, participants, phase, reply_mode, created_at, updated_at, client_name, project_name, project_type, latest_metadata, metadata_updated_at",
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
                    # Include metadata fields
                    "client_name": item.get("client_name"),
                    "project_name": item.get("project_name"),
                    "project_type": item.get("project_type"),
                    "latest_metadata": _convert_decimals(item.get("latest_metadata")) if item.get("latest_metadata") else None,
                    "metadata_updated_at": item.get("metadata_updated_at"),
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
        
        # These fields are already in the conversation from DynamoDB, just ensure they're included
        # The _convert_decimals above already handles the latest_metadata field if it exists

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
        
        # IMPORTANT: Use the current conversation phase, not the stale one from pending reply
        # The phase may have been updated after the reply was queued
        current_phase = conversation.get("phase", "unknown")
        email_meta["phase"] = current_phase
        
        # Log the extracted metadata
        logger.info(f"[APPROVE_REPLY] Extracted metadata - should_send_pdf={email_meta.get('should_send_pdf')}, phase={current_phase}")
        logger.info(f"[APPROVE_REPLY] Email body preview: {email_meta.get('body', '')[:100]}...")

        # Store timestamp for later use
        now = datetime.now(timezone.utc).isoformat()

        # Initialize storage_info for all emails (will be populated for PDFs)
        storage_info = None

        # Check if we should send a PDF proposal
        if email_meta.get("should_send_pdf") and email_meta.get("phase") in ["proposal_draft", "proposal_feedback"]:
            # Prefer reusing a pre-generated proposal stored during pending-creation
            pregen_version = (
                (reply_data or {}).get("proposal_version")
                or (reply_data or {}).get("metadata", {}).get("proposal_version")
            )
            pregen_pdf_bytes = None
            storage_info = None

            if pregen_version:
                try:
                    from src.storage import S3ProposalStore  # type: ignore
                    s3_store = S3ProposalStore(
                        bucket_name=os.environ.get("DOCUMENT_BUCKET")
                        or os.environ.get("ATTACHMENTS_BUCKET", "solopilot-attachments")
                    )
                    pregen_pdf_bytes = s3_store.get_proposal_pdf(conversation_id, int(pregen_version))
                    if pregen_pdf_bytes:
                        storage_info = {"version": int(pregen_version)}
                        logger.info(
                            f"Using pre-generated proposal v{pregen_version} for conversation {conversation_id}"
                        )
                except Exception as fetch_e:
                    logger.warning(
                        f"Failed to fetch pre-generated proposal v{pregen_version}: {str(fetch_e)}"
                    )

            if pregen_pdf_bytes is None:
                # Fall back to generating now
                try:
                    from pdf_generator import ProposalPDFGenerator

                    pdf_lambda_arn = os.environ.get("PDF_LAMBDA_ARN", "")
                    if not pdf_lambda_arn:
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
                    pdf_generator = ProposalPDFGenerator(pdf_lambda_arn)
                    pregen_pdf_bytes, pdf_error, storage_info = (
                        pdf_generator.generate_and_store_proposal_pdf(conversation)
                    )
                    if not pregen_pdf_bytes:
                        error_details = {
                            "error": "PDF generation failed",
                            "error_type": "PdfGenerationError",
                            "conversation_id": conversation_id,
                            "client_email": email_meta["recipient"],
                            "pdf_error": pdf_error,
                        }
                        logger.error(f"PDF_GENERATION_FAILED: {json.dumps(error_details)}")
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
                    error_details = {
                        "error": "PDF generation exception",
                        "error_type": "PdfGenerationException",
                        "conversation_id": conversation_id,
                        "client_email": email_meta["recipient"],
                        "exception": str(pdf_e),
                    }
                    logger.error(
                        f"PDF_GENERATION_FAILED: {json.dumps(error_details)}", exc_info=True
                    )
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

            # Prepare email body
            requirements = conversation.get("requirements", {})
            client_name = requirements.get("client_name", "Client")
            project_title = requirements.get("title", "Your Project")
            email_body_to_send = email_meta.get("body", "")
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
                pdf_content=pregen_pdf_bytes,
                pdf_filename=f"{client_name.replace(' ', '_')}_proposal.pdf",
                in_reply_to=email_meta.get("in_reply_to"),
                references=email_meta.get("references", []),
            )
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

        # Store S3 storage info if available
        if storage_info and storage_info.get("version") is not None:
            pending_replies[reply_index]["proposal_version"] = storage_info.get("version")
            if storage_info.get("s3_key"):
                pending_replies[reply_index]["s3_key"] = storage_info.get("s3_key")
            logger.info(
                f"Stored proposal version {storage_info.get('version')} info in pending reply"
            )
        else:
            # If we reused a pre-generated version, persist that version number
            pregen_version_to_keep = (
                (reply_data or {}).get("proposal_version")
                or (reply_data or {}).get("metadata", {}).get("proposal_version")
            )
            if pregen_version_to_keep:
                pending_replies[reply_index]["proposal_version"] = int(pregen_version_to_keep)
                logger.info(
                    f"Kept pre-generated proposal version {pregen_version_to_keep} on pending reply"
                )

        # Store message ID mapping for proper threading
        # SES uses the MessageId as the actual Message-ID in format: <MessageId@us-east-2.amazonses.com>
        if ses_message_id:
            try:
                # Import canonicalization function
                try:
                    # For Lambda runtime (when imported as api.lambda_api)
                    from utils import EmailThreadingUtils
                except ImportError:
                    # For local development/testing
                    from ..utils import EmailThreadingUtils

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

                # Ensure metadata exists
                if "metadata" not in pending_replies[i]:
                    pending_replies[i]["metadata"] = {}
                
                # Store original email_body for audit trail (only if not already stored)
                if "original_email_body" not in pending_replies[i]["metadata"]:
                    original_body = pending_replies[i]["metadata"].get("email_body", "")
                    if original_body:  # Only store if there's an original
                        pending_replies[i]["metadata"]["original_email_body"] = original_body

                # Update the email_body in metadata directly - this becomes the source of truth
                pending_replies[i]["metadata"]["email_body"] = amended_content
                
                # Track amendment details for audit trail
                pending_replies[i]["amended_at"] = datetime.now(timezone.utc).isoformat()
                pending_replies[i]["amended_by"] = body.get("amended_by", "admin")
                
                # Log the amendment for debugging
                logger.info(f"Amended reply {reply_id}: updated metadata.email_body with {len(amended_content)} characters")
                
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


def get_reply_review(reply_id: str) -> Dict[str, Any]:
    """Get or generate AI review for a specific reply."""
    try:
        # Get reviewer toggle from environment
        reviewer_enabled = os.environ.get("ENABLE_REVIEWER", "true").lower() == "true"
        
        if not reviewer_enabled:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "reply_id": reply_id,
                    "review": {
                        "relevance_score": 5,
                        "completeness_score": 5,
                        "accuracy_score": 5,
                        "next_steps_score": 5,
                        "overall_score": 5,
                        "red_flags": [],
                        "summary": "AI review is disabled",
                        "reviewed_at": datetime.now(timezone.utc).isoformat()
                    },
                    "cached": False
                }, cls=DecimalEncoder)
            }
        
        # Search for the reply across all conversations
        table = dynamodb.Table(TABLE_NAME)
        
        # Scan for conversations that might contain this reply
        response = table.scan(
            FilterExpression="attribute_exists(pending_replies)",
            ProjectionExpression="conversation_id, pending_replies, email_history, phase, client_email"
        )
        
        reply_data = None
        conversation_data = None
        
        for item in response['Items']:
            pending_replies = item.get('pending_replies', [])
            for reply in pending_replies:
                if reply.get('reply_id') == reply_id:
                    reply_data = reply
                    conversation_data = item
                    break
            if reply_data:
                break
        
        if not reply_data:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Reply not found"})
            }
        
        # Check if review is already cached (and not null)
        if 'review' in reply_data and reply_data['review'] is not None:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "reply_id": reply_id,
                    "review": reply_data['review'],
                    "cached": True
                }, cls=DecimalEncoder)
            }
        
        # Generate new review
        from reviewer import EmailReviewer
        
        reviewer = EmailReviewer()
        response_text = reply_data.get('llm_response', '')
        metadata = reply_data.get('metadata', {})
        
        review = reviewer.review_response(conversation_data, response_text, metadata)
        
        # Cache the review in DynamoDB
        try:
            # Update the specific reply with review data
            conversation_id = conversation_data['conversation_id']
            pending_replies = conversation_data.get('pending_replies', [])
            
            # Find and update the specific reply
            for i, reply in enumerate(pending_replies):
                if reply.get('reply_id') == reply_id:
                    pending_replies[i]['review'] = review
                    break
            
            # Update the conversation with the new review
            table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="SET pending_replies = :pr",
                ExpressionAttributeValues={":pr": pending_replies}
            )
            
            logger.info(f"Cached review for reply {reply_id} with overall score: {review.get('overall_score', 0)}")
            
        except Exception as e:
            logger.warning(f"Failed to cache review for reply {reply_id}: {str(e)}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "reply_id": reply_id,
                "review": review,
                "cached": False
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error getting reply review: {str(e)}", exc_info=True)
        return {
            "statusCode": 500, 
            "body": json.dumps({
                "error": "Failed to get reply review",
                "details": str(e)
            })
        }

def request_reply_revision(reply_id: str) -> Dict[str, Any]:
    """Request AI revision for a specific reply based on its review feedback."""
    try:
        # Get reviewer toggle from environment
        revision_enabled = os.environ.get("ENABLE_REVISION", "true").lower() == "true"
        
        if not revision_enabled:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Revision feature is disabled",
                    "details": "Set ENABLE_REVISION=true to enable"
                })
            }
        
        # Search for the reply across all conversations
        table = dynamodb.Table(TABLE_NAME)
        
        # Scan for conversations that might contain this reply
        response = table.scan(
            FilterExpression="attribute_exists(pending_replies)",
            ProjectionExpression="conversation_id, pending_replies, email_history, phase, client_email"
        )
        
        reply_data = None
        conversation_data = None
        
        for item in response['Items']:
            pending_replies = item.get('pending_replies', [])
            for reply in pending_replies:
                if reply.get('reply_id') == reply_id:
                    reply_data = reply
                    conversation_data = item
                    break
            if reply_data:
                break
        
        if not reply_data:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Reply not found"})
            }
        
        # Check if reply already has a revision
        if 'revision' in reply_data and reply_data['revision']:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "reply_id": reply_id,
                    "revision": reply_data['revision'],
                    "cached": True
                }, cls=DecimalEncoder)
            }
        
        # Get or generate review first
        review = reply_data.get('review')
        if not review:
            # Generate review first
            from reviewer import EmailReviewer
            reviewer = EmailReviewer()
            response_text = reply_data.get('llm_response', '')
            metadata = reply_data.get('metadata', {})
            review = reviewer.review_response(conversation_data, response_text, metadata)
        
        # Generate feedback from review
        from reviewer import EmailReviewer
        from response_reviser import ResponseReviser
        
        reviewer = EmailReviewer()
        reviser = ResponseReviser()
        
        original_response = reply_data.get('llm_response', '')
        
        # Generate feedback prompt
        feedback = reviewer.generate_feedback_prompt(review, original_response, conversation_data)
        
        # Request revision
        revision_result = reviser.revise_with_retry(
            original_response, 
            feedback, 
            conversation_data,
            max_attempts=2
        )
        
        # If revision was successful, review the revised response
        revised_review = None
        if revision_result.get("revision_successful", False):
            try:
                revised_response = revision_result["revised_response"]
                metadata = reply_data.get('metadata', {})
                revised_review = reviewer.review_response(conversation_data, revised_response, metadata)
                revision_result["revised_review"] = revised_review
                
                logger.info(f"Revised response scored {revised_review.get('overall_score', 0)} vs original {review.get('overall_score', 0)}")
                
            except Exception as e:
                logger.warning(f"Failed to review revised response: {str(e)}")
                # Continue without revised review
        
        # Cache the revision in DynamoDB
        try:
            conversation_id = conversation_data['conversation_id']
            pending_replies = conversation_data.get('pending_replies', [])
            
            # Find and update the specific reply
            for i, reply in enumerate(pending_replies):
                if reply.get('reply_id') == reply_id:
                    pending_replies[i]['revision'] = revision_result
                    # Also ensure review is cached
                    if not pending_replies[i].get('review'):
                        pending_replies[i]['review'] = review
                    break
            
            # Update the conversation with the revision
            table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="SET pending_replies = :pr",
                ExpressionAttributeValues={":pr": pending_replies}
            )
            
            logger.info(f"Cached revision for reply {reply_id}. Successful: {revision_result.get('revision_successful', False)}")
            
        except Exception as e:
            logger.warning(f"Failed to cache revision for reply {reply_id}: {str(e)}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "reply_id": reply_id,
                "revision": revision_result,
                "original_review": review,
                "cached": False
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        logger.error(f"Error requesting reply revision: {str(e)}", exc_info=True)
        return {
            "statusCode": 500, 
            "body": json.dumps({
                "error": "Failed to request reply revision",
                "details": str(e)
            })
        }


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


def list_proposals(conversation_id: str) -> Dict[str, Any]:
    """List all proposal versions for a conversation.

    Args:
        conversation_id: Conversation ID

    Returns:
        API response with list of proposals
    """
    try:
        # Canonical import path for Lambda package layout
        from src.storage import ProposalVersionIndex  # type: ignore

        version_index = ProposalVersionIndex()
        proposals = version_index.list_versions(conversation_id)

        # Convert to API response format
        proposal_list = []
        for proposal in proposals:
            proposal_list.append(
                {
                    "version": proposal.version,
                    "created_at": proposal.created_at,
                    "file_size": proposal.file_size,
                    "budget": proposal.budget,
                    "has_revisions": proposal.has_revisions,
                }
            )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "conversation_id": conversation_id,
                    "proposals": proposal_list,
                    "count": len(proposal_list),
                }
            ),
        }

    except ImportError:
        logger.warning("Storage module not available")
        return {
            "statusCode": 501,
            "body": json.dumps({"error": "Proposal storage not implemented"}),
        }
    except Exception as e:
        logger.error(f"Error listing proposals: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to list proposals"})}


def get_proposal_url(conversation_id: str, version: str) -> Dict[str, Any]:
    """Get presigned URL for a specific proposal version.

    Args:
        conversation_id: Conversation ID
        version: Version number as string

    Returns:
        API response with presigned URL
    """
    try:
        # Validate version is a number
        try:
            version_num = int(version)
        except ValueError:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid version number"}),
            }

        # Canonical import path for Lambda package layout
        from src.storage import S3ProposalStore  # type: ignore

        s3_store = S3ProposalStore(
            bucket_name=os.environ.get("DOCUMENT_BUCKET")
            or os.environ.get("ATTACHMENTS_BUCKET", "solopilot-attachments")
        )

        # Generate presigned URL
        url = s3_store.generate_presigned_url(conversation_id, version_num)

        if not url:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Proposal not found"}),
            }

        # Get metadata if available
        metadata = s3_store.get_proposal_metadata(conversation_id, version_num)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "conversation_id": conversation_id,
                    "version": version_num,
                    "url": url,
                    "expires_in": 3600,
                    "metadata": metadata,
                }
            ),
        }

    except ImportError:
        logger.warning("Storage module not available")
        return {
            "statusCode": 501,
            "body": json.dumps({"error": "Proposal storage not implemented"}),
        }
    except Exception as e:
        logger.error(f"Error getting proposal URL: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to get proposal URL"})}

def delete_conversation(conversation_id: str) -> Dict[str, Any]:
    """Delete a conversation and all its related data."""
    try:
        if not conversation_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "conversation_id is required"}),
            }

        # Get the table
        table = dynamodb.Table(TABLE_NAME)
        
        # Delete the conversation from DynamoDB
        response = table.delete_item(
            Key={"conversation_id": conversation_id},
            ReturnValues="ALL_OLD"
        )

        # Check if the item existed
        if "Attributes" not in response:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Conversation not found"}),
            }

        logger.info(f"Deleted conversation {conversation_id}")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Conversation deleted successfully"}),
        }

    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to delete conversation"}),
        }
