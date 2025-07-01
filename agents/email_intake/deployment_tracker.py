"""Track client deployments in DynamoDB."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DeploymentTracker:
    """Manages client deployment records in DynamoDB."""

    def __init__(self, table_name: str = "client_deployments"):
        """Initialize with DynamoDB table.

        Args:
            table_name: Name of DynamoDB table for deployments
        """
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

    def create_deployment_record(
        self,
        client_id: str,
        client_name: str,
        project_type: str = "site",
        vercel_project_id: Optional[str] = None,
        github_repo_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new deployment record for a client.

        Args:
            client_id: Unique client identifier (from conversation_id)
            client_name: Client business name
            project_type: Type of project (site, app, api)
            vercel_project_id: Vercel project ID
            github_repo_url: GitHub repository URL

        Returns:
            Created deployment record
        """
        now = datetime.now(timezone.utc).isoformat()

        deployment = {
            "client_id": client_id,
            "client_name": client_name,
            "project_type": project_type,
            "vercel_project_id": vercel_project_id,
            "github_repo_url": github_repo_url,
            "deployment_urls": [],
            "created_at": now,
            "last_deployed_at": None,
            "status": "initialized",
            "deployment_count": Decimal(0),
            "metadata": {"source": "email_intake", "environment": "production"},
        }

        try:
            # Use conditional put to prevent duplicates
            self.table.put_item(
                Item=deployment, ConditionExpression="attribute_not_exists(client_id)"
            )
            logger.info(f"Created deployment record for client: {client_id}")
            return deployment

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Record already exists, return it
                logger.info(f"Deployment record already exists for: {client_id}")
                return self.get_deployment(client_id)
            raise

    def get_deployment(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get deployment record by client ID.

        Args:
            client_id: Client identifier

        Returns:
            Deployment record or None
        """
        try:
            response = self.table.get_item(
                Key={"client_id": client_id}, ConsistentRead=True
            )

            if "Item" in response:
                return self._deserialize_item(response["Item"])
            return None

        except Exception as e:
            logger.error(f"Error getting deployment for {client_id}: {str(e)}")
            return None

    def update_vercel_project(
        self, client_id: str, vercel_project_id: str, project_name: str
    ) -> Dict[str, Any]:
        """Update Vercel project information.

        Args:
            client_id: Client identifier
            vercel_project_id: Vercel project ID
            project_name: Vercel project name

        Returns:
            Updated deployment record
        """
        try:
            response = self.table.update_item(
                Key={"client_id": client_id},
                UpdateExpression="""
                    SET vercel_project_id = :project_id,
                        #metadata.vercel_project_name = :project_name,
                        #metadata.vercel_updated_at = :timestamp
                """,
                ExpressionAttributeNames={"#metadata": "metadata"},
                ExpressionAttributeValues={
                    ":project_id": vercel_project_id,
                    ":project_name": project_name,
                    ":timestamp": datetime.now(timezone.utc).isoformat(),
                },
                ReturnValues="ALL_NEW",
            )

            logger.info(
                f"Updated Vercel project for client {client_id}: {vercel_project_id}"
            )
            return self._deserialize_item(response["Attributes"])

        except Exception as e:
            logger.error(f"Error updating Vercel project: {str(e)}")
            raise

    def update_github_repo(
        self, client_id: str, github_repo_url: str, repo_name: str
    ) -> Dict[str, Any]:
        """Update GitHub repository information.

        Args:
            client_id: Client identifier
            github_repo_url: GitHub repository URL
            repo_name: Repository name

        Returns:
            Updated deployment record
        """
        try:
            response = self.table.update_item(
                Key={"client_id": client_id},
                UpdateExpression="""
                    SET github_repo_url = :repo_url,
                        #metadata.github_repo_name = :repo_name,
                        #metadata.github_updated_at = :timestamp
                """,
                ExpressionAttributeNames={"#metadata": "metadata"},
                ExpressionAttributeValues={
                    ":repo_url": github_repo_url,
                    ":repo_name": repo_name,
                    ":timestamp": datetime.now(timezone.utc).isoformat(),
                },
                ReturnValues="ALL_NEW",
            )

            logger.info(
                f"Updated GitHub repo for client {client_id}: {github_repo_url}"
            )
            return self._deserialize_item(response["Attributes"])

        except Exception as e:
            logger.error(f"Error updating GitHub repo: {str(e)}")
            raise

    def add_deployment_url(
        self,
        client_id: str,
        deployment_url: str,
        deployment_id: str,
        environment: str = "production",
    ) -> Dict[str, Any]:
        """Add a new deployment URL to the record.

        Args:
            client_id: Client identifier
            deployment_url: Vercel deployment URL
            deployment_id: Vercel deployment ID
            environment: Deployment environment

        Returns:
            Updated deployment record
        """
        now = datetime.now(timezone.utc).isoformat()

        deployment_entry = {
            "url": deployment_url,
            "deployment_id": deployment_id,
            "environment": environment,
            "deployed_at": now,
            "status": "active",
        }

        try:
            response = self.table.update_item(
                Key={"client_id": client_id},
                UpdateExpression="""
                    SET deployment_urls = list_append(deployment_urls, :url),
                        last_deployed_at = :timestamp,
                        deployment_count = deployment_count + :one,
                        #status = :status
                """,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":url": [deployment_entry],
                    ":timestamp": now,
                    ":one": Decimal(1),
                    ":status": "deployed",
                },
                ReturnValues="ALL_NEW",
            )

            logger.info(
                f"Added deployment URL for client {client_id}: {deployment_url}"
            )
            return self._deserialize_item(response["Attributes"])

        except Exception as e:
            logger.error(f"Error adding deployment URL: {str(e)}")
            raise

    def update_deployment_status(
        self, client_id: str, status: str, error_message: Optional[str] = None
    ) -> None:
        """Update deployment status.

        Args:
            client_id: Client identifier
            status: New status (initialized, deploying, deployed, failed)
            error_message: Optional error message for failed deployments
        """
        try:
            update_expr = "SET #status = :status"
            expr_names = {"#status": "status"}
            expr_values = {":status": status}

            if error_message and status == "failed":
                update_expr += ", #metadata.last_error = :error"
                expr_names["#metadata"] = "metadata"
                expr_values[":error"] = error_message

            self.table.update_item(
                Key={"client_id": client_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )

            logger.info(f"Updated deployment status for {client_id} to {status}")

        except Exception as e:
            logger.error(f"Error updating deployment status: {str(e)}")
            raise

    def list_client_deployments(
        self, status_filter: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List all client deployments.

        Args:
            status_filter: Optional status to filter by
            limit: Maximum number of results

        Returns:
            List of deployment records
        """
        try:
            scan_kwargs = {"Limit": limit}

            if status_filter:
                scan_kwargs["FilterExpression"] = "#status = :status"
                scan_kwargs["ExpressionAttributeNames"] = {"#status": "status"}
                scan_kwargs["ExpressionAttributeValues"] = {":status": status_filter}

            response = self.table.scan(**scan_kwargs)

            items = [self._deserialize_item(item) for item in response.get("Items", [])]

            # Sort by last deployment date
            items.sort(
                key=lambda x: x.get("last_deployed_at", x.get("created_at", "")),
                reverse=True,
            )

            return items

        except Exception as e:
            logger.error(f"Error listing deployments: {str(e)}")
            return []

    def get_deployment_by_vercel_project(
        self, vercel_project_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find deployment by Vercel project ID.

        Args:
            vercel_project_id: Vercel project ID

        Returns:
            Deployment record or None
        """
        try:
            response = self.table.scan(
                FilterExpression="vercel_project_id = :project_id",
                ExpressionAttributeValues={":project_id": vercel_project_id},
            )

            items = response.get("Items", [])
            if items:
                return self._deserialize_item(items[0])
            return None

        except Exception as e:
            logger.error(f"Error finding deployment by Vercel project: {str(e)}")
            return None

    def _deserialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB item to Python dict with proper types."""
        for key, value in item.items():
            if isinstance(value, Decimal):
                if value % 1 == 0:
                    item[key] = int(value)
                else:
                    item[key] = float(value)
        return item
