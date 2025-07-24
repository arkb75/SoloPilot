#!/usr/bin/env python3
"""
Create email_message_map DynamoDB table for stable conversation IDs.

This table maps email Message-IDs to conversation IDs, allowing us to maintain
stable conversation IDs across email threads.
"""

import sys
from datetime import datetime

import boto3


def create_message_map_table(region="us-east-2"):
    """Create the email_message_map DynamoDB table."""
    dynamodb = boto3.resource("dynamodb", region_name=region)

    table_name = "email_message_map"

    try:
        # Check if table already exists
        existing_tables = [table.name for table in dynamodb.tables.all()]
        if table_name in existing_tables:
            print(f"Table {table_name} already exists")
            return dynamodb.Table(table_name)

        # Create table
        print(f"Creating table {table_name}...")
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "message_id", "KeyType": "HASH"}],  # Partition key
            AttributeDefinitions=[{"AttributeName": "message_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",  # On-demand pricing
            Tags=[
                {"Key": "Project", "Value": "SoloPilot"},
                {"Key": "Component", "Value": "EmailIntake"},
                {"Key": "Environment", "Value": "Production"},
            ],
        )

        # Wait for table to be created
        print("Waiting for table to be created...")
        table.wait_until_exists()

        print(f"Table {table_name} created successfully!")
        print(f"Table ARN: {table.table_arn}")

        # Enable TTL on the table
        client = boto3.client("dynamodb", region_name=region)
        try:
            client.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
            )
            print("TTL enabled on 'ttl' attribute")
        except Exception as e:
            print(f"Warning: Could not enable TTL: {str(e)}")

        return table

    except Exception as e:
        print(f"Error creating table: {str(e)}")
        sys.exit(1)


def test_table_operations(table_name="email_message_map", region="us-east-2"):
    """Test basic operations on the message map table."""
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    # Test item
    test_message_id = "test-message-123@example.com"
    test_conversation_id = "conv-test-123"

    try:
        # Put item
        print("\nTesting put_item...")
        response = table.put_item(
            Item={
                "message_id": test_message_id,
                "conversation_id": test_conversation_id,
                "created_at": datetime.utcnow().isoformat(),
                "ttl": int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60),  # 90 days
            }
        )
        print("Put item successful")

        # Get item
        print("\nTesting get_item...")
        response = table.get_item(Key={"message_id": test_message_id})
        if "Item" in response:
            print(f"Retrieved item: {response['Item']}")

        # Delete test item
        print("\nCleaning up test item...")
        table.delete_item(Key={"message_id": test_message_id})
        print("Test item deleted")

        print("\nTable operations test completed successfully!")

    except Exception as e:
        print(f"Error during table operations test: {str(e)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create email_message_map DynamoDB table")
    parser.add_argument("--region", default="us-east-2", help="AWS region")
    parser.add_argument("--test", action="store_true", help="Run table operations test")

    args = parser.parse_args()

    # Create table
    table = create_message_map_table(args.region)

    # Run test if requested
    if args.test:
        test_table_operations(region=args.region)
