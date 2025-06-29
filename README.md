# 🚀 SoloPilot – End-to-End Freelance Automation Platform

[![CI Status](https://github.com/your-username/SoloPilot/workflows/CI/badge.svg)](https://github.com/your-username/SoloPilot/actions)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=solopilot_ai_automation&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=solopilot_ai_automation)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=solopilot_ai_automation&metric=coverage)](https://sonarcloud.io/summary/new_code?id=solopilot_ai_automation)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=solopilot_ai_automation&metric=code_smells)](https://sonarcloud.io/summary/new_code?id=solopilot_ai_automation)

**SoloPilot** automates the entire freelance development process from client email to deployed website. Our AI agents handle requirements gathering, development, review, and deployment—delivering professional websites in days, not weeks.

## 🎯 Vision

Transform freelance development by automating everything except client relationships:
- **Email arrives** → Requirements extracted via conversational AI
- **AI builds** → Code reviewed automatically with quality gates
- **Deploy happens** → Client gets live site on custom domain
- **Portfolio grows** → Case studies attract more clients

### 🛡️ Production-Ready Features
- **AI Code Review**: Every PR reviewed by AI + SonarCloud
- **Token Optimization**: Serena LSP reduces costs by 50% (822 avg tokens)
- **Quality Gates**: Automated testing on Ubuntu/macOS
- **Cost Control**: <$50/month infrastructure target

## 🌟 Current Status (June 2025)

### ✅ Completed
- **Sprint 1**: AI provider abstraction, cost telemetry, context engines
- **Serena Integration**: Symbol-aware context with 2x token efficiency
- **AI Pair Reviewer**: Automated code review with CI integration
- **Email Intake Agent**: AWS SES-based requirement extraction

### 🚧 In Progress
- **First Client Demo**: End-to-end delivery of real freelance project
- **Deployment Pipeline**: GitHub → Vercel automation

### 📅 Coming Next
- **Client Communication**: Automated progress updates
- **Portfolio Generation**: Case studies from completed projects
- **Billing Integration**: Stripe for payments

## 🏗️ Architecture

```mermaid
flowchart TD
    subgraph "Client Acquisition"
        A[Apollo.io Outreach] --> B[Email Reply]
        B --> C[AWS SES]
    end
    
    subgraph "Email Processing"
        C --> D[S3 Storage]
        D --> E[Lambda: Email Intake Agent]
        E --> F[DynamoDB: Conversation State]
        E --> G[Bedrock: Extract Requirements]
        G --> H[SES: Send Follow-ups]
        E --> I[SQS: Pipeline Handoff]
    end
    
    subgraph "Development Pipeline"
        I --> J[Analyser Agent]
        J --> K[Planning Agent]
        K --> L[Dev Agent + Serena LSP]
        L --> M[AI Reviewer]
        M --> |Pass| N[Auto Deploy]
        M --> |Fail| O[Block & Fix]
    end
    
    subgraph "Delivery"
        N --> P[Vercel/Netlify]
        P --> Q[Custom Domain]
        Q --> R[Client Notification]
        R --> S[Portfolio Case Study]
    end
```

## 📂 Module Overview

| Module | Status | Purpose |
|--------|--------|---------|
| **email_intake** | ✅ Active | Process client emails, extract requirements |
| **analyser** | ✅ Active | Parse requirements into structured specs |
| **planning** | ✅ Active | Convert specs into development roadmaps |
| **dev** | ✅ Active | Generate code with Serena context engine |
| **review** | ✅ Active | AI code review + static analysis |
| **deploy** | 🚧 Building | Automated deployment to hosting platforms |
| **marketing** | ✅ Active | Generate announcements and case studies |
| **coordination** | 🔄 Planned | Orchestrate multi-agent workflows |

## 🧩 Tech Stack

### Core Infrastructure
- **Cloud**: AWS (SES, Lambda, DynamoDB, SQS, Bedrock)
- **LLM**: Claude 4 Sonnet via Bedrock (primary), GPT-4 (fallback)
- **Context**: Serena LSP for symbol-aware code understanding
- **Deployment**: Vercel/Netlify with GitHub Actions

### Development Stack
- **Backend**: Python 3.13, FastAPI
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **Database**: Supabase (PostgreSQL + Auth)
- **Payments**: Stripe (planned)

### Quality & Monitoring
- **CI/CD**: GitHub Actions with matrix testing
- **Code Quality**: Ruff, Black, MyPy, SonarCloud
- **Monitoring**: CloudWatch, custom telemetry
- **Cost Tracking**: Per-call LLM logging to `logs/llm_calls.log`

## 🚀 Quick Start

### Prerequisites
```bash
# AWS CLI configured with credentials
aws configure

# Python 3.11+ and Node.js 18+
python --version
node --version
```

### Local Development
```bash
# Clone and setup
git clone <repo-url>
cd SoloPilot

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the full pipeline
make plan-dev

# With Serena context engine
CONTEXT_ENGINE=serena make dev
```

### Email Intake Setup
```bash
# 1. Configure AWS SES domain
# 2. Create S3 bucket for emails
# 3. Deploy Lambda function
cd agents/email_intake
zip -r email-intake.zip .
# Upload to Lambda

# 4. Set environment variables
REQUIREMENT_QUEUE_URL=<your-sqs-queue>
SENDER_EMAIL=<your-verified-email>
DYNAMO_TABLE=conversations
```

## ⚙️ Configuration

### Environment Variables

**AI Provider Settings:**
- `AI_PROVIDER`: bedrock (default) | fake | openai
- `BEDROCK_IP_ARN`: Claude 4 Sonnet inference profile
- `NO_NETWORK`: Force offline mode for testing

**Context Engine Settings:**
- `CONTEXT_ENGINE`: serena (recommended) | legacy | lc_chroma
- `SERENA_BALANCED_TARGET`: Token budget (default: 1500)
- `SERENA_TELEMETRY_ENABLED`: Production monitoring

**Deployment Settings:**
- `VERCEL_TOKEN`: For automated deployments
- `GITHUB_TOKEN`: For PR reviews
- `SONAR_TOKEN`: For code quality analysis

## 📋 Development Workflow

### Standard Commands
```bash
# Activate environment
source .venv/bin/activate

# Run tests
make test

# Lint and format
make lint

# Full pipeline test
make plan-dev

# Deploy to production
make deploy
```

### AI Review Workflow
```bash
# Review current code
make review

# If review passes, promote to staging
make promote

# Generate marketing announcement
make announce
```

## 🔍 Quality Assurance

### Automated Checks
1. **AI Code Review**: Every PR reviewed for bugs, security, performance
2. **Static Analysis**: Ruff, MyPy, Black formatting
3. **SonarCloud**: Security vulnerabilities and code smells
4. **Token Validation**: CI enforces <2000 tokens per call

### Manual Verification
- Review `logs/llm_calls.log` for cost monitoring
- Check `serena_telemetry.jsonl` for performance metrics
- Verify deployment smoke tests pass

## 📈 Metrics & Monitoring

### Key Performance Indicators
- **Token Usage**: 822 avg per context (target: <1500)
- **Response Time**: <3s for email processing
- **Pipeline Duration**: <10 mins from email to deployed site
- **Cost per Project**: <$5 in LLM calls

### Telemetry
When `SERENA_TELEMETRY_ENABLED=1`:
- Token usage per request
- Symbol lookup performance
- Budget violations
- Response times

## 🎯 Roadmap

### Phase 1: MVP (Current)
- ✅ Core agent pipeline
- ✅ Email intake system
- 🚧 Deployment automation
- 🚧 First client demo

### Phase 2: Scale (July 2025)
- Multi-channel intake (SMS, chat)
- Payment automation
- Client portal
- Advanced project types

### Phase 3: Growth (August 2025)
- Team collaboration features
- White-label options
- API for integrations
- Global deployment regions

## 📝 License

Proprietary - SoloPilot AI Automation