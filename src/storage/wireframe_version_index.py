"""DynamoDB-based version tracking for wireframes."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)


class WireframeVersion:
    """Represents a wireframe version."""

    def __init__(
        self,
        conversation_id: str,
        version: int,
        s3_key: str,
        created_at: datetime,
        screen_count: int,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.conversation_id = conversation_id
        self.version = version
        self.s3_key = s3_key
        self.created_at = created_at
        self.screen_count = screen_count
        self.metadata = metadata or {}


class WireframeListItem:
    """Lightweight wireframe version for listing."""

    def __init__(
        self,
        version: int,
        created_at: str,
        screen_count: int,
        s3_key: str,
    ):
        self.version = version
        self.created_at = created_at
        self.screen_count = screen_count
        self.s3_key = s3_key


class WireframeVersionIndex:
    """Manages wireframe versions in DynamoDB."""

    def __init__(self, table_name: str = "wireframe_versions"):
        """Initialize with DynamoDB table.

        Args:
            table_name: Name of the DynamoDB table
        """
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

    def allocate_next_version(self, conversation_id: str) -> int:
        """Atomically allocate the next version number.

        Args:
            conversation_id: Conversation ID

        Returns:
            The allocated version number
        """
        try:
            response = self.table.update_item(
                Key={"conversation_id": conversation_id, "version": 0},
                UpdateExpression="ADD current_version :inc",
                ExpressionAttributeValues={":inc": Decimal(1)},
                ReturnValues="UPDATED_NEW",
            )
            version = int(response["Attributes"]["current_version"])
            logger.info(f"Allocated wireframe version {version} for {conversation_id}")
            return version

        except Exception as e:
            logger.error(f"Error allocating wireframe version: {str(e)}")
            raise

    def record_version(
        self,
        conversation_id: str,
        version: int,
        s3_key: str,
        screen_count: int,
        metadata: Dict[str, Any],
    ) -> WireframeVersion:
        """Record a new wireframe version.

        Args:
            conversation_id: Conversation ID
            version: Version number
            s3_key: S3 key prefix for this version
            screen_count: Number of screens
            metadata: Additional metadata

        Returns:
            WireframeVersion object
        """
        try:
            now = datetime.now(timezone.utc)

            item = {
                "conversation_id": conversation_id,
                "version": version,
                "s3_key": s3_key,
                "created_at": now.isoformat(),
                "screen_count": screen_count,
                "status": "active",
                "metadata": metadata,
                "ttl": int(now.timestamp()) + (365 * 24 * 60 * 60),  # 1 year TTL
            }

            self.table.put_item(Item=item)

            logger.info(f"Recorded wireframe version {version} for {conversation_id}")

            return WireframeVersion(
                conversation_id=conversation_id,
                version=version,
                s3_key=s3_key,
                created_at=now,
                screen_count=screen_count,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Error recording wireframe version: {str(e)}")
            raise

    def get_version(self, conversation_id: str, version: int) -> Optional[WireframeVersion]:
        """Get a specific wireframe version.

        Args:
            conversation_id: Conversation ID
            version: Version number

        Returns:
            WireframeVersion if found, None otherwise
        """
        try:
            response = self.table.get_item(
                Key={"conversation_id": conversation_id, "version": version}
            )

            if "Item" not in response:
                return None

            item = response["Item"]
            return WireframeVersion(
                conversation_id=item["conversation_id"],
                version=int(item["version"]),
                s3_key=item["s3_key"],
                created_at=datetime.fromisoformat(item["created_at"]),
                screen_count=int(item["screen_count"]),
                metadata=item.get("metadata", {}),
            )

        except Exception as e:
            logger.error(f"Error getting wireframe version: {str(e)}")
            return None

    def list_versions(self, conversation_id: str, limit: int = 20) -> List[WireframeListItem]:
        """List all wireframe versions for a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Maximum number of versions to return

        Returns:
            List of WireframeListItem objects, newest first
        """
        try:
            response = self.table.query(
                KeyConditionExpression=Key("conversation_id").eq(conversation_id)
                & Key("version").gt(0),
                ScanIndexForward=False,
                Limit=limit,
            )

            versions = []
            for item in response.get("Items", []):
                versions.append(
                    WireframeListItem(
                        version=int(item["version"]),
                        created_at=item["created_at"],
                        screen_count=int(item.get("screen_count", 0)),
                        s3_key=item["s3_key"],
                    )
                )

            return versions

        except Exception as e:
            logger.error(f"Error listing wireframe versions: {str(e)}")
            return []

    def get_latest_version(self, conversation_id: str) -> Optional[WireframeVersion]:
        """Get the latest wireframe version.

        Args:
            conversation_id: Conversation ID

        Returns:
            Latest WireframeVersion if any exist, None otherwise
        """
        versions = self.list_versions(conversation_id, limit=1)
        if not versions:
            return None
        return self.get_version(conversation_id, versions[0].version)
