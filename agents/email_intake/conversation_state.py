"""DynamoDB wrapper for managing conversation state."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import boto3

logger = logging.getLogger(__name__)


class ConversationStateManager:
    """Manages conversation state in DynamoDB."""

    def __init__(self, table_name: str = "conversations"):
        """Initialize with DynamoDB table.

        Args:
            table_name: Name of DynamoDB table
        """
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

    def get_or_create(self, conversation_id: str) -> Dict[str, Any]:
        """Get existing conversation or create new one.

        Args:
            conversation_id: Unique conversation identifier (email thread ID)

        Returns:
            Conversation state dict
        """
        try:
            response = self.table.get_item(Key={"conversation_id": conversation_id})

            if "Item" in response:
                logger.info(f"Found existing conversation: {conversation_id}")
                return response["Item"]
            else:
                logger.info(f"Creating new conversation: {conversation_id}")
                return self._create_conversation(conversation_id)

        except Exception as e:
            logger.error(f"Error accessing conversation {conversation_id}: {str(e)}")
            raise

    def _create_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Create new conversation entry."""
        conversation = {
            "conversation_id": conversation_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "email_history": [],
            "requirements": {},
            "metadata": {},
        }

        self.table.put_item(Item=conversation)
        return conversation

    def add_email(self, conversation_id: str, email: Dict[str, Any]) -> Dict[str, Any]:
        """Add email to conversation history.

        Args:
            conversation_id: Conversation identifier
            email: Email data (from, subject, body, timestamp)

        Returns:
            Updated conversation state
        """
        try:
            # Add timestamp if not present
            if "timestamp" not in email:
                email["timestamp"] = datetime.now(timezone.utc).isoformat()

            response = self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="SET email_history = list_append(email_history, :email), updated_at = :updated",
                ExpressionAttributeValues={
                    ":email": [email],
                    ":updated": datetime.now(timezone.utc).isoformat(),
                },
                ReturnValues="ALL_NEW",
            )

            logger.info(f"Added email to conversation {conversation_id}")
            return response["Attributes"]

        except Exception as e:
            logger.error(f"Error adding email to {conversation_id}: {str(e)}")
            raise

    def update_requirements(
        self, conversation_id: str, requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update conversation requirements.

        Args:
            conversation_id: Conversation identifier
            requirements: Updated requirements dict

        Returns:
            Updated conversation state
        """
        try:
            response = self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="SET requirements = :req, updated_at = :updated",
                ExpressionAttributeValues={
                    ":req": requirements,
                    ":updated": datetime.now(timezone.utc).isoformat(),
                },
                ReturnValues="ALL_NEW",
            )

            logger.info(f"Updated requirements for {conversation_id}")
            return response["Attributes"]

        except Exception as e:
            logger.error(f"Error updating requirements for {conversation_id}: {str(e)}")
            raise

    def update_status(self, conversation_id: str, status: str) -> None:
        """Update conversation status.

        Args:
            conversation_id: Conversation identifier
            status: New status (active, pending_info, completed)
        """
        try:
            self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="SET #status = :status, updated_at = :updated",
                ExpressionAttributeNames={"#status": "status"},  # status is reserved word
                ExpressionAttributeValues={
                    ":status": status,
                    ":updated": datetime.now(timezone.utc).isoformat(),
                },
            )

            logger.info(f"Updated status for {conversation_id} to {status}")

        except Exception as e:
            logger.error(f"Error updating status for {conversation_id}: {str(e)}")
            raise

    def get_active_conversations(self) -> List[Dict[str, Any]]:
        """Get all active conversations.

        Returns:
            List of active conversation states
        """
        try:
            response = self.table.scan(
                FilterExpression="attribute_exists(#status) AND #status IN (:active, :pending)",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":active": "active", ":pending": "pending_info"},
            )

            return response.get("Items", [])

        except Exception as e:
            logger.error(f"Error getting active conversations: {str(e)}")
            raise
