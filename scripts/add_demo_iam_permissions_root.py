#!/usr/bin/env python3
"""Add IAM permissions to abdul user - RUN THIS AS ROOT USER.

This script should be run with root AWS credentials to grant permissions
to the abdul user for the demo.

Usage:
    # First, switch to root credentials:
    export AWS_PROFILE=root  # or whatever your root profile is named
    
    # Then run:
    python add_demo_iam_permissions_root.py
    
    # To remove:
    python add_demo_iam_permissions_root.py --remove
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
                "Sid": "DynamoDBOperations",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:*"
                ],
                "Resource": [
                    f"arn:aws:dynamodb:{AWS_REGION}:{account_id}:table/conversations",
                    f"arn:aws:dynamodb:{AWS_REGION}:{account_id}:table/conversations/*",
                    f"arn:aws:dynamodb:{AWS_REGION}:{account_id}:table/client_deployments",
                    f"arn:aws:dynamodb:{AWS_REGION}:{account_id}:table/client_deployments/*"
                ]
            },
            {
                "Sid": "DynamoDBCreateTable",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:CreateTable",
                    "dynamodb:DescribeTable",
                    "dynamodb:ListTables",
                    "dynamodb:TagResource"
                ],
                "Resource": "*"
            },
            {
                "Sid": "SQSOperations",
                "Effect": "Allow",
                "Action": [
                    "sqs:*"
                ],
                "Resource": [
                    f"arn:aws:sqs:{AWS_REGION}:{account_id}:solopilot-requirements-queue",
                    f"arn:aws:sqs:{AWS_REGION}:{account_id}:*"
                ]
            },
            {
                "Sid": "LambdaOperations",
                "Effect": "Allow",
                "Action": [
                    "lambda:*"
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
                    "ses:*"
                ],
                "Resource": "*"
            },
            {
                "Sid": "CloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:*"
                ],
                "Resource": [
                    f"arn:aws:logs:{AWS_REGION}:{account_id}:log-group:/aws/lambda/*",
                    f"arn:aws:logs:{AWS_REGION}:{account_id}:log-group:*",
                    f"arn:aws:logs:{AWS_REGION}:{account_id}:log-stream:*"
                ]
            },
            {
                "Sid": "S3EmailStorage",
                "Effect": "Allow",
                "Action": [
                    "s3:*"
                ],
                "Resource": [
                    "arn:aws:s3:::solopilot-emails/*",
                    "arn:aws:s3:::solopilot-emails"
                ]
            }
        ]
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Add IAM permissions to abdul user (RUN AS ROOT)"
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove the demo permissions"
    )
    
    args = parser.parse_args()
    
    # Verify we're running with sufficient privileges
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        logger.info(f"Running as: {identity['Arn']}")
        
        # Check if this is root or has admin privileges
        if "root" not in identity['Arn'] and "admin" not in identity['Arn'].lower():
            logger.warning("⚠️  Not running as root/admin user!")
            logger.warning("   This script requires root or administrator privileges")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ AWS credentials error: {str(e)}")
        sys.exit(1)
    
    # Initialize IAM client
    iam = boto3.client("iam")
    
    if args.remove:
        # Remove policy
        logger.info(f"Removing policy '{POLICY_NAME}' from user '{USER_NAME}'...")
        try:
            iam.delete_user_policy(
                UserName=USER_NAME,
                PolicyName=POLICY_NAME
            )
            logger.info("✅ Policy removed successfully")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                logger.info("Policy not found - nothing to remove")
            else:
                logger.error(f"❌ Error: {str(e)}")
                sys.exit(1)
    else:
        # Add policy
        logger.info(f"Adding policy '{POLICY_NAME}' to user '{USER_NAME}'...")
        
        # Check if user exists
        try:
            iam.get_user(UserName=USER_NAME)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                logger.error(f"❌ User '{USER_NAME}' not found!")
                logger.info("   Please create the user first")
                sys.exit(1)
            else:
                raise
        
        # Add the policy
        policy_doc = get_demo_policy()
        try:
            iam.put_user_policy(
                UserName=USER_NAME,
                PolicyName=POLICY_NAME,
                PolicyDocument=json.dumps(policy_doc)
            )
            
            logger.info("✅ Policy added successfully!")
            print("\n" + "="*60)
            print("📋 Demo Permissions Added")
            print("="*60)
            print(f"User: {USER_NAME}")
            print(f"Policy: {POLICY_NAME}")
            print(f"Account: {identity['Account']}")
            print("\nThe abdul user now has permissions for:")
            print("  ✅ DynamoDB (conversations, client_deployments)")
            print("  ✅ SQS (all operations)")
            print("  ✅ Lambda (email-intake-lambda)")
            print("  ✅ SES (email operations)")
            print("  ✅ CloudWatch Logs")
            print("  ✅ S3 (solopilot-emails bucket)")
            print("\n⚠️  Remember to remove these permissions after testing!")
            print(f"   Run: python {sys.argv[0]} --remove")
            print("="*60)
            
        except Exception as e:
            logger.error(f"❌ Failed to add policy: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()