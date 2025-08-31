# Email Intake Agent

An AI-powered email agent that engages in multi-turn conversations with clients to understand requirements, present proposals, and manage the approval workflow.

## Features

- **Multi-Turn Conversations**: Maintains context across email exchanges
- **Phase-Based Workflow**: Understanding → Proposal → Documentation → Approval
- **Manual Approval Mode**: Review and approve AI responses before sending
- **Email Threading**: Proper RFC 5322 compliant email threading
- **Budget Awareness**: Respects client budget constraints
- **PDF Proposals**: Automatic proposal PDF generation
- **Frontend Dashboard**: Web interface for managing conversations

## Architecture

### Core Components

1. **`lambda_function.py`**: Main Lambda handler for processing emails
2. **`conversation_state.py`**: DynamoDB state management with manual approval support
3. **`conversational_responder.py`**: AI response generation with prompt tracking
4. **`email_parser.py`**: SES email parsing utilities
5. **`pdf_generator.py`**: Proposal PDF generation
6. **`api/lambda_api.py`**: REST API for frontend operations

### Frontend Components

- **React + TypeScript**: Modern web interface
- **Tailwind CSS**: Styling
- **API Integration**: Real-time conversation management

## Setup

### Prerequisites

- AWS Account with SES, Lambda, DynamoDB configured
- Node.js 18+ for frontend
- Python 3.9+ for Lambda

### Environment Variables

```bash
# Lambda Environment
DYNAMODB_TABLE=conversations
SENDER_EMAIL=abdul@solopilot.com
SENDER_NAME=Abdul
CALENDLY_LINK=https://calendly.com/your-link
PDF_LAMBDA_ARN=arn:aws:lambda:region:account:function:doc-gen
DOCUMENT_BUCKET=solopilot-dev-documents

# Frontend Environment
VITE_API_URL=https://your-api-gateway-url.execute-api.region.amazonaws.com/prod
VITE_API_KEY=your-api-key
```

### Deployment

1. **Deploy Lambda Functions**:
   ```bash
   ./deploy.sh
   ```

2. **Setup API Gateway**:
   - Use `api/api_gateway_config.yaml` as reference
   - Configure CORS and API key authentication

3. **Deploy Frontend**:
   ```bash
   cd frontend
   npm install
   npm run build
   aws s3 sync dist/ s3://your-frontend-bucket/
   ```

## Usage

### Email Processing Flow

1. **Inbound Email** → Lambda triggers
2. **Conversation Management** → Thread tracking and state updates
3. **AI Response Generation** → Phase-appropriate responses with LLM prompts
4. **Manual Approval** → Queue responses for review (default mode)
5. **Send Reply** → After approval or in auto mode

### Manual Approval Workflow

1. All new conversations start in **manual mode**
2. AI generates response and stores with full LLM prompt
3. Admin reviews in frontend dashboard
4. Options: **Approve**, **Edit**, or **Reject**
5. Approved/edited responses are sent via SES

### Conversation Phases

- **Understanding**: Gathering requirements
- **Proposal Draft**: Presenting cost/timeline
- **Proposal Feedback**: Handling client response
- **Documentation**: Detailed project plan
- **Awaiting Approval**: Final confirmation
- **Approved**: Ready to start work

## API Endpoints

- `GET /conversations` - List all conversations
- `GET /conversations/{id}` - Get conversation details
- `PATCH /conversations/{id}/mode` - Toggle auto/manual mode
- `GET /conversations/{id}/pending-replies` - Get pending replies
- `POST /replies/{id}/approve` - Approve reply
- `POST /replies/{id}/reject` - Reject reply
- `PATCH /replies/{id}` - Amend reply content
- `GET /attachments/{id}` - Get attachment URL

## DynamoDB Schema

```json
{
  "conversation_id": "unique-id",
  "phase": "understanding",
  "reply_mode": "manual",
  "pending_replies": [{
    "reply_id": "uuid",
    "llm_prompt": "full prompt text",
    "llm_response": "generated response",
    "status": "pending"
  }],
  "email_history": [...],
  "attachments": [...],
  "participants": ["client@example.com"],
  "thread_references": ["message-ids"]
}
```

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
