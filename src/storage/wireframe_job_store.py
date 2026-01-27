"""DynamoDB-based job tracking for async wireframe generation."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)


class WireframeJob:
    """Represents a wireframe generation job."""

    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    def __init__(
        self,
        job_id: str,
        conversation_id: str,
        status: str,
        created_at: datetime,
        completed_at: Optional[datetime] = None,
        version: Optional[int] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.job_id = job_id
        self.conversation_id = conversation_id
        self.status = status
        self.created_at = created_at
        self.completed_at = completed_at
        self.version = version
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "job_id": self.job_id,
            "conversation_id": self.conversation_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "version": self.version,
            "error": self.error,
        }


class WireframeJobStore:
    """Manages wireframe generation jobs in DynamoDB."""

    def __init__(self, table_name: str = "wireframe_jobs"):
        """Initialize with DynamoDB table.

        Args:
            table_name: Name of the DynamoDB table
        """
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

    def create_job(self, conversation_id: str) -> WireframeJob:
        """Create a new pending generation job.

        Args:
            conversation_id: Conversation ID

        Returns:
            WireframeJob object
        """
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        item = {
            "job_id": job_id,
            "conversation_id": conversation_id,
            "status": WireframeJob.STATUS_PENDING,
            "created_at": now.isoformat(),
            "ttl": int(now.timestamp()) + (24 * 60 * 60),  # 24 hour TTL
        }

        try:
            self.table.put_item(Item=item)
            logger.info(f"Created wireframe job {job_id} for {conversation_id}")

            return WireframeJob(
                job_id=job_id,
                conversation_id=conversation_id,
                status=WireframeJob.STATUS_PENDING,
                created_at=now,
            )
        except Exception as e:
            logger.error(f"Error creating wireframe job: {str(e)}")
            raise

    def get_job(self, job_id: str) -> Optional[WireframeJob]:
        """Get a job by ID.

        Args:
            job_id: Job ID

        Returns:
            WireframeJob if found, None otherwise
        """
        try:
            response = self.table.get_item(Key={"job_id": job_id})

            if "Item" not in response:
                return None

            item = response["Item"]
            return WireframeJob(
                job_id=item["job_id"],
                conversation_id=item["conversation_id"],
                status=item["status"],
                created_at=datetime.fromisoformat(item["created_at"]),
                completed_at=datetime.fromisoformat(item["completed_at"])
                if item.get("completed_at")
                else None,
                version=int(item["version"]) if item.get("version") else None,
                error=item.get("error"),
                metadata=item.get("metadata", {}),
            )
        except Exception as e:
            logger.error(f"Error getting wireframe job: {str(e)}")
            return None

    def update_status(
        self,
        job_id: str,
        status: str,
        version: Optional[int] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update job status.

        Args:
            job_id: Job ID
            status: New status
            version: Wireframe version (for completed status)
            error: Error message (for failed status)

        Returns:
            True if successful
        """
        try:
            update_expr = "SET #status = :status"
            expr_values: Dict[str, Any] = {":status": status}
            expr_names = {"#status": "status"}

            if status in [WireframeJob.STATUS_COMPLETED, WireframeJob.STATUS_FAILED]:
                update_expr += ", completed_at = :completed_at"
                expr_values[":completed_at"] = datetime.now(timezone.utc).isoformat()

            if version is not None:
                update_expr += ", version = :version"
                expr_values[":version"] = version

            if error is not None:
                update_expr += ", #error = :error"
                expr_values[":error"] = error
                expr_names["#error"] = "error"

            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames=expr_names,
            )

            logger.info(f"Updated wireframe job {job_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating wireframe job status: {str(e)}")
            return False

    def get_active_job(self, conversation_id: str) -> Optional[WireframeJob]:
        """Get the most recent pending/in-progress job for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            WireframeJob if found, None otherwise
        """
        try:
            # Query using GSI on conversation_id
            response = self.table.query(
                IndexName="conversation_id-index",
                KeyConditionExpression=Key("conversation_id").eq(conversation_id),
                ScanIndexForward=False,  # Newest first
                Limit=5,
            )

            for item in response.get("Items", []):
                if item["status"] in [
                    WireframeJob.STATUS_PENDING,
                    WireframeJob.STATUS_IN_PROGRESS,
                ]:
                    return WireframeJob(
                        job_id=item["job_id"],
                        conversation_id=item["conversation_id"],
                        status=item["status"],
                        created_at=datetime.fromisoformat(item["created_at"]),
                    )

            return None
        except Exception as e:
            logger.error(f"Error getting active wireframe job: {str(e)}")
            return None
