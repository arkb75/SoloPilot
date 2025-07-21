"""Enhanced DynamoDB wrapper with manual approval workflow support."""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from utils import EmailThreadingUtils

logger = logging.getLogger(__name__)


class ConversationStateManager:
    """Thread-safe conversation state management with manual approval workflow."""

    def __init__(self, table_name: str = "conversations"):
        """Initialize with DynamoDB table.

        Args:
            table_name: Name of DynamoDB table
        """
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

    def fetch_or_create_conversation(
        self,
        conversation_id: str,
        original_message_id: str,
        initial_email: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fetch existing conversation or create new one atomically.

        Args:
            conversation_id: Unique conversation identifier
            original_message_id: First email's Message-ID
            initial_email: Initial email data for new conversations

        Returns:
            Conversation state dict
        """
        try:
            # Try to get existing conversation
            response = self.table.get_item(
                Key={"conversation_id": conversation_id}, ConsistentRead=True
            )

            if "Item" in response:
                logger.info(f"Found existing conversation: {conversation_id}")
                return self._deserialize_item(response["Item"])

            # If not found by conversation_id, check if this is a reply to a sent message
            in_reply_to = initial_email.get("in_reply_to", "")
            if in_reply_to:
                # Extract clean message ID
                clean_reply_to = EmailThreadingUtils.extract_message_id(in_reply_to)
                if clean_reply_to:
                    # Check if this message ID is in any conversation's sent_message_ids
                    existing_conv = self.get_conversation_by_sent_message_id(clean_reply_to)
                    if existing_conv:
                        logger.info(f"Found conversation by sent message ID: {existing_conv['conversation_id']}")
                        return existing_conv

            # Create new conversation
            logger.info(f"Creating new conversation: {conversation_id}")
            return self._create_conversation_atomic(
                conversation_id, original_message_id, initial_email
            )

        except Exception as e:
            logger.error(f"Error accessing conversation {conversation_id}: {str(e)}")
            raise

    def _create_conversation_atomic(
        self,
        conversation_id: str,
        original_message_id: str,
        initial_email: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create new conversation with conditional put to prevent duplicates."""
        now = datetime.now(timezone.utc).isoformat()
        ttl = EmailThreadingUtils.calculate_ttl(days=30)

        # Extract participants
        participants = EmailThreadingUtils.extract_participants(initial_email)

        conversation = {
            "conversation_id": conversation_id,
            "created_at": now,
            "updated_at": now,
            "last_updated_at": now,
            "last_seq": Decimal(0),
            "status": "active",  # Legacy field
            "phase": "understanding",  # New phase system
            "phase_history": [],
            "ttl": ttl,
            # Threading info
            "original_message_id": original_message_id,
            "subject": initial_email.get("subject", ""),
            "participants": participants,
            "thread_references": [original_message_id] if original_message_id else [],
            "sent_message_ids": [],  # Track outbound message IDs for thread lookup
            # Content
            "email_history": [],
            "requirements": {},
            "requirements_version": Decimal(0),
            # Phase-specific data
            "understanding_context": {
                "clarified_points": [],
                "open_questions": [],
                "confidence_level": Decimal(0)
            },
            "proposal": {
                "draft": "",
                "feedback": [],
                "version": Decimal(0)
            },
            "final_documentation": "",
            "approval_status": {
                "approved": False,
                "approved_at": None,
                "approved_by": None
            },
            # NEW: Manual approval workflow fields
            "reply_mode": "manual",  # "manual" | "auto" - default to manual
            "pending_replies": [],  # List of pending replies awaiting approval
            "attachments": [],  # List of attachments sent/received
            # Metadata
            "metadata": {"priority": "medium", "tags": [], "client_info": {}},
        }

        try:
            # Conditional put - only if conversation doesn't exist
            self.table.put_item(
                Item=conversation,
                ConditionExpression="attribute_not_exists(conversation_id)",
            )
            return conversation
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Conversation was created by another Lambda - fetch it
                logger.info(
                    f"Conversation {conversation_id} already exists, fetching..."
                )
                response = self.table.get_item(
                    Key={"conversation_id": conversation_id}, ConsistentRead=True
                )
                return self._deserialize_item(response["Item"])
            raise

    def add_pending_reply(
        self,
        conversation_id: str,
        llm_prompt: str,
        llm_response: str,
        phase: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a pending reply to the conversation for approval.

        Args:
            conversation_id: Conversation identifier
            llm_prompt: The full prompt sent to the LLM
            llm_response: The LLM's generated response
            phase: Current conversation phase
            metadata: Additional metadata about the reply

        Returns:
            The reply_id of the pending reply
        """
        try:
            reply_id = str(uuid4())
            now = datetime.now(timezone.utc).isoformat()
            
            pending_reply = {
                "reply_id": reply_id,
                "generated_at": now,
                "llm_prompt": llm_prompt,
                "llm_response": llm_response,
                "status": "pending",  # "pending" | "approved" | "rejected" | "amended"
                "amended_content": None,
                "reviewed_by": None,
                "reviewed_at": None,
                "sent_at": None,
                "message_id": None,
                "phase": phase,
                "metadata": metadata or {}
            }
            
            # Update conversation with new pending reply
            self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="""
                    SET pending_replies = list_append(if_not_exists(pending_replies, :empty), :reply),
                        updated_at = :updated,
                        last_seq = last_seq + :one
                """,
                ExpressionAttributeValues={
                    ":empty": [],
                    ":reply": [pending_reply],
                    ":updated": now,
                    ":one": Decimal(1)
                },
                ReturnValues="NONE"
            )
            
            logger.info(f"Added pending reply {reply_id} to conversation {conversation_id}")
            return reply_id
            
        except Exception as e:
            logger.error(f"Error adding pending reply: {str(e)}")
            raise

    def approve_reply(
        self,
        conversation_id: str,
        reply_id: str,
        reviewed_by: str,
        amended_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve a pending reply for sending.

        Args:
            conversation_id: Conversation identifier
            reply_id: Reply identifier
            reviewed_by: Who approved the reply
            amended_content: Optional amended content (if edited)

        Returns:
            The approved reply data
        """
        try:
            # Get current conversation
            response = self.table.get_item(
                Key={"conversation_id": conversation_id},
                ConsistentRead=True
            )
            
            if "Item" not in response:
                raise ValueError(f"Conversation {conversation_id} not found")
            
            conversation = response["Item"]
            pending_replies = conversation.get("pending_replies", [])
            
            # Find and update the reply
            updated_reply = None
            for i, reply in enumerate(pending_replies):
                if reply.get("reply_id") == reply_id:
                    if reply.get("status") != "pending":
                        raise ValueError(f"Reply {reply_id} is not pending")
                    
                    now = datetime.now(timezone.utc).isoformat()
                    pending_replies[i]["status"] = "approved"
                    pending_replies[i]["reviewed_by"] = reviewed_by
                    pending_replies[i]["reviewed_at"] = now
                    
                    if amended_content:
                        pending_replies[i]["amended_content"] = amended_content
                        pending_replies[i]["amended_at"] = now
                    
                    updated_reply = pending_replies[i]
                    break
            
            if not updated_reply:
                raise ValueError(f"Reply {reply_id} not found")
            
            # Update conversation
            self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="SET pending_replies = :replies, updated_at = :updated",
                ExpressionAttributeValues={
                    ":replies": pending_replies,
                    ":updated": datetime.now(timezone.utc).isoformat()
                }
            )
            
            return updated_reply
            
        except Exception as e:
            logger.error(f"Error approving reply: {str(e)}")
            raise

    def add_attachment(
        self,
        conversation_id: str,
        attachment_type: str,
        s3_key: str,
        filename: str,
        size: int,
        direction: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add an attachment record to the conversation.

        Args:
            conversation_id: Conversation identifier
            attachment_type: Type of attachment (e.g., "proposal_pdf")
            s3_key: S3 key where file is stored
            filename: Original filename
            size: File size in bytes
            direction: "inbound" or "outbound"
            metadata: Additional metadata

        Returns:
            The attachment_id
        """
        try:
            attachment_id = str(uuid4())
            now = datetime.now(timezone.utc).isoformat()
            
            attachment = {
                "attachment_id": attachment_id,
                "type": attachment_type,
                "s3_key": s3_key,
                "filename": filename,
                "size": size,
                "created_at": now,
                "direction": direction,
                "metadata": metadata or {}
            }
            
            # Update conversation
            self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="""
                    SET attachments = list_append(if_not_exists(attachments, :empty), :attachment),
                        updated_at = :updated,
                        last_seq = last_seq + :one
                """,
                ExpressionAttributeValues={
                    ":empty": [],
                    ":attachment": [attachment],
                    ":updated": now,
                    ":one": Decimal(1)
                }
            )
            
            logger.info(f"Added attachment {attachment_id} to conversation {conversation_id}")
            return attachment_id
            
        except Exception as e:
            logger.error(f"Error adding attachment: {str(e)}")
            raise

    def update_reply_mode(self, conversation_id: str, mode: str) -> None:
        """Update conversation reply mode.

        Args:
            conversation_id: Conversation identifier
            mode: "manual" or "auto"
        """
        if mode not in ["manual", "auto"]:
            raise ValueError(f"Invalid reply mode: {mode}")
        
        try:
            self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="SET reply_mode = :mode, updated_at = :updated",
                ExpressionAttributeValues={
                    ":mode": mode,
                    ":updated": datetime.now(timezone.utc).isoformat()
                }
            )
            logger.info(f"Updated reply mode for {conversation_id} to {mode}")
            
        except Exception as e:
            logger.error(f"Error updating reply mode: {str(e)}")
            raise

    def get_pending_replies(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all pending replies for a conversation.

        Args:
            conversation_id: Conversation identifier

        Returns:
            List of pending replies
        """
        try:
            response = self.table.get_item(
                Key={"conversation_id": conversation_id},
                ProjectionExpression="pending_replies"
            )
            
            if "Item" not in response:
                return []
            
            pending_replies = []
            for reply in response["Item"].get("pending_replies", []):
                if reply.get("status") == "pending":
                    pending_replies.append(self._deserialize_item(reply))
            
            return pending_replies
            
        except Exception as e:
            logger.error(f"Error getting pending replies: {str(e)}")
            raise

    # Include all methods from V2 that are still needed
    def append_email_with_retry(
        self, conversation_id: str, email_data: Dict[str, Any], max_retries: int = 1
    ) -> Dict[str, Any]:
        """Append email to conversation with optimistic locking.

        Args:
            conversation_id: Conversation identifier
            email_data: Email data to append
            max_retries: Maximum retry attempts on conflicts

        Returns:
            Updated conversation state
        """
        retries = 0

        while retries <= max_retries:
            try:
                # Get current state with sequence number
                response = self.table.get_item(
                    Key={"conversation_id": conversation_id}, ConsistentRead=True
                )

                if "Item" not in response:
                    raise ValueError(f"Conversation {conversation_id} not found")

                current_state = self._deserialize_item(response["Item"])
                current_seq = int(current_state.get("last_seq", 0))

                # Prepare email entry
                email_entry = self._prepare_email_entry(
                    conversation_id, email_data, current_state
                )

                # Update with optimistic locking
                now = datetime.now(timezone.utc).isoformat()
                new_seq = current_seq + 1

                # Extract new participants
                new_participants = EmailThreadingUtils.extract_participants(email_data)
                all_participants = (
                    set(current_state.get("participants", [])) | new_participants
                )

                # Merge thread references
                new_refs = EmailThreadingUtils.merge_thread_references(
                    current_state.get("thread_references", []),
                    email_data.get("message_id", ""),
                    EmailThreadingUtils.parse_references(
                        email_data.get("references", "")
                    ),
                )

                update_response = self.table.update_item(
                    Key={"conversation_id": conversation_id},
                    UpdateExpression="""
                        SET email_history = list_append(email_history, :email),
                            updated_at = :updated,
                            last_updated_at = :updated,
                            last_seq = :new_seq,
                            participants = :participants,
                            thread_references = :refs,
                            #ttl = :ttl
                    """,
                    ExpressionAttributeNames={
                        "#ttl": "ttl"
                    },
                    ExpressionAttributeValues={
                        ":email": [email_entry],
                        ":updated": now,
                        ":new_seq": Decimal(new_seq),
                        ":current_seq": Decimal(current_seq),
                        ":participants": all_participants,
                        ":refs": new_refs,
                        ":ttl": EmailThreadingUtils.calculate_ttl(days=30),
                    },
                    ConditionExpression="last_seq = :current_seq",
                    ReturnValues="ALL_NEW",
                )

                logger.info(
                    f"Added email to conversation {conversation_id} (seq: {current_seq} -> {new_seq})"
                )
                return self._deserialize_item(update_response["Attributes"])

            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    retries += 1
                    if retries <= max_retries:
                        logger.warning(
                            f"Optimistic lock conflict for {conversation_id}, retry {retries}/{max_retries}"
                        )
                        continue
                    else:
                        logger.error(f"Failed to add email after {max_retries} retries")
                        raise
                raise
            except Exception as e:
                logger.error(f"Error adding email to {conversation_id}: {str(e)}")
                raise

    def _prepare_email_entry(
        self,
        conversation_id: str,
        email_data: Dict[str, Any],
        current_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prepare email entry for storage."""
        # Generate unique email ID
        email_id = EmailThreadingUtils.generate_email_id(
            conversation_id,
            email_data.get("message_id", ""),
            email_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )

        # Extract new content from quoted text
        new_content, quoted_content = EmailThreadingUtils.extract_quoted_text(
            email_data.get("body", "")
        )

        # Check if automated
        is_automated = EmailThreadingUtils.is_automated_response(
            email_data.get("body", ""), email_data.get("subject", "")
        )

        entry = {
            "email_id": email_id,
            "message_id": email_data.get("message_id", ""),
            "in_reply_to": email_data.get("in_reply_to", ""),
            "references": EmailThreadingUtils.parse_references(
                email_data.get("references", "")
            ),
            "from": email_data.get("from", ""),
            "to": email_data.get("to", []),
            "cc": email_data.get("cc", []),
            "subject": email_data.get("subject", ""),
            "body": email_data.get("body", ""),
            "new_content": new_content,
            "timestamp": email_data.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
            "direction": email_data.get("direction", "inbound"),
            "is_automated": is_automated,
            "attachments": email_data.get("attachments", []),
            "metadata": email_data.get("metadata", {}),
        }

        return entry

    def update_requirements_atomic(
        self,
        conversation_id: str,
        requirements: Dict[str, Any],
        expected_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update requirements with version control.

        Args:
            conversation_id: Conversation identifier
            requirements: New requirements
            expected_version: Expected requirements version for optimistic locking

        Returns:
            Updated conversation state
        """
        try:
            # Get current state
            response = self.table.get_item(
                Key={"conversation_id": conversation_id}, ConsistentRead=True
            )

            if "Item" not in response:
                raise ValueError(f"Conversation {conversation_id} not found")

            current_state = self._deserialize_item(response["Item"])
            current_version = int(current_state.get("requirements_version", 0))

            # If expected version provided, validate it
            if expected_version is not None and current_version != expected_version:
                raise ValueError(
                    f"Version mismatch: expected {expected_version}, got {current_version}"
                )

            # Update with new version
            new_version = current_version + 1
            now = datetime.now(timezone.utc).isoformat()

            update_response = self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="""
                    SET requirements = :req,
                        requirements_version = :new_version,
                        updated_at = :updated,
                        last_updated_at = :updated,
                        last_seq = last_seq + :one
                """,
                ExpressionAttributeValues={
                    ":req": requirements,
                    ":new_version": Decimal(new_version),
                    ":updated": now,
                    ":one": Decimal(1),
                    ":current_version": Decimal(current_version),
                },
                ConditionExpression="requirements_version = :current_version",
                ReturnValues="ALL_NEW",
            )

            logger.info(
                f"Updated requirements for {conversation_id} (v{current_version} -> v{new_version})"
            )
            return self._deserialize_item(update_response["Attributes"])

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.error(f"Requirements version conflict for {conversation_id}")
                raise ValueError("Requirements were updated by another process")
            raise
        except Exception as e:
            logger.error(f"Error updating requirements for {conversation_id}: {str(e)}")
            raise

    def update_status(self, conversation_id: str, status: str) -> None:
        """Update conversation status."""
        # Legacy statuses kept for backward compatibility
        valid_statuses = ["active", "pending_info", "completed", "archived"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}")

        try:
            now = datetime.now(timezone.utc).isoformat()
            self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="""
                    SET #status = :status,
                        updated_at = :updated,
                        last_updated_at = :updated,
                        last_seq = last_seq + :one
                """,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": status,
                    ":updated": now,
                    ":one": Decimal(1),
                },
            )
            logger.info(f"Updated status for {conversation_id} to {status}")
        except Exception as e:
            logger.error(f"Error updating status for {conversation_id}: {str(e)}")
            raise
    
    def update_phase(self, conversation_id: str, phase: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Update conversation phase with transition tracking."""
        valid_phases = [
            "understanding",      # Clarifying requirements
            "proposal_draft",     # Presenting proposal
            "proposal_feedback",  # Awaiting feedback
            "documentation",      # Creating detailed plan
            "awaiting_approval",  # Waiting for approval
            "approved",          # Client approved
            "archived"           # Archived
        ]
        
        if phase not in valid_phases:
            raise ValueError(f"Invalid phase: {phase}")
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            # Get current phase for history
            response = self.table.get_item(
                Key={"conversation_id": conversation_id},
                ProjectionExpression="phase,phase_history"
            )
            
            current_phase = response.get("Item", {}).get("phase", "understanding")
            phase_history = response.get("Item", {}).get("phase_history", [])
            
            # Add transition to history
            phase_history.append({
                "from": current_phase,
                "to": phase,
                "timestamp": now,
                "metadata": metadata or {}
            })
            
            # Update phase
            self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="""
                    SET phase = :phase,
                        phase_history = :history,
                        updated_at = :updated,
                        last_updated_at = :updated,
                        last_seq = last_seq + :one
                """,
                ExpressionAttributeValues={
                    ":phase": phase,
                    ":history": phase_history,
                    ":updated": now,
                    ":one": Decimal(1)
                }
            )
            logger.info(f"Updated phase for {conversation_id}: {current_phase} -> {phase}")
            
        except Exception as e:
            logger.error(f"Error updating phase for {conversation_id}: {str(e)}")
            raise

    def add_outbound_reply(
        self, conversation_id: str, reply_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add outbound reply to conversation and track message ID.

        Args:
            conversation_id: Conversation identifier
            reply_data: Outbound email data

        Returns:
            Updated conversation state
        """
        # Mark as outbound
        reply_data["direction"] = "outbound"

        # Add timestamp if not present
        if "timestamp" not in reply_data:
            reply_data["timestamp"] = datetime.now(timezone.utc).isoformat()

        # First append the email
        result = self.append_email_with_retry(conversation_id, reply_data)
        
        # Then update sent_message_ids if we have a message_id
        if reply_data.get("message_id"):
            try:
                # Add the message ID to sent_message_ids for future lookup
                self.table.update_item(
                    Key={"conversation_id": conversation_id},
                    UpdateExpression="SET sent_message_ids = list_append(if_not_exists(sent_message_ids, :empty), :new_id)",
                    ExpressionAttributeValues={
                        ":empty": [],
                        ":new_id": [reply_data["message_id"]]
                    }
                )
                logger.info(f"Added sent message ID {reply_data['message_id']} to conversation {conversation_id}")
            except Exception as e:
                logger.warning(f"Failed to update sent_message_ids: {str(e)}")
        
        return result

    def get_conversation_by_sent_message_id(
        self, message_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find conversation by a sent message ID.
        
        Args:
            message_id: The message ID to search for
            
        Returns:
            Conversation if found, None otherwise
        """
        try:
            # Clean the message ID - remove angle brackets
            clean_id = message_id.strip("<>")
            logger.info(f"Searching for conversation with message ID: {clean_id}")
            
            # We need to scan conversations to find one with this message ID
            # This is not optimal but DynamoDB doesn't support querying on list attributes
            response = self.table.scan(
                FilterExpression="contains(sent_message_ids, :msg_id)",
                ExpressionAttributeValues={
                    ":msg_id": clean_id
                }
            )
            
            if response.get('Items'):
                # Found a conversation
                conversation = self._deserialize_item(response['Items'][0])
                logger.info(f"Found conversation {conversation['conversation_id']} by message ID {clean_id}")
                return conversation
            
            # If not found in sent_message_ids, check email history
            # This is a backup method
            logger.info(f"Message ID not found in sent_message_ids, checking email history")
            response = self.table.scan()
            
            for item in response.get('Items', []):
                for email in item.get('email_history', []):
                    if email.get('direction') == 'outbound' and email.get('message_id'):
                        stored_id = email['message_id'].strip("<>")
                        if stored_id == clean_id:
                            conversation = self._deserialize_item(item)
                            logger.info(f"Found conversation {conversation['conversation_id']} in email history")
                            return conversation
            
            logger.warning(f"No conversation found for message ID: {clean_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding conversation by sent message ID {message_id}: {str(e)}")
            return None
    
    def get_conversations_by_participant(
        self, email_address: str, status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query conversations by participant email.

        Args:
            email_address: Participant email address
            status_filter: Optional status filter

        Returns:
            List of conversations
        """
        try:
            # This would use GSI2 (ParticipantIndex) once created
            # For now, scan with filter
            filter_exp = "contains(participants, :email)"
            exp_values = {":email": email_address.lower()}

            if status_filter:
                filter_exp += " AND #status = :status"
                exp_values[":status"] = status_filter

            response = self.table.scan(
                FilterExpression=filter_exp,
                ExpressionAttributeNames=(
                    {"#status": "status"} if status_filter else None
                ),
                ExpressionAttributeValues=exp_values,
            )

            items = [self._deserialize_item(item) for item in response.get("Items", [])]
            return sorted(items, key=lambda x: x.get("updated_at", ""), reverse=True)

        except Exception as e:
            logger.error(f"Error querying by participant {email_address}: {str(e)}")
            raise

    def _deserialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB item to Python dict with proper types."""
        # Convert Decimal to int/float
        for key, value in item.items():
            if isinstance(value, Decimal):
                if value % 1 == 0:
                    item[key] = int(value)
                else:
                    item[key] = float(value)
            elif isinstance(value, set):
                item[key] = list(value)
        return item
    
    # Message ID mapping methods for stable conversation IDs
    def get_conversation_by_message_id(self, message_id: str) -> Optional[str]:
        """Get conversation ID for a given message ID.
        
        Args:
            message_id: The email Message-ID to lookup
            
        Returns:
            The conversation ID if found, None otherwise
        """
        try:
            logger.info(f"Looking up Message-ID in mapping table: '{message_id}'")
            
            # Initialize message map table
            message_map_table = boto3.resource("dynamodb").Table("email_message_map")
            
            response = message_map_table.get_item(
                Key={"message_id": message_id}
            )
            
            if "Item" in response:
                conv_id = response["Item"].get("conversation_id")
                logger.info(f"✓ Found conversation ID: {conv_id} for Message-ID: {message_id}")
                return conv_id
            else:
                logger.info(f"✗ No mapping found for Message-ID: {message_id}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error looking up message ID {message_id}: {str(e)}")
            return None
    
    def store_message_id_mapping(
        self, message_id: str, conversation_id: str
    ) -> None:
        """Store a mapping from message ID to conversation ID.
        
        Args:
            message_id: The email Message-ID
            conversation_id: The stable conversation ID
        """
        try:
            # Initialize message map table
            message_map_table = boto3.resource("dynamodb").Table("email_message_map")
            
            # Calculate TTL (90 days from now)
            ttl = int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())
            
            # Store mapping with conditional write to avoid overwrites
            message_map_table.put_item(
                Item={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "ttl": ttl
                },
                ConditionExpression="attribute_not_exists(message_id)"
            )
            
            logger.info(f"Stored message ID mapping: {message_id} -> {conversation_id}")
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Mapping already exists, which is fine
                logger.debug(f"Message ID {message_id} already mapped")
            else:
                logger.error(f"Error storing message ID mapping: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Error storing message ID mapping: {str(e)}")
            raise
    
    def lookup_conversation_from_references(
        self, in_reply_to: str, references: List[str]
    ) -> Optional[str]:
        """Look up conversation ID from In-Reply-To or References headers.
        
        Args:
            in_reply_to: The In-Reply-To header value
            references: List of Message-IDs from References header
            
        Returns:
            The conversation ID if found, None otherwise
        """
        # First check In-Reply-To
        if in_reply_to:
            conv_id = self.get_conversation_by_message_id(in_reply_to)
            if conv_id:
                return conv_id
        
        # Then check References in order (oldest first)
        for ref_id in references:
            if ref_id:
                conv_id = self.get_conversation_by_message_id(ref_id)
                if conv_id:
                    return conv_id
        
        return None