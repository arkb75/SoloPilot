# Multi-Turn Email Conversation Support

This enhancement adds thread-safe, multi-turn conversation support to the email intake Lambda with RFC 5322 compliant email threading.

## Features

### Core Capabilities
- **RFC 5322 Email Threading**: Proper handling of Message-ID, In-Reply-To, and References headers
- **Thread-Safe State Management**: Optimistic locking prevents race conditions from concurrent emails
- **Conversation Tracking**: All emails in a thread are grouped by conversation ID
- **Outbound Reply Tracking**: Optional tracking of system-generated replies
- **TTL-Based Expiry**: Automatic cleanup of old conversations after 30 days
- **Automated Response Detection**: Ignores out-of-office and auto-reply emails

### Architecture Improvements
- **Futureproof DynamoDB Schema**: Supports GSIs for querying by status and participant
- **Versioned Requirements**: Prevents lost updates with version control
- **Participant Tracking**: Maintains set of all email addresses in conversation
- **Thread Reference Chain**: Complete Message-ID history for email clients

## Quick Start

### 1. Deploy Updated Lambda Code

```bash
# Package the Lambda
cd agents/email_intake
zip -r email_intake_v2.zip *.py

# Update Lambda function code
aws lambda update-function-code \
  --function-name email-intake-lambda \
  --zip-file fileb://email_intake_v2.zip
```

### 2. Update Lambda Handler

Change the Lambda handler to use the new version:
```
lambda_function_v2.lambda_handler
```

### 3. Set Environment Variables

```bash
aws lambda update-function-configuration \
  --function-name email-intake-lambda \
  --environment Variables='{
    "DYNAMO_TABLE": "conversations",
    "REQUIREMENT_QUEUE_URL": "https://sqs.region.amazonaws.com/account/queue-name",
    "SENDER_EMAIL": "noreply@yourdomain.com",
    "ENABLE_OUTBOUND_TRACKING": "true"
  }'
```

### 4. Migrate Existing Data

```bash
# Check migration plan (dry run)
python migrate_dynamodb.py --table conversations --dry-run

# Run migration
python migrate_dynamodb.py --table conversations

# Check for missing GSIs
python migrate_dynamodb.py --table conversations --check-gsi
```

## DynamoDB Schema

### Primary Key
- **conversation_id** (String) - Hashed from first email's Message-ID

### Key Attributes
```yaml
Core:
  - last_seq: Number (for optimistic locking)
  - last_updated_at: String (for optimistic locking)
  - ttl: Number (Unix timestamp for expiry)

Threading:
  - original_message_id: String
  - thread_references: List[String]
  - participants: Set[String]

Email History:
  - email_history: List of email objects with:
    - email_id: Unique ID within conversation
    - message_id: RFC 5322 Message-ID
    - in_reply_to: Parent message reference
    - references: Thread reference chain
    - direction: inbound|outbound
    - attachments: List of attachment metadata
```

### Global Secondary Indexes

1. **StatusIndex**
   - Partition: status
   - Sort: updated_at
   - Use: Query conversations by status

2. **ParticipantIndex** 
   - Partition: participant
   - Sort: updated_at
   - Use: Find all conversations for an email address

## Usage Examples

### Processing a New Email Thread

```python
# Email 1: Initial inquiry
From: client@example.com
Subject: Need help with project
Message-ID: <abc123@example.com>

# Creates conversation with ID: hash("abc123@example.com")
# Status: pending_info
# Sends follow-up questions
```

### Processing a Reply

```python
# Email 2: Reply with details
From: client@example.com
Subject: Re: Need help with project
Message-ID: <def456@example.com>
In-Reply-To: <abc123@example.com>

# Maps to same conversation via In-Reply-To
# Updates requirements with new info
# If complete: sends confirmation
```

### Handling Concurrent Emails

```python
# Two team members reply simultaneously
# Both emails have In-Reply-To: <original@team.com>

# Lambda A: Reads seq=5, updates to seq=6 ✓
# Lambda B: Reads seq=5, tries update, gets conflict
# Lambda B: Re-reads seq=6, updates to seq=7 ✓

# Both emails successfully added to conversation
```

## Testing

### Unit Tests
```bash
# Test threading utilities
pytest tests/test_email_intake_v2.py::TestEmailThreadingUtils -v

# Test optimistic locking
pytest tests/test_email_intake_v2.py::TestConversationStateV2 -v

# Test race conditions
pytest tests/test_email_intake_v2.py::TestRaceConditionScenarios -v
```

### Integration Tests
```bash
# Test full conversation flow
pytest tests/test_email_conversation_flow.py::TestMultiEmailConversationFlow -v

# Test specific scenario
pytest tests/test_email_conversation_flow.py::test_three_email_conversation_flow -v
```

## Monitoring

### CloudWatch Metrics to Track

1. **Optimistic Lock Conflicts**
   ```
   Filter: "Optimistic lock conflict"
   Metric: Count of retries needed
   ```

2. **Conversation Completion Rate**
   ```
   Filter: "Requirements complete"
   Metric: Completed vs pending conversations
   ```

3. **Thread Length Distribution**
   ```
   Custom metric: email_history length
   ```

### Key Logs to Monitor

```python
# Successful threading
"Reply detected: conversation=abc123, original=msg@example.com"

# Race condition handled
"Optimistic lock conflict for conv123, retry 1/2"

# Automated responses
"Skipping automated response for conversation abc123"
```

## Migration Path

### Phase 1: Deploy Code (No Downtime)
1. Deploy new Lambda code as `lambda_function_v2.py`
2. Update Lambda handler configuration
3. New emails use enhanced threading

### Phase 2: Migrate Data (Minutes)
1. Run migration script to add new attributes
2. Existing conversations gain threading support
3. No impact on active processing

### Phase 3: Create Indexes (Optional)
1. Add GSIs via CloudFormation/Console
2. Enable advanced queries
3. Monitor index build progress

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DYNAMO_TABLE | conversations | DynamoDB table name |
| ENABLE_OUTBOUND_TRACKING | true | Track system replies |
| SES_CONFIGURATION_SET | (empty) | SES config for tracking |
| TTL_DAYS | 30 | Days before expiry |

### Feature Flags

```python
# In lambda_function_v2.py
ENABLE_AUTO_RESPONSE_FILTER = True  # Skip OOO emails
MAX_RETRY_ATTEMPTS = 2              # Optimistic lock retries
TRACK_RESPONSE_METRICS = True       # Calculate response times
```

## Troubleshooting

### Common Issues

1. **High retry rate on updates**
   - Cause: Many concurrent emails
   - Fix: Increase MAX_RETRY_ATTEMPTS
   - Monitor: CloudWatch logs for "retry"

2. **Conversations not linking**
   - Cause: Missing email headers
   - Fix: Check References/In-Reply-To
   - Debug: Log thread_info in parser

3. **Old conversations reappearing**
   - Cause: TTL not processed
   - Fix: Enable DynamoDB TTL on table
   - Verify: Check item TTL values

### Debug Commands

```bash
# Check conversation state
aws dynamodb get-item \
  --table-name conversations \
  --key '{"conversation_id": {"S": "abc123"}}'

# List recent conversations
aws dynamodb query \
  --table-name conversations \
  --index-name StatusIndex \
  --key-condition-expression "status = :s" \
  --expression-attribute-values '{":s": {"S": "active"}}' \
  --scan-index-forward false \
  --limit 10
```

## Performance Considerations

### Optimizations Implemented
- Consistent reads only when necessary
- Batch attribute updates in single operation  
- Minimal retries with exponential backoff
- Efficient Message-ID hashing (MD5 16-char)

### Capacity Planning
- Read capacity: 5-40 RCU (auto-scaling)
- Write capacity: 10-80 WCU (auto-scaling)
- Item size: ~5-50KB (10-20 emails typical)
- Hot partition prevention via hash distribution

## Security

### Data Protection
- Email content encrypted at rest (DynamoDB)
- No PII in CloudWatch logs
- TTL ensures data lifecycle compliance

### Access Control
- Lambda execution role requires:
  - dynamodb:GetItem
  - dynamodb:PutItem  
  - dynamodb:UpdateItem
  - dynamodb:Query (for GSIs)

## Future Enhancements

### Planned Features
1. **Analytics Dashboard**: Response time metrics
2. **Smart Routing**: Auto-assign based on content
3. **Template Responses**: Reusable reply templates
4. **Webhook Notifications**: Real-time updates

### API Extensions
```python
# Get conversation summary
GET /conversations/{id}/summary

# Search by participant
GET /conversations?participant=email@example.com

# Bulk operations
POST /conversations/bulk-update
```