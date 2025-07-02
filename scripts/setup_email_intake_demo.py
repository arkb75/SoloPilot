#!/usr/bin/env python3
"""Setup script for email intake Lambda demo with proper region configuration.

This script:
- Sets AWS_DEFAULT_REGION=us-east-2 for all operations
- Creates conversations table if missing
- Sets up TTL on the table
- Uploads Lambda package
- Updates Lambda configuration
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Force us-east-2 region
os.environ["AWS_DEFAULT_REGION"] = "us-east-2"
AWS_REGION = "us-east-2"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EmailIntakeSetup:
    """Sets up email intake Lambda and dependencies."""
    
    def __init__(self):
        """Initialize AWS clients with explicit region."""
        logger.info(f"Initializing setup with region: {AWS_REGION}")
        
        # Create clients with explicit region
        self.dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        self.dynamodb_client = boto3.client("dynamodb", region_name=AWS_REGION)
        self.lambda_client = boto3.client("lambda", region_name=AWS_REGION)
        self.sqs_client = boto3.client("sqs", region_name=AWS_REGION)
        self.ses_client = boto3.client("ses", region_name=AWS_REGION)
        
        # Configuration
        self.table_name = "conversations"
        self.lambda_name = "email-intake-lambda"
        self.sender_email = "intake@solopilot.abdulkhurram.com"
        
    def setup_dynamodb_table(self) -> bool:
        """Create conversations table if it doesn't exist."""
        logger.info(f"Checking DynamoDB table: {self.table_name}")
        
        try:
            # Check if table exists
            table = self.dynamodb.Table(self.table_name)
            table.load()
            logger.info(f"✅ Table '{self.table_name}' already exists")
            
            # Check and enable TTL
            self._setup_ttl()
            return True
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.info(f"Table '{self.table_name}' not found. Creating...")
                return self._create_table()
            elif e.response["Error"]["Code"] == "AccessDeniedException":
                logger.error(f"❌ Access denied to DynamoDB")
                logger.info("   Required permissions: dynamodb:DescribeTable, dynamodb:CreateTable")
                logger.info("   Please ensure your AWS user has DynamoDB permissions")
                return False
            else:
                logger.error(f"Error checking table: {str(e)}")
                return False
    
    def _create_table(self) -> bool:
        """Create the conversations table with proper schema."""
        try:
            # Create table
            table = self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {"AttributeName": "conversation_id", "KeyType": "HASH"}
                ],
                AttributeDefinitions=[
                    {"AttributeName": "conversation_id", "AttributeType": "S"}
                ],
                BillingMode="PAY_PER_REQUEST",
                Tags=[
                    {"Key": "Project", "Value": "SoloPilot"},
                    {"Key": "Component", "Value": "EmailIntake"},
                    {"Key": "Environment", "Value": "Demo"}
                ]
            )
            
            logger.info("⏳ Waiting for table creation...")
            table.meta.client.get_waiter("table_exists").wait(
                TableName=self.table_name,
                WaiterConfig={"Delay": 2, "MaxAttempts": 30}
            )
            
            logger.info(f"✅ Table '{self.table_name}' created successfully")
            
            # Enable TTL after table is active
            time.sleep(5)  # Brief delay to ensure table is ready
            self._setup_ttl()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create table: {str(e)}")
            return False
    
    def _setup_ttl(self) -> None:
        """Enable TTL on the 'ttl' attribute."""
        try:
            # Check current TTL status
            response = self.dynamodb_client.describe_time_to_live(
                TableName=self.table_name
            )
            
            ttl_status = response["TimeToLiveDescription"]["TimeToLiveStatus"]
            
            if ttl_status == "ENABLED":
                logger.info("✅ TTL is already enabled on 'ttl' attribute")
                return
            
            # Enable TTL
            logger.info("Enabling TTL on 'ttl' attribute...")
            self.dynamodb_client.update_time_to_live(
                TableName=self.table_name,
                TimeToLiveSpecification={
                    "Enabled": True,
                    "AttributeName": "ttl"
                }
            )
            
            logger.info("✅ TTL enabled successfully (may take a few minutes to activate)")
            
        except Exception as e:
            logger.warning(f"⚠️  Could not setup TTL: {str(e)}")
    
    def get_sqs_queue_url(self) -> Optional[str]:
        """Get or create the requirement processing queue."""
        queue_name = "solopilot-requirements-queue"
        
        try:
            # Try to get existing queue
            response = self.sqs_client.get_queue_url(QueueName=queue_name)
            queue_url = response["QueueUrl"]
            logger.info(f"✅ Found existing SQS queue: {queue_name}")
            return queue_url
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "AWS.SimpleQueueService.NonExistentQueue":
                # Create queue
                logger.info(f"Creating SQS queue: {queue_name}")
                response = self.sqs_client.create_queue(
                    QueueName=queue_name,
                    Attributes={
                        "MessageRetentionPeriod": "1209600",  # 14 days
                        "VisibilityTimeout": "300",  # 5 minutes
                    },
                    tags={
                        "Project": "SoloPilot",
                        "Component": "EmailIntake",
                        "Environment": "Demo"
                    }
                )
                queue_url = response["QueueUrl"]
                logger.info(f"✅ Created SQS queue: {queue_url}")
                return queue_url
            else:
                logger.error(f"Error accessing SQS: {str(e)}")
                return None
    
    def check_ses_configuration(self) -> bool:
        """Verify SES is configured for the sender email."""
        try:
            # Check if email is verified
            response = self.ses_client.get_identity_verification_attributes(
                Identities=[self.sender_email]
            )
            
            verification_attrs = response.get("VerificationAttributes", {})
            
            if self.sender_email in verification_attrs:
                status = verification_attrs[self.sender_email].get("VerificationStatus")
                if status == "Success":
                    logger.info(f"✅ SES email verified: {self.sender_email}")
                    return True
                else:
                    logger.warning(f"⚠️  SES email verification status: {status}")
            else:
                logger.warning(f"⚠️  Email {self.sender_email} is not verified in SES")
                logger.info("   Run: aws ses verify-email-identity --email-address " + self.sender_email)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking SES: {str(e)}")
            return False
    
    def update_lambda_configuration(self, queue_url: str) -> bool:
        """Update Lambda function configuration."""
        try:
            # Check if Lambda exists
            try:
                response = self.lambda_client.get_function(
                    FunctionName=self.lambda_name
                )
                logger.info(f"✅ Found Lambda function: {self.lambda_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    logger.error(f"❌ Lambda function '{self.lambda_name}' not found")
                    logger.info("   Please create the Lambda function first")
                    return False
                raise
            
            # Update configuration
            logger.info("Updating Lambda configuration...")
            
            config_updates = {
                "FunctionName": self.lambda_name,
                "Handler": "lambda_function_v2.lambda_handler",
                "Environment": {
                    "Variables": {
                        "SENDER_EMAIL": self.sender_email,
                        "REQUIREMENT_QUEUE_URL": queue_url,
                        "DYNAMO_TABLE": self.table_name,
                        "ENABLE_OUTBOUND_TRACKING": "true"
                    }
                }
            }
            
            self.lambda_client.update_function_configuration(**config_updates)
            
            logger.info("✅ Lambda configuration updated")
            
            # Wait for update to complete
            waiter = self.lambda_client.get_waiter("function_updated")
            waiter.wait(
                FunctionName=self.lambda_name,
                WaiterConfig={"Delay": 2, "MaxAttempts": 30}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating Lambda: {str(e)}")
            return False
    
    def upload_lambda_package(self) -> bool:
        """Upload the Lambda deployment package."""
        package_path = Path(__file__).parent.parent / "agents" / "email_intake" / "email_intake.zip"
        
        if not package_path.exists():
            logger.warning(f"⚠️  Lambda package not found at: {package_path}")
            logger.info("   Run: cd agents/email_intake && make package")
            return False
        
        try:
            logger.info(f"Uploading Lambda package: {package_path}")
            
            with open(package_path, "rb") as f:
                zip_data = f.read()
            
            self.lambda_client.update_function_code(
                FunctionName=self.lambda_name,
                ZipFile=zip_data
            )
            
            # Wait for update
            waiter = self.lambda_client.get_waiter("function_updated")
            waiter.wait(
                FunctionName=self.lambda_name,
                WaiterConfig={"Delay": 2, "MaxAttempts": 30}
            )
            
            logger.info("✅ Lambda code uploaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading Lambda code: {str(e)}")
            return False
    
    def print_summary(self, queue_url: Optional[str]) -> None:
        """Print setup summary."""
        print("\n" + "="*60)
        print("📧 Email Intake Setup Summary")
        print("="*60)
        print(f"Region: {AWS_REGION}")
        print(f"DynamoDB Table: {self.table_name}")
        print(f"Lambda Function: {self.lambda_name}")
        print(f"SQS Queue URL: {queue_url or 'Not configured'}")
        print(f"Sender Email: {self.sender_email}")
        print("="*60)
        
        print("\n📝 Next Steps:")
        print("1. Ensure SES is configured to receive emails")
        print("2. Set up SES rule to trigger Lambda on incoming emails")
        print("3. Run test_email_flow.py to test the setup")
        print("4. Check CloudWatch logs for Lambda execution details")
    
    def print_permissions_summary(self) -> None:
        """Print required AWS permissions."""
        print("\n" + "="*60)
        print("🔑 Required AWS Permissions")
        print("="*60)
        print("DynamoDB:")
        print("  - dynamodb:DescribeTable")
        print("  - dynamodb:CreateTable")
        print("  - dynamodb:UpdateTimeToLive")
        print("  - dynamodb:DescribeTimeToLive")
        print("\nSQS:")
        print("  - sqs:GetQueueUrl")
        print("  - sqs:CreateQueue")
        print("\nSES:")
        print("  - ses:GetIdentityVerificationAttributes")
        print("  - ses:SendEmail")
        print("\nLambda:")
        print("  - lambda:GetFunction")
        print("  - lambda:UpdateFunctionConfiguration")
        print("  - lambda:UpdateFunctionCode")
        print("="*60)
    
    def run(self) -> bool:
        """Run the complete setup process."""
        logger.info("🚀 Starting Email Intake Setup")
        logger.info(f"   AWS Region: {AWS_REGION}")
        
        # Step 1: Setup DynamoDB
        if not self.setup_dynamodb_table():
            self.print_permissions_summary()
            return False
        
        # Step 2: Get/Create SQS Queue
        queue_url = self.get_sqs_queue_url()
        if not queue_url:
            return False
        
        # Step 3: Check SES
        self.check_ses_configuration()
        
        # Step 4: Update Lambda Configuration
        if not self.update_lambda_configuration(queue_url):
            return False
        
        # Step 5: Upload Lambda Package
        if not self.upload_lambda_package():
            logger.warning("⚠️  Skipping Lambda code upload")
        
        # Print summary
        self.print_summary(queue_url)
        
        logger.info("\n✅ Setup completed successfully!")
        return True


def main():
    """Main entry point."""
    # Verify AWS credentials
    try:
        sts = boto3.client("sts", region_name=AWS_REGION)
        identity = sts.get_caller_identity()
        logger.info(f"AWS Account: {identity['Account']}")
        logger.info(f"AWS User: {identity['Arn']}")
    except Exception as e:
        logger.error(f"❌ AWS credentials not configured: {str(e)}")
        sys.exit(1)
    
    # Run setup
    setup = EmailIntakeSetup()
    success = setup.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()