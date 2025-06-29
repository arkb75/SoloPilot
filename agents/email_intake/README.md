# Email Intake Agent

AWS Lambda-based email processing agent for handling Apollo.io replies and extracting project requirements.

## Architecture

- **AWS SES** → Receives incoming emails
- **S3** → Stores raw email files
- **Lambda** → Processes emails (this module)
- **DynamoDB** → Maintains conversation state
- **Bedrock** → Extracts requirements using LLM
- **SQS** → Sends completed requirements to dev pipeline

## Components

### email_agent.py
Main Lambda handler that orchestrates the email processing workflow:
- Downloads email from S3
- Parses email content
- Maintains conversation state
- Extracts requirements
- Sends follow-up questions or pushes to SQS

### conversation_state.py
DynamoDB wrapper for managing conversation threads:
- Creates/retrieves conversations by thread ID
- Stores email history
- Updates requirements progressively
- Tracks conversation status

### email_parser.py
Extracts structured data from raw emails:
- Thread ID extraction/generation
- Email address parsing
- Subject line cleaning
- Body text extraction
- Signature removal

### requirement_extractor.py
Uses Bedrock LLM to extract project requirements:
- Builds conversation context
- Generates extraction prompts
- Validates requirement completeness
- Generates follow-up questions

## Email Templates

**Initial Response:**
- Acknowledges interest
- Asks for missing information

**Follow-up Questions:**
- Project type
- Business description
- Key features (3-5)
- Timeline
- Budget

**Confirmation:**
- Summarizes understood scope
- Confirms handoff to dev pipeline

## Testing

```bash
# Run unit tests
pytest tests/test_email_intake.py -v

# Test locally with mock email
python scripts/test_email_intake.py
```

## Deployment

1. Create DynamoDB table:
   - Name: `conversations`
   - Primary key: `conversation_id` (String)

2. Set Lambda environment variables:
   - `REQUIREMENT_QUEUE_URL`: SQS queue URL
   - `SENDER_EMAIL`: Verified SES email
   - `DYNAMO_TABLE`: Table name (default: conversations)

3. Configure SES to trigger Lambda on email receipt

## Status: ✅ COMPLETE

All components implemented and tested with mock Apollo.io replies.