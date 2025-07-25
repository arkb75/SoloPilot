"""DynamoDB-based version tracking for proposals."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from .models import ProposalListItem, ProposalVersion

logger = logging.getLogger(__name__)


class ProposalVersionIndex:
    """Manages proposal versions in DynamoDB."""

    def __init__(self, table_name: str = "proposal_versions"):
        """Initialize with DynamoDB table.

        Args:
            table_name: Name of the DynamoDB table
        """
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

    def allocate_next_version(self, conversation_id: str) -> int:
        """Atomically allocate the next version number.

        Uses a special item with version=0 to track the current version.

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
            logger.info(f"Allocated version {version} for conversation {conversation_id}")
            return version

        except Exception as e:
            logger.error(f"Error allocating version for {conversation_id}: {str(e)}")
            raise

    def record_version(
        self,
        conversation_id: str,
        version: int,
        s3_key: str,
        file_size: int,
        requirements_hash: str,
        metadata: Dict[str, any],
    ) -> ProposalVersion:
        """Record a new proposal version.

        Args:
            conversation_id: Conversation ID
            version: Version number
            s3_key: S3 key prefix for this version
            file_size: Size of the PDF in bytes
            requirements_hash: Hash of requirements used
            metadata: Additional metadata

        Returns:
            ProposalVersion object
        """
        try:
            now = datetime.now(timezone.utc)

            item = {
                "conversation_id": conversation_id,
                "version": version,
                "s3_key": s3_key,
                "created_at": now.isoformat(),
                "file_size": file_size,
                "requirements_hash": requirements_hash,
                "status": "active",
                "metadata": metadata,
                "ttl": int(now.timestamp()) + (365 * 24 * 60 * 60),  # 1 year TTL
            }

            self.table.put_item(Item=item)

            logger.info(
                f"Recorded version {version} for conversation {conversation_id} "
                f"with s3_key {s3_key}"
            )

            return ProposalVersion(
                conversation_id=conversation_id,
                version=version,
                s3_key=s3_key,
                created_at=now,
                file_size=file_size,
                requirements_hash=requirements_hash,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Error recording version: {str(e)}")
            raise

    def get_version(self, conversation_id: str, version: int) -> Optional[ProposalVersion]:
        """Get a specific proposal version.

        Args:
            conversation_id: Conversation ID
            version: Version number

        Returns:
            ProposalVersion if found, None otherwise
        """
        try:
            response = self.table.get_item(
                Key={"conversation_id": conversation_id, "version": version}
            )

            if "Item" not in response:
                return None

            item = response["Item"]
            return ProposalVersion(
                conversation_id=item["conversation_id"],
                version=int(item["version"]),
                s3_key=item["s3_key"],
                created_at=datetime.fromisoformat(item["created_at"]),
                file_size=int(item["file_size"]),
                requirements_hash=item["requirements_hash"],
                metadata=item.get("metadata", {}),
            )

        except Exception as e:
            logger.error(f"Error getting version {version} for {conversation_id}: {str(e)}")
            return None

    def list_versions(self, conversation_id: str, limit: int = 20) -> List[ProposalListItem]:
        """List all versions for a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Maximum number of versions to return

        Returns:
            List of ProposalListItem objects, newest first
        """
        try:
            response = self.table.query(
                KeyConditionExpression=Key("conversation_id").eq(conversation_id)
                & Key("version").gt(0),  # Skip the version counter item
                ScanIndexForward=False,  # Newest first
                Limit=limit,
            )

            versions = []
            for item in response.get("Items", []):
                metadata = item.get("metadata", {})
                versions.append(
                    ProposalListItem(
                        version=int(item["version"]),
                        created_at=item["created_at"],
                        file_size=int(item["file_size"]),
                        budget=metadata.get("budget"),
                        has_revisions=bool(metadata.get("revised_requirements_used")),
                        s3_key=item["s3_key"],
                    )
                )

            return versions

        except Exception as e:
            logger.error(f"Error listing versions for {conversation_id}: {str(e)}")
            return []

    def get_latest_version(self, conversation_id: str) -> Optional[ProposalVersion]:
        """Get the latest proposal version for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Latest ProposalVersion if any exist, None otherwise
        """
        versions = self.list_versions(conversation_id, limit=1)
        if not versions:
            return None

        # Get the full version details
        return self.get_version(conversation_id, versions[0].version)

    def delete_version(self, conversation_id: str, version: int) -> bool:
        """Soft delete a version by marking it inactive.

        Args:
            conversation_id: Conversation ID
            version: Version number

        Returns:
            True if successful, False otherwise
        """
        try:
            self.table.update_item(
                Key={"conversation_id": conversation_id, "version": version},
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "deleted"},
            )
            logger.info(f"Marked version {version} as deleted for {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting version: {str(e)}")
            return False
