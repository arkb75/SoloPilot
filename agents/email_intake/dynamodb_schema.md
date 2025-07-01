# DynamoDB Schema for Multi-Turn Email Conversations

## Table: conversations

### Primary Key
- **conversation_id** (String) - Partition Key
  - Value: First email's Message-ID (hashed to 16 chars for consistency)
  - Example: "a1b2c3d4e5f6g7h8"

### Attributes

#### Core Attributes
- **conversation_id** (S) - Unique conversation identifier
- **created_at** (S) - ISO 8601 timestamp of first email
- **updated_at** (S) - ISO 8601 timestamp of last modification
- **last_updated_at** (S) - Used for optimistic locking (same as updated_at)
- **last_seq** (N) - Sequence number for optimistic locking (starts at 0)
- **status** (S) - Conversation state: active | pending_info | completed | archived
- **ttl** (N) - Unix timestamp for auto-expiry (30 days from last update)

#### Email Threading
- **original_message_id** (S) - Raw Message-ID of first email
- **subject** (S) - Cleaned subject (Re:/Fwd: removed)
- **participants** (SS) - Set of all email addresses involved
- **thread_references** (L) - List of all Message-IDs in thread

#### Email History
- **email_history** (L) - List of email objects:
  ```json
  {
    "email_id": "unique-email-id",
    "message_id": "RFC 5322 Message-ID",
    "in_reply_to": "Parent Message-ID",
    "references": ["thread", "reference", "ids"],
    "from": "sender@example.com",
    "to": ["recipient@example.com"],
    "cc": ["cc@example.com"],
    "subject": "Email subject",
    "body": "Email content",
    "timestamp": "2024-01-15T10:30:00Z",
    "direction": "inbound|outbound",
    "attachments": [
      {
        "filename": "document.pdf",
        "content_type": "application/pdf",
        "size": 102400,
        "s3_key": "attachments/conv-id/email-id/document.pdf"
      }
    ],
    "metadata": {
      "client_ip": "192.168.1.1",
      "user_agent": "Outlook/16.0",
      "spam_score": 0.1
    }
  }
  ```

#### Requirements & Analysis
- **requirements** (M) - Extracted requirements object
- **requirements_version** (N) - Version number for requirements updates
- **ai_analysis** (M) - AI-generated insights and summaries
- **sentiment_scores** (L) - Sentiment analysis per email

#### Metadata
- **metadata** (M) - Extensible metadata:
  - client_info (M) - Client details extracted from emails
  - tags (SS) - Searchable tags
  - priority (S) - high | medium | low
  - assigned_to (S) - Team member assignment
  - notes (L) - Internal notes with timestamps

### Global Secondary Indexes (GSIs)

#### GSI1: StatusIndex
- Partition Key: status (S)
- Sort Key: updated_at (S)
- Projection: ALL
- Use case: Query conversations by status with time ordering

#### GSI2: ParticipantIndex
- Partition Key: participant (S)
- Sort Key: updated_at (S) 
- Projection: KEYS_ONLY + subject, status, last_seq
- Use case: Find all conversations for a specific email address
- Note: Uses sparse index - write participant entries separately

#### GSI3: TTLIndex (Future)
- Partition Key: ttl_date (S) - YYYY-MM-DD format
- Sort Key: ttl (N)
- Projection: KEYS_ONLY
- Use case: Batch process expiring conversations

### Access Patterns

1. **Get conversation by ID**
   - Query: conversation_id = :id

2. **List active conversations**
   - Query GSI1: status = "active", sorted by updated_at

3. **Find conversations by participant**
   - Query GSI2: participant = :email

4. **Update with optimistic locking**
   - Condition: last_seq = :expected_seq
   - Update: SET last_seq = :expected_seq + 1

5. **Append email with retry**
   - Update: list_append(email_history, :new_email)
   - Condition: last_seq = :current_seq

### Capacity Planning

- **Read Capacity**: 5 RCU (auto-scaling 5-40)
- **Write Capacity**: 10 WCU (auto-scaling 10-80)
- **Item Size**: ~5-50KB per conversation (10-20 emails avg)
- **Hot Partition Prevention**: Hash conversation_id evenly

### Migration Strategy

1. **Phase 1**: Add new attributes to existing items
   - Add last_seq (default 0)
   - Add last_updated_at (copy from updated_at)
   - Add ttl (30 days from updated_at)

2. **Phase 2**: Create GSIs
   - Deploy StatusIndex first (most critical)
   - Add ParticipantIndex for search
   - TTLIndex can wait for v2

3. **Phase 3**: Update application code
   - Implement optimistic locking
   - Add participant tracking
   - Enable TTL processing

### Future Enhancements

1. **Analytics Attributes**
   - response_time_avg (N)
   - email_count (N) 
   - resolution_time (N)

2. **Search Capabilities**
   - full_text_search (S) - Concatenated searchable content
   - elasticsearch_indexed (BOOL)

3. **Compliance**
   - data_retention_policy (S)
   - gdpr_consent (BOOL)
   - audit_log (L)