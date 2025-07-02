#!/usr/bin/env python3
"""Add temporary IAM permissions for SoloPilot email intake demo.

This script creates an inline policy for the user 'abdul' with the minimum
permissions needed to run the email intake demo.

Usage:
    python add_demo_iam_permissions.py          # Add permissions
    python add_demo_iam_permissions.py --remove # Remove permissions
"""

import argparse
import json
import logging
import sys
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Policy configuration
USER_NAME = "abdul"
POLICY_NAME = "SoloPilotDemoPolicy-Temporary"
AWS_REGION = "us-east-2"


def get_demo_policy() -> Dict[str, Any]:
    """Get the IAM policy document for demo permissions."""
    # Get current account ID
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DynamoDBConversationsTable",
                "Effect": "Allow",
                "Action": [
                    # Table management
                    "dynamodb:CreateTable",
                    "dynamodb:DescribeTable",
                    "dynamodb:ListTables",
                    "dynamodb:UpdateTimeToLive",
                    "dynamodb:DescribeTimeToLive",
                    # CRUD operations
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    # Batch operations
                    "dynamodb:BatchGetItem",
                    "dynamodb:BatchWriteItem",
                    # Tag management
                    "dynamodb:TagResource",
                    "dynamodb:ListTagsOfResource"
                ],
                "Resource": [
                    f"arn:aws:dynamodb:{AWS_REGION}:{account_id}:table/conversations",
                    f"arn:aws:dynamodb:{AWS_REGION}:{account_id}:table/conversations/*"
                ]
            },
            {
                "Sid": "DynamoDBClientDeployments",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:DescribeTable",
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"
                ],
                "Resource": [
                    f"arn:aws:dynamodb:{AWS_REGION}:{account_id}:table/client_deployments",
                    f"arn:aws:dynamodb:{AWS_REGION}:{account_id}:table/client_deployments/*"
                ]
            },
            {
                "Sid": "SQSOperations",
                "Effect": "Allow",
                "Action": [
                    # Queue management
                    "sqs:CreateQueue",
                    "sqs:GetQueueUrl",
                    "sqs:GetQueueAttributes",
                    "sqs:SetQueueAttributes",
                    "sqs:ListQueues",
                    "sqs:ListQueueTags",
                    "sqs:TagQueue",
                    # Message operations
                    "sqs:SendMessage",
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:ChangeMessageVisibility",
                    "sqs:GetQueueUrl",
                    "sqs:PurgeQueue"
                ],
                "Resource": [
                    f"arn:aws:sqs:{AWS_REGION}:{account_id}:solopilot-requirements-queue",
                    f"arn:aws:sqs:{AWS_REGION}:{account_id}:*"  # For CreateQueue
                ]
            },
            {
                "Sid": "LambdaOperations",
                "Effect": "Allow",
                "Action": [
                    # Function management
                    "lambda:GetFunction",
                    "lambda:GetFunctionConfiguration",
                    "lambda:UpdateFunctionConfiguration",
                    "lambda:UpdateFunctionCode",
                    "lambda:ListFunctions",
                    "lambda:TagResource",
                    "lambda:ListTags",
                    # Permissions
                    "lambda:GetPolicy",
                    "lambda:AddPermission",
                    "lambda:RemovePermission",
                    # Monitoring
                    "lambda:GetFunctionConcurrency",
                    "lambda:PutFunctionConcurrency"
                ],
                "Resource": [
                    f"arn:aws:lambda:{AWS_REGION}:{account_id}:function:email-intake-lambda",
                    f"arn:aws:lambda:{AWS_REGION}:{account_id}:function:solopilot-*"
                ]
            },
            {
                "Sid": "SESOperations",
                "Effect": "Allow",
                "Action": [
                    # Email verification
                    "ses:GetIdentityVerificationAttributes",
                    "ses:VerifyEmailIdentity",
                    "ses:ListVerifiedEmailAddresses",
                    # Sending emails
                    "ses:SendEmail",
                    "ses:SendRawEmail",
                    # Configuration
                    "ses:GetSendQuota",
                    "ses:GetSendStatistics",
                    "ses:ListConfigurationSets",
                    "ses:DescribeConfigurationSet"
                ],
                "Resource": "*"  # SES doesn't support resource-level permissions for most actions
            },
            {
                "Sid": "CloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                    "logs:GetLogEvents",
                    "logs:FilterLogEvents"
                ],
                "Resource": [
                    f"arn:aws:logs:{AWS_REGION}:{account_id}:log-group:/aws/lambda/email-intake-lambda:*",
                    f"arn:aws:logs:{AWS_REGION}:{account_id}:log-group:/aws/lambda/solopilot-*:*"
                ]
            },
            {
                "Sid": "S3EmailStorage",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket"
                ],
                "Resource": [
                    "arn:aws:s3:::solopilot-emails/*",
                    "arn:aws:s3:::solopilot-emails"
                ]
            }
        ]
    }


class IAMPermissionManager:
    """Manages IAM permissions for the demo."""
    
    def __init__(self):
        """Initialize IAM client."""
        self.iam = boto3.client("iam")
        self.sts = boto3.client("sts")
        
    def check_user_exists(self) -> bool:
        """Check if the user exists."""
        try:
            self.iam.get_user(UserName=USER_NAME)
            logger.info(f"✅ User '{USER_NAME}' found")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                logger.error(f"❌ User '{USER_NAME}' not found")
                return False
            raise
    
    def check_policy_exists(self) -> bool:
        """Check if the inline policy already exists."""
        try:
            response = self.iam.get_user_policy(
                UserName=USER_NAME,
                PolicyName=POLICY_NAME
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                return False
            raise
    
    def add_permissions(self) -> bool:
        """Add the demo permissions to the user."""
        logger.info(f"🔑 Adding demo permissions for user '{USER_NAME}'")
        
        # Check user exists
        if not self.check_user_exists():
            return False
        
        # Check if policy already exists
        if self.check_policy_exists():
            logger.info(f"⚠️  Policy '{POLICY_NAME}' already exists")
            logger.info("   Use --remove flag to delete it first if you want to recreate")
            return True
        
        # Get policy document
        policy_doc = get_demo_policy()
        
        try:
            # Add inline policy
            self.iam.put_user_policy(
                UserName=USER_NAME,
                PolicyName=POLICY_NAME,
                PolicyDocument=json.dumps(policy_doc)
            )
            
            logger.info(f"✅ Successfully added policy '{POLICY_NAME}'")
            self._print_policy_summary()
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add policy: {str(e)}")
            return False
    
    def remove_permissions(self) -> bool:
        """Remove the demo permissions from the user."""
        logger.info(f"🗑️  Removing demo permissions for user '{USER_NAME}'")
        
        # Check user exists
        if not self.check_user_exists():
            return False
        
        # Check if policy exists
        if not self.check_policy_exists():
            logger.info(f"⚠️  Policy '{POLICY_NAME}' not found - nothing to remove")
            return True
        
        try:
            # Delete inline policy
            self.iam.delete_user_policy(
                UserName=USER_NAME,
                PolicyName=POLICY_NAME
            )
            
            logger.info(f"✅ Successfully removed policy '{POLICY_NAME}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to remove policy: {str(e)}")
            return False
    
    def _print_policy_summary(self) -> None:
        """Print a summary of the permissions granted."""
        print("\n" + "="*60)
        print("📋 Demo Permissions Summary")
        print("="*60)
        print(f"User: {USER_NAME}")
        print(f"Policy: {POLICY_NAME}")
        print(f"Region: {AWS_REGION}")
        print("\nPermissions granted:")
        print("  ✅ DynamoDB: conversations & client_deployments tables")
        print("  ✅ SQS: solopilot-requirements-queue")
        print("  ✅ Lambda: email-intake-lambda")
        print("  ✅ SES: Email sending and verification")
        print("  ✅ CloudWatch Logs: Lambda log access")
        print("  ✅ S3: Email storage bucket access")
        print("\n⚠️  IMPORTANT: These are temporary demo permissions")
        print("   Remove them after testing with: --remove flag")
        print("="*60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage IAM permissions for SoloPilot demo"
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove the demo permissions"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    # Verify AWS credentials
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        logger.info(f"AWS Account: {identity['Account']}")
        logger.info(f"AWS User: {identity['Arn']}")
        
        # Check if we're running as the target user
        if USER_NAME not in identity['Arn']:
            logger.warning(f"⚠️  Not running as user '{USER_NAME}'")
            logger.info("   This script will modify permissions for that user")
        
    except Exception as e:
        logger.error(f"❌ AWS credentials not configured: {str(e)}")
        sys.exit(1)
    
    # Dry run mode
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
        policy = get_demo_policy()
        print("\nPolicy that would be applied:")
        print(json.dumps(policy, indent=2))
        return
    
    # Execute action
    manager = IAMPermissionManager()
    
    if args.remove:
        success = manager.remove_permissions()
    else:
        success = manager.add_permissions()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()