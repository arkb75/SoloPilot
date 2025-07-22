#!/usr/bin/env python3
"""Create the email-intake-lambda function."""

import json
import logging
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

# Force us-east-2 region
os.environ["AWS_DEFAULT_REGION"] = "us-east-2"
AWS_REGION = "us-east-2"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_lambda_execution_role():
    """Create IAM role for Lambda execution."""
    iam = boto3.client("iam")
    role_name = "email-intake-lambda-role"

    # Check if role exists
    try:
        response = iam.get_role(RoleName=role_name)
        logger.info(f"✅ Role '{role_name}' already exists")
        return response["Role"]["Arn"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise

    # Create role
    logger.info(f"Creating IAM role: {role_name}")

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Execution role for email intake Lambda",
        )

        # Attach basic Lambda execution policy
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )

        # Attach DynamoDB access
        iam.attach_role_policy(
            RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
        )

        # Attach SQS access
        iam.attach_role_policy(
            RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonSQSFullAccess"
        )

        # Attach SES access
        iam.attach_role_policy(
            RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonSESFullAccess"
        )

        # Attach S3 access
        iam.attach_role_policy(
            RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess"
        )

        # Wait for role to be available
        time.sleep(10)

        logger.info(f"✅ Created role: {response['Role']['Arn']}")
        return response["Role"]["Arn"]

    except Exception as e:
        logger.error(f"Error creating role: {str(e)}")
        raise


def create_lambda_function():
    """Create the Lambda function."""
    lambda_client = boto3.client("lambda", region_name=AWS_REGION)
    function_name = "email-intake-lambda"

    # Check if function exists
    try:
        response = lambda_client.get_function(FunctionName=function_name)
        logger.info(f"✅ Lambda function '{function_name}' already exists")
        return
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    # Get execution role
    role_arn = create_lambda_execution_role()

    # Create minimal Lambda function
    logger.info(f"Creating Lambda function: {function_name}")

    # Create a minimal zip file
    import io
    import zipfile

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(
            "lambda_function.py",
            """def lambda_handler(event, context):
    return {"statusCode": 200, "body": "Not implemented yet"}
""",
        )

    zip_content = zip_buffer.getvalue()

    try:
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.9",
            Role=role_arn,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": zip_content},
            Description="Email intake processing Lambda",
            Timeout=300,
            MemorySize=512,
            Environment={"Variables": {"PLACEHOLDER": "true"}},
        )

        logger.info(f"✅ Created Lambda function: {function_name}")
        logger.info(f"   ARN: {response['FunctionArn']}")

    except Exception as e:
        logger.error(f"Error creating function: {str(e)}")
        raise


def main():
    """Main entry point."""
    try:
        create_lambda_function()
        print("\n✅ Lambda function created successfully!")
        print("   You can now run the setup script again")
    except Exception as e:
        logger.error(f"Failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
