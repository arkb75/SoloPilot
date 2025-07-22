#!/usr/bin/env python3
"""Test script for email intake flow - sends test email and monitors DynamoDB.

This script:
- Sends a test email via SES
- Polls DynamoDB to show conversation creation
- Displays conversation details for manual testing
"""

import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Force us-east-2 region
os.environ["AWS_DEFAULT_REGION"] = "us-east-2"
AWS_REGION = "us-east-2"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class EmailFlowTester:
    """Tests the email intake flow end-to-end."""

    def __init__(self):
        """Initialize AWS clients with explicit region."""
        logger.info(f"Initializing tester with region: {AWS_REGION}")

        # Create clients with explicit region
        self.ses_client = boto3.client("ses", region_name=AWS_REGION)
        self.dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        self.table = self.dynamodb.Table("conversations")

        # Configuration
        self.sender_email = "intake@solopilot.abdulkhurram.com"
        self.test_recipient = None  # Will be set based on verified emails

    def get_verified_email(self) -> Optional[str]:
        """Get a verified email address for testing."""
        try:
            response = self.ses_client.list_verified_email_addresses()
            verified_emails = response.get("VerifiedEmailAddresses", [])

            if not verified_emails:
                logger.error("❌ No verified email addresses found in SES")
                logger.info("   Run: aws ses verify-email-identity --email-address YOUR_EMAIL")
                return None

            # Use the first verified email
            email = verified_emails[0]
            logger.info(f"✅ Using verified email: {email}")
            return email

        except Exception as e:
            logger.error(f"Error getting verified emails: {str(e)}")
            return None

    def send_test_email(self, subject: str, body: str) -> Optional[str]:
        """Send a test email via SES."""
        if not self.test_recipient:
            logger.error("No test recipient configured")
            return None

        try:
            # Generate unique message ID for tracking
            message_id = f"test-{uuid.uuid4().hex[:8]}"

            response = self.ses_client.send_email(
                Source=self.test_recipient,
                Destination={"ToAddresses": [self.sender_email]},
                Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": body}}},
                Tags=[
                    {"Name": "test_id", "Value": message_id},
                    {"Name": "test_type", "Value": "email_intake_flow"},
                ],
            )

            ses_message_id = response["MessageId"]
            logger.info("✅ Email sent successfully")
            logger.info(f"   SES Message ID: {ses_message_id}")
            logger.info(f"   Test ID: {message_id}")

            return ses_message_id

        except ClientError as e:
            if e.response["Error"]["Code"] == "MessageRejected":
                logger.error("❌ Email rejected by SES")
                logger.info("   Check if you're in sandbox mode and emails are verified")
            else:
                logger.error(f"Error sending email: {str(e)}")
            return None

    def poll_dynamodb(self, max_wait: int = 60, poll_interval: int = 5) -> Optional[Dict[str, Any]]:
        """Poll DynamoDB for new conversations."""
        logger.info(f"⏳ Polling DynamoDB for new conversations (max {max_wait}s)...")

        start_time = time.time()
        initial_conversations = self._get_recent_conversations()
        initial_ids = {c["conversation_id"] for c in initial_conversations}

        while time.time() - start_time < max_wait:
            current_conversations = self._get_recent_conversations()

            # Check for new conversations
            for conv in current_conversations:
                if conv["conversation_id"] not in initial_ids:
                    logger.info(f"✅ New conversation detected: {conv['conversation_id']}")
                    return conv

            # Show progress
            elapsed = int(time.time() - start_time)
            logger.info(f"   Waiting... ({elapsed}s/{max_wait}s)")
            time.sleep(poll_interval)

        logger.warning("⚠️  No new conversation detected within timeout")
        return None

    def _get_recent_conversations(self) -> list:
        """Get recent conversations from DynamoDB."""
        try:
            # Scan with limit (in production, use GSI with timestamp)
            response = self.table.scan(
                Limit=10,
                ProjectionExpression="conversation_id, created_at, updated_at, #s, subject",
                ExpressionAttributeNames={"#s": "status"},
            )

            items = response.get("Items", [])

            # Sort by created_at descending
            items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            return items

        except Exception as e:
            logger.error(f"Error scanning DynamoDB: {str(e)}")
            return []

    def display_conversation_details(self, conversation_id: str) -> None:
        """Display detailed conversation information."""
        try:
            response = self.table.get_item(Key={"conversation_id": conversation_id})

            if "Item" not in response:
                logger.error(f"Conversation {conversation_id} not found")
                return

            conv = response["Item"]

            print("\n" + "=" * 60)
            print("📧 Conversation Details")
            print("=" * 60)
            print(f"ID: {conversation_id}")
            print(f"Status: {conv.get('status', 'N/A')}")
            print(f"Subject: {conv.get('subject', 'N/A')}")
            print(f"Created: {conv.get('created_at', 'N/A')}")
            print(f"Updated: {conv.get('updated_at', 'N/A')}")
            print(f"Email Count: {len(conv.get('email_history', []))}")
            print(f"TTL: {conv.get('ttl', 'Not set')}")

            # Show participants
            participants = conv.get("participants", [])
            if participants:
                print("\nParticipants:")
                for p in participants:
                    print(f"  - {p}")

            # Show requirements if any
            requirements = conv.get("requirements", {})
            if requirements:
                print("\nExtracted Requirements:")
                print(f"  Title: {requirements.get('title', 'N/A')}")
                print(f"  Type: {requirements.get('project_type', 'N/A')}")
                print(f"  Timeline: {requirements.get('timeline', 'N/A')}")
                print(f"  Budget: {requirements.get('budget', 'N/A')}")

                features = requirements.get("features", [])
                if features:
                    print("  Features:")
                    for f in features[:3]:  # Show first 3
                        print(f"    - {f.get('name', 'N/A')}")

            print("=" * 60)

        except Exception as e:
            logger.error(f"Error getting conversation details: {str(e)}")

    def run_test_scenario(self, scenario: str = "basic") -> None:
        """Run a specific test scenario."""
        scenarios = {
            "basic": {
                "subject": "Need a website for my bakery",
                "body": """Hi,

I need a website for my bakery business. We want to showcase our products 
and allow customers to place orders online.

Budget is around $5000 and we need it done in 2 months.

Thanks,
Test Customer""",
            },
            "incomplete": {
                "subject": "Website project",
                "body": "I need a website built. Can you help?",
            },
            "detailed": {
                "subject": "E-commerce Platform Development",
                "body": """Hello,

I'm looking for a development team to build a custom e-commerce platform for 
my artisan jewelry business.

Requirements:
- Product catalog with categories
- Shopping cart and checkout
- Payment integration (Stripe)
- Order management system
- Customer accounts
- Mobile responsive design

Timeline: 3-4 months
Budget: $15,000-20,000

Please let me know if you need any additional information.

Best regards,
Jane Smith
Artisan Jewels LLC""",
            },
        }

        if scenario not in scenarios:
            logger.error(f"Unknown scenario: {scenario}")
            return

        test_data = scenarios[scenario]
        logger.info(f"🧪 Running test scenario: {scenario}")

        # Send test email
        message_id = self.send_test_email(test_data["subject"], test_data["body"])

        if not message_id:
            return

        # Wait a bit for SES to process
        logger.info("⏳ Waiting 5s for SES processing...")
        time.sleep(5)

        # Poll for conversation
        conversation = self.poll_dynamodb()

        if conversation:
            self.display_conversation_details(conversation["conversation_id"])

            print("\n✅ Test completed successfully!")
            print(f"   Conversation ID: {conversation['conversation_id']}")
            print("   Use this ID to test further interactions")
        else:
            print("\n❌ Test failed - no conversation created")
            print("   Check Lambda logs in CloudWatch for details")

    def list_recent_conversations(self) -> None:
        """List recent conversations for debugging."""
        conversations = self._get_recent_conversations()

        if not conversations:
            print("\n📭 No conversations found in DynamoDB")
            return

        print("\n" + "=" * 60)
        print("📋 Recent Conversations")
        print("=" * 60)

        for conv in conversations[:5]:  # Show last 5
            print(f"\nID: {conv.get('conversation_id', 'N/A')}")
            print(f"  Status: {conv.get('status', 'N/A')}")
            print(f"  Subject: {conv.get('subject', 'N/A')[:50]}...")
            print(f"  Created: {conv.get('created_at', 'N/A')}")

        print("=" * 60)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Test email intake flow")
    parser.add_argument(
        "--scenario",
        choices=["basic", "incomplete", "detailed"],
        default="basic",
        help="Test scenario to run",
    )
    parser.add_argument("--list", action="store_true", help="List recent conversations")
    parser.add_argument("--details", help="Show details for a specific conversation ID")

    args = parser.parse_args()

    # Verify AWS credentials
    try:
        sts = boto3.client("sts", region_name=AWS_REGION)
        identity = sts.get_caller_identity()
        logger.info(f"AWS Account: {identity['Account']}")
        logger.info(f"AWS User: {identity['Arn']}")
    except Exception as e:
        logger.error(f"❌ AWS credentials not configured: {str(e)}")
        sys.exit(1)

    # Initialize tester
    tester = EmailFlowTester()

    # Handle different commands
    if args.list:
        tester.list_recent_conversations()
    elif args.details:
        tester.display_conversation_details(args.details)
    else:
        # Get verified email for testing
        tester.test_recipient = tester.get_verified_email()
        if not tester.test_recipient:
            sys.exit(1)

        # Run test scenario
        tester.run_test_scenario(args.scenario)


if __name__ == "__main__":
    main()
