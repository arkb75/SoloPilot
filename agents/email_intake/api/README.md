# Email Agent API Deployment

This directory contains the API Lambda function and deployment scripts for the Email Agent Management system.

## Prerequisites

- AWS CLI configured with appropriate credentials
- DynamoDB table named `conversations` already exists (from main email intake deployment)
- AWS region set (defaults to us-east-2)

## Deployment Steps

### 1. Deploy Lambda Function

```bash
./deploy_api.sh
```

This script will:
- Create/update the Lambda function `email-agent-api`
- Create necessary IAM roles and policies
- Package the code with required dependencies

### 2. Create API Gateway

```bash
./create_api_gateway.sh
```

This script will:
- Create a REST API in API Gateway
- Configure all required endpoints
- Enable CORS
- Create an API key and usage plan
- Output your API URL and API key

### 3. Update Frontend Configuration

After running both scripts, update your frontend `.env.local` file with the values output by the second script:

```env
VITE_API_URL=https://[your-api-id].execute-api.us-east-2.amazonaws.com/prod
VITE_API_KEY=[your-api-key]
```

## API Endpoints

- `GET /conversations` - List all conversations
- `GET /conversations/{id}` - Get conversation details
- `PATCH /conversations/{id}` - Update conversation
- `PATCH /conversations/{id}/mode` - Toggle auto/manual mode
- `GET /conversations/{id}/pending-replies` - Get pending replies
- `PATCH /replies/{id}` - Amend reply
- `POST /replies/{id}/approve` - Approve reply
- `POST /replies/{id}/reject` - Reject reply
- `GET /attachments/{id}` - Get attachment URL

All endpoints require the API key in the `X-Api-Key` header.