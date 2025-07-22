"""Migration script to update existing DynamoDB conversations table."""

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

from utils import EmailThreadingUtils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DynamoDBMigration:
    """Migrate existing conversations to support multi-turn threading."""

    def __init__(self, table_name: str = "conversations", region: str = None):
        """Initialize migration with DynamoDB table."""
        # Use AWS_DEFAULT_REGION if set, otherwise fallback to provided region or us-east-2
        if region is None:
            region = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")

        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name
        self.region = region
        self.stats = {"total": 0, "migrated": 0, "skipped": 0, "failed": 0}

    def migrate_all_conversations(self, dry_run: bool = True) -> Dict[str, int]:
        """Migrate all conversations in the table.

        Args:
            dry_run: If True, only simulate migration

        Returns:
            Migration statistics
        """
        logger.info(
            f"Starting migration for table: {self.table_name} in region: {self.region} (dry_run={dry_run})"
        )

        # Scan all items
        scan_kwargs = {"ProjectionExpression": "conversation_id, updated_at, email_history"}

        done = False
        start_key = None

        while not done:
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key

            response = self.table.scan(**scan_kwargs)
            items = response.get("Items", [])

            for item in items:
                self.stats["total"] += 1
                self._migrate_conversation(item, dry_run)

            start_key = response.get("LastEvaluatedKey", None)
            done = start_key is None

        logger.info(f"Migration complete: {self.stats}")
        return self.stats

    def _migrate_conversation(self, item: Dict[str, Any], dry_run: bool) -> None:
        """Migrate a single conversation."""
        conversation_id = item["conversation_id"]

        try:
            # Check if already migrated
            if "last_seq" in item and "last_updated_at" in item:
                logger.debug(f"Skipping {conversation_id} - already migrated")
                self.stats["skipped"] += 1
                return

            # Calculate new attributes
            updates = self._calculate_updates(item)

            if dry_run:
                logger.info(f"Would migrate {conversation_id}: {updates}")
                self.stats["migrated"] += 1
                return

            # Apply updates
            self._apply_updates(conversation_id, updates)
            self.stats["migrated"] += 1

        except Exception as e:
            logger.error(f"Failed to migrate {conversation_id}: {str(e)}")
            self.stats["failed"] += 1

    def _calculate_updates(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate required updates for conversation."""
        updates = {}

        # Add sequence number
        updates["last_seq"] = Decimal(len(item.get("email_history", [])))

        # Add last_updated_at (copy from updated_at)
        updates["last_updated_at"] = item.get("updated_at", datetime.now(timezone.utc).isoformat())

        # Add TTL (30 days from last update)
        updates["ttl"] = EmailThreadingUtils.calculate_ttl(days=30)

        # Extract participants from email history
        participants = set()
        thread_refs = []

        for email in item.get("email_history", []):
            if email.get("from"):
                participants.add(email["from"].lower())
            # Add any to/cc addresses if present
            for addr_field in ["to", "cc"]:
                if addr_field in email:
                    addrs = email[addr_field]
                    if isinstance(addrs, str):
                        addrs = [addrs]
                    for addr in addrs:
                        participants.add(addr.lower())

            # Collect message IDs for thread references
            if email.get("message_id"):
                thread_refs.append(EmailThreadingUtils.extract_message_id(email["message_id"]))

        updates["participants"] = participants
        updates["thread_references"] = thread_refs

        # Add requirements version if requirements exist
        if "requirements" in item and "requirements_version" not in item:
            updates["requirements_version"] = Decimal(1)

        return updates

    def _apply_updates(self, conversation_id: str, updates: Dict[str, Any]) -> None:
        """Apply updates to conversation."""
        # Build update expression
        update_parts = []
        attribute_values = {}

        for key, value in updates.items():
            update_parts.append(f"{key} = :{key}")
            attribute_values[f":{key}"] = value

        update_expression = "SET " + ", ".join(update_parts)

        try:
            self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=attribute_values,
                ConditionExpression="attribute_exists(conversation_id)",
            )
            logger.info(f"Migrated conversation: {conversation_id}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(f"Conversation {conversation_id} was deleted during migration")
            else:
                raise

    def create_gsi_if_needed(self, dry_run: bool = True) -> None:
        """Create Global Secondary Indexes if they don't exist.

        Note: This is a placeholder - GSI creation must be done through
        CloudFormation or AWS Console as it requires table update.
        """
        logger.info("Checking for required GSIs...")

        # Get current table description
        response = self.dynamodb.meta.client.describe_table(TableName=self.table_name)
        table_desc = response["Table"]

        existing_gsis = {gsi["IndexName"] for gsi in table_desc.get("GlobalSecondaryIndexes", [])}

        required_gsis = {
            "StatusIndex": {
                "IndexName": "StatusIndex",
                "Keys": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "updated_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            "ParticipantIndex": {
                "IndexName": "ParticipantIndex",
                "Keys": [
                    {"AttributeName": "participant", "KeyType": "HASH"},
                    {"AttributeName": "updated_at", "KeyType": "RANGE"},
                ],
                "Projection": {
                    "ProjectionType": "INCLUDE",
                    "NonKeyAttributes": ["subject", "status", "last_seq"],
                },
            },
        }

        missing_gsis = []
        for gsi_name, gsi_config in required_gsis.items():
            if gsi_name not in existing_gsis:
                missing_gsis.append(gsi_config)

        if missing_gsis:
            logger.warning(f"Missing GSIs: {[g['IndexName'] for g in missing_gsis]}")
            logger.warning("Please create these GSIs through AWS Console or CloudFormation")

            if not dry_run:
                # Print CloudFormation snippet
                print("\nCloudFormation snippet for GSIs:")
                print("GlobalSecondaryIndexes:")
                for gsi in missing_gsis:
                    print(f"  - IndexName: {gsi['IndexName']}")
                    print("    Keys:")
                    for key in gsi["Keys"]:
                        print(f"      - AttributeName: {key['AttributeName']}")
                        print(f"        KeyType: {key['KeyType']}")
                    print("    Projection:")
                    print(f"      ProjectionType: {gsi['Projection']['ProjectionType']}")
                    if "NonKeyAttributes" in gsi["Projection"]:
                        print(f"      NonKeyAttributes: {gsi['Projection']['NonKeyAttributes']}")
                    print("    ProvisionedThroughput:")
                    print("      ReadCapacityUnits: 5")
                    print("      WriteCapacityUnits: 5")
        else:
            logger.info("All required GSIs exist")


def main():
    """Run migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate DynamoDB conversations table")
    parser.add_argument("--table", default="conversations", help="DynamoDB table name")
    parser.add_argument("--region", help="AWS region (defaults to AWS_DEFAULT_REGION or us-east-2)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without changes")
    parser.add_argument("--check-gsi", action="store_true", help="Check for required GSIs")

    args = parser.parse_args()

    migration = DynamoDBMigration(args.table, args.region)

    if args.check_gsi:
        migration.create_gsi_if_needed(args.dry_run)

    stats = migration.migrate_all_conversations(args.dry_run)

    print(f"\nMigration {'simulation' if args.dry_run else 'complete'}:")
    print(f"  Total conversations: {stats['total']}")
    print(f"  Migrated: {stats['migrated']}")
    print(f"  Skipped (already migrated): {stats['skipped']}")
    print(f"  Failed: {stats['failed']}")


if __name__ == "__main__":
    main()
