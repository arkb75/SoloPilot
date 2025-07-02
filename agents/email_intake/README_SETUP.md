# Email Intake Lambda Setup Guide

## Overview

This guide helps you set up the email intake Lambda function with proper AWS region configuration. The system processes incoming emails, extracts requirements, and manages conversations in DynamoDB.

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Python 3.8+ with boto3 installed
3. Lambda function created (named `email-intake-lambda`)
4. SES configured to receive emails

## Quick Setup

### Option A: Automated Setup (Recommended)

```bash
# Run the complete demo setup
./scripts/run_email_intake_demo.sh
```

This will:
1. Add temporary IAM permissions
2. Set up all infrastructure
3. Show test commands

### Option B: Manual Setup

### 1. Add IAM Permissions (if needed)

```bash
# Add temporary demo permissions
python scripts/add_demo_iam_permissions.py

# View policy without applying
python scripts/add_demo_iam_permissions.py --dry-run

# Remove permissions after demo
python scripts/add_demo_iam_permissions.py --remove
```

### 2. Run the Setup Script

```bash
# From project root
export AWS_DEFAULT_REGION=us-east-2
python scripts/setup_email_intake_demo.py
```

This script will:
- Create the `conversations` DynamoDB table (if missing)
- Enable TTL on the table (30-day expiry)
- Create/find the SQS queue for requirements
- Update Lambda environment variables
- Upload the Lambda deployment package (if available)

### 3. Build Lambda Package (if needed)

If the setup script reports that the Lambda package is missing:

```bash
cd agents/email_intake
make package
# This creates email_intake.zip
```

### 4. Test the Email Flow

```bash
# List recent conversations
python scripts/test_email_flow.py --list

# Send a test email (basic scenario)
python scripts/test_email_flow.py --scenario basic

# Send detailed requirements
python scripts/test_email_flow.py --scenario detailed

# Check specific conversation
python scripts/test_email_flow.py --details <conversation_id>
```

## Region Configuration

All scripts now respect the `AWS_DEFAULT_REGION` environment variable:

```bash
# Set region for all operations
export AWS_DEFAULT_REGION=us-east-2

# Or specify region in migration script
python agents/email_intake/migrate_dynamodb.py --region us-east-2
```

## Lambda Configuration

The setup script configures these environment variables:

- `SENDER_EMAIL`: noreply@solopilot.abdulkhurram.com
- `REQUIREMENT_QUEUE_URL`: Auto-detected/created SQS queue URL
- `DYNAMO_TABLE`: conversations
- `ENABLE_OUTBOUND_TRACKING`: true
- `AWS_DEFAULT_REGION`: us-east-2

## SES Configuration

1. Verify sender email:
```bash
aws ses verify-email-identity --email-address noreply@solopilot.abdulkhurram.com --region us-east-2
```

2. Create SES rule to trigger Lambda:
- Action: Lambda
- Function: email-intake-lambda
- Store in S3 bucket (optional but recommended)

## DynamoDB Schema

The `conversations` table uses:
- Primary Key: `conversation_id` (String)
- TTL attribute: `ttl` (Number) - 30 day expiry
- Attributes:
  - `last_seq`: Sequence number for emails
  - `last_updated_at`: ISO timestamp
  - `participants`: Set of email addresses
  - `email_history`: List of email objects
  - `requirements`: Extracted requirements
  - `status`: active/pending_info/completed

## Troubleshooting

1. **Lambda not found**: Create the Lambda function first via AWS Console
2. **SES not verified**: Check email verification status and sandbox mode
3. **No conversations created**: Check CloudWatch logs for Lambda errors
4. **Region mismatch**: Ensure AWS_DEFAULT_REGION=us-east-2 is set

## Migration

To migrate existing conversations for multi-turn support:

```bash
export AWS_DEFAULT_REGION=us-east-2

# Dry run first
python agents/email_intake/migrate_dynamodb.py --dry-run

# Execute migration
python agents/email_intake/migrate_dynamodb.py
```