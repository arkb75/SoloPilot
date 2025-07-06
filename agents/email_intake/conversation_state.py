"""Enhanced DynamoDB wrapper with optimistic locking for thread-safe operations."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from utils import EmailThreadingUtils

logger = logging.getLogger(__name__)


class ConversationStateManagerV2:
    """Thread-safe conversation state management with optimistic locking."""

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
            "status": "active",
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
            # Handle both formats: raw SES ID and full email format
            # SES IDs look like: 010f0197dd099476-4a695c7d-3c72-4774-a453-7c9c47a1fdc0-000000
            # Full format: <010f0197dd099476-4a695c7d-3c72-4774-a453-7c9c47a1fdc0-000000@us-east-2.amazonses.com>
            search_ids = [message_id]
            
            # If it's a full email format, also search for just the ID part
            if "@" in message_id:
                id_part = message_id.split("@")[0]
                search_ids.append(id_part)
            
            # If it's just an ID, also search for the full format with common SES domains
            elif "-" in message_id and len(message_id) > 30:
                search_ids.extend([
                    f"{message_id}@us-east-2.amazonses.com",
                    f"{message_id}@email.amazonses.com",
                    f"{message_id}@amazonses.com"
                ])
            
            logger.info(f"Searching for conversation with sent message IDs: {search_ids}")
            
            # Scan for conversations containing any of these sent message IDs
            for search_id in search_ids:
                response = self.table.scan(
                    FilterExpression="contains(sent_message_ids, :msg_id)",
                    ExpressionAttributeValues={
                        ":msg_id": search_id
                    }
                )
                
                items = response.get("Items", [])
                if items:
                    # Found a conversation with this message ID
                    logger.info(f"Found conversation by sent message ID: {search_id}")
                    return self._deserialize_item(items[0])
            
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
