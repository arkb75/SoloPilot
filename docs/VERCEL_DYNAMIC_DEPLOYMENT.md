# Vercel Dynamic Deployment System

This system enables automatic creation and deployment of Vercel projects for each client, providing isolated deployments with unique URLs.

## Quick Start

### Prerequisites
- Vercel personal account with API token
- GitHub personal access token
- AWS credentials for DynamoDB access

### Environment Variables
```bash
export VERCEL_TOKEN="your-vercel-api-token"
export GITHUB_TOKEN="your-github-pat"
export AWS_REGION="us-east-1"
```

## Usage

### 1. Create a Client Project
```bash
python scripts/vercel_project_manager.py create \
  --client-name "Smith Consulting" \
  --project-type site \
  --framework nextjs
```

### 2. Deploy from Conversation
```bash
python scripts/deploy_client_project.py deploy-conversation \
  --conversation-id "conv-abc123"
```

### 3. Deploy with Project Creation
```bash
python scripts/deploy_to_vercel.py \
  --token $VERCEL_TOKEN \
  --create-project \
  --client-name "ABC Corp" \
  --project-type app \
  --branch main \
  --commit abc123
```

### 4. List Client Projects
```bash
python scripts/vercel_project_manager.py list
```

## Architecture

### Components

1. **Vercel Project Manager** (`scripts/vercel_project_manager.py`)
   - Creates Vercel projects with unique names
   - Manages project lifecycle (create, list, delete)
   - Configures framework-specific settings

2. **Deployment Tracker** (`agents/email_intake/deployment_tracker.py`)
   - Stores deployment records in DynamoDB
   - Tracks Vercel project IDs and GitHub repos
   - Maintains deployment history

3. **Client Deployment Orchestrator** (`scripts/deploy_client_project.py`)
   - Coordinates full deployment pipeline
   - Creates GitHub repos with branch protection
   - Triggers Vercel deployments
   - Returns live URLs

4. **Enhanced Deploy Script** (`scripts/deploy_to_vercel.py`)
   - Supports `--create-project` flag
   - Auto-detects framework
   - Handles personal Vercel accounts

5. **GitHub Workflow** (`.github/workflows/deploy.yml`)
   - Detects client branches (`client/**`)
   - Supports manual client deployments
   - Automatic project creation

## Project Naming Convention

Projects are named using the pattern:
```
client-{sanitized-name}-{type}-{YYYYMMDD}
```

Examples:
- `client-smith-consulting-site-20250701`
- `client-abc-corp-app-20250701`
- `client-xyz-inc-api-20250701`

## DynamoDB Schema

### Table: `client_deployments`
```python
{
  "client_id": "conv-abc123",          # Primary key
  "client_name": "Smith Consulting",
  "project_type": "site",
  "vercel_project_id": "prj_abc123",
  "github_repo_url": "https://github.com/user/smith-consulting-site",
  "deployment_urls": [
    {
      "url": "client-smith-site-abc123.vercel.app",
      "deployment_id": "dpl_xyz789",
      "environment": "production",
      "deployed_at": "2025-07-01T10:00:00Z"
    }
  ],
  "status": "deployed",
  "created_at": "2025-07-01T09:00:00Z",
  "last_deployed_at": "2025-07-01T10:00:00Z"
}
```

## Deployment Flow

1. **Email Intake** → Requirements extracted → Conversation created
2. **Deployment Trigger** → Orchestrator reads requirements
3. **GitHub Repo** → Created with branch protection
4. **Vercel Project** → Created with unique name
5. **Deployment** → Code deployed to Vercel
6. **URL Return** → Live URL returned to user

## CLI Commands

### Vercel Project Manager
```bash
# Create project
python scripts/vercel_project_manager.py create \
  --client-name "Client Name" \
  --project-type site

# List projects
python scripts/vercel_project_manager.py list

# Delete project
python scripts/vercel_project_manager.py delete \
  --project-id prj_abc123
```

### Deployment Orchestrator
```bash
# Deploy from conversation
python scripts/deploy_client_project.py deploy-conversation \
  --conversation-id conv-abc123

# Deploy from requirements file
python scripts/deploy_client_project.py deploy-requirements \
  --requirements requirements.json

# List deployments
python scripts/deploy_client_project.py list-deployments
```

## GitHub Actions Integration

The workflow automatically detects client deployments:

1. **Branch-based**: Push to `client/smith-consulting` branch
2. **Manual trigger**: Use workflow_dispatch with client_name

Example workflow trigger:
```yaml
on:
  push:
    branches:
      - 'client/**'
  workflow_dispatch:
    inputs:
      client_name:
        description: 'Client name'
        required: true
      project_type:
        description: 'Project type'
        default: 'site'
```

## Security Considerations

1. **Private Repos**: All client repos are created as private
2. **Branch Protection**: Main branch protected by default
3. **Environment Isolation**: Each client has separate Vercel project
4. **Token Security**: Use GitHub secrets for API tokens

## Troubleshooting

### Common Issues

1. **Project Already Exists**
   - The system checks for existing projects before creating
   - Use the same client name to reuse projects

2. **Deployment Fails**
   - Check Vercel logs: `vercel logs --project-id prj_abc123`
   - Verify GitHub repo has code

3. **DynamoDB Access**
   - Ensure AWS credentials are configured
   - Check table exists: `aws dynamodb describe-table --table-name client_deployments`

### Debug Commands
```bash
# Check Vercel project
curl -H "Authorization: Bearer $VERCEL_TOKEN" \
  https://api.vercel.com/v10/projects/prj_abc123

# Check deployment status
python -c "
from src.agents.email_intake.deployment_tracker import DeploymentTracker
tracker = DeploymentTracker()
print(tracker.get_deployment('conv-abc123'))
"
```

## Future Enhancements

1. **Custom Domains**: Auto-configure client domains
2. **Environment Variables**: Client-specific env management
3. **Webhook Notifications**: Deployment status callbacks
4. **Cost Tracking**: Per-client usage metrics
5. **Template Projects**: Starter templates by project type
