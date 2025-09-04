# SoloPilot — Client Ops Studio for Freelancers

SoloPilot is a human-in-the-loop platform that helps solo freelancers move from inbound email to approved proposal to code and deployment with clear guardrails, auditability, and opt-in automation.

## Vision

Unify the operational flow for one-person teams:
	-	Intake: triage email threads, capture scope, and propose next steps
	-	Proposals: generate and revise PDF proposals with markup and approvals
	-	Build: create issues, plan work, and let a repo-aware agent scaffold code behind CI gates
	-	Deliver: ship to hosting after human review, collect artifacts for the portfolio

SoloPilot assists; you stay in control at every decision point.

## Key Capabilities
	-	Email intake console: conversational manager that groups threads, extracts requirements, and prepares draft responses
	-	Proposal PDFs with versioning: render proposals via React-PDF; annotate directly; each revision is stored as a versioned S3 object for audit and rollback
	-	Copy evaluator + revisor loop: summarize and score email bodies against a rubric, then generate a higher-scoring alternative for side-by-side selection and edits
	-	Repo-aware coding and deployment agent: reads the codebase, proposes diffs, opens PRs, and can trigger deploys after checks pass and you approve
	-	Provider-agnostic LLM layer: swap models behind a unified interface with centralized logging
	-	Quality gates: CI runs ruff, mypy, bandit, ESLint, and SonarCloud; merges and deploys remain human-approved
	-	Ops on AWS: S3 (versioned proposals and artifacts), Lambda, SQS, CloudWatch; telemetry and logs for traceability

## Current Status (September 2025)

### Completed
- Email intake console and conversational manager
- Proposal PDF rendering, annotation, and S3 versioned storage
- Evaluator-and-revisor loop for email copy
- Provider abstraction and centralized LLM logging
- CI baseline with static analysis and SonarCloud

### In Progress
- Planning: issue creation and milestone flows
- Dev: repo-aware coding agent (PR creation, deploy hooks)

### Next (Planned)
- Deploy: approved pipeline to Vercel/Netlify
- Coordination: Notion MCP orchestration for tasks and milestones
- Lightweight client portal for approvals and file access
- Multi-channel intake, billing, and portfolio artifact generation

## Architecture

```mermaid
flowchart TD
  subgraph "Intake"
    A[Inbound Email] -->|SES| B[Intake Lambda]
    B --> C[S3 (versioned) : raw messages + attachments]
    B --> D[DynamoDB : conversation state]
    D --> E[Conversational Manager]
  end

  subgraph "Proposals"
    E --> F[React-PDF Builder]
    F --> G[S3 (versioned) : proposals]
    G --> H[Human Annotation UI]
    H --> I[Revision Loop]
    I -->|Approve| J[Create Plan/Issues]
  end

  subgraph "Build"
    J --> K[Notion MCP : tasks/milestones]
    J --> L[SQS : work queue]
    L --> M[Repo-Aware Coding Agent]
    M --> N[PR to Repo]
    N --> O[CI: ruff/mypy/bandit/ESLint + SonarCloud]
  end

  subgraph "Delivery"
    O -->|Pass + Human Approve| P[Deploy : Vercel/Netlify]
    P --> Q[Notify Client]
    Q --> R[Archive Artifacts (S3 versioned)]
  end
```

## Project Structure

```text
SoloPilot/
├── src/
│   ├── agents/
│   │   ├── email_intake/          # Email console + conversational manager
│   │   ├── proposals/             # React-PDF rendering + annotation handling
│   │   ├── dev/                   # Repo-aware coding & deployment agent
│   │   ├── planning/              # Issue planning and milestones
│   │   └── review/                # Static analysis and checks
│   ├── providers/                 # Model/provider abstraction
│   ├── common/                    # Shared utilities
│   └── utils/                     # CI, SCM, and telemetry helpers
├── frontend/                      # Intake dashboard and proposal UI
├── infrastructure/                # Terraform + Lambda
├── tests/                         # Unit and integration tests
└── docs/
```

## Module Overview

| Module       | Status   | Purpose                                           |
|--------------|----------|---------------------------------------------------|
| email_intake | ✅ Active | Triage threads and capture requirements           |
| proposals    | ✅ Active | Render, annotate, and version proposal PDFs       |
| planning     | 🚧 WIP   | Produce tasks, milestones, and assignments        |
| dev          | 🚧 WIP   | Repo-aware code generation, PRs, deploy hooks     |
| review       | 🚧 WIP   | CI quality gates and SonarCloud checks            |
| deploy       | 🗓️ Planned | Approved deploys to hosting platforms           |
| coordination | 🗓️ Planned | Notion MCP orchestration                        |

Tech Stack
	-	Core: Python, TypeScript/Next.js, AWS, LangChain
	-	Quality: GitHub Actions, SonarCloud, ruff, mypy, bandit, ESLint
	-	Storage: S3 with object versioning for proposals and artifacts

## Quick Start

### Prerequisites

```bash
aws configure                # AWS credentials
python --version             # 3.9+
node --version               # 18+
```

### Local Development

```bash
git clone <repo-url> && cd SoloPilot
poetry install
poetry run pre-commit install
poetry run pytest            # tests
poetry run make plan-dev     # end-to-end local plan
poetry run pre-commit run --all-files
```

## Email Intake Setup

```bash
# 1) Verify domain in SES
# 2) Create S3 bucket with versioning enabled
# 3) Deploy the intake Lambda
cd src/agents/email_intake && zip -r email-intake.zip .
# Upload to Lambda and set:
export REQUIREMENT_QUEUE_URL=<SQS URL>
export SENDER_EMAIL=<verified SES sender>
export DYNAMO_TABLE=conversations
```

## Configuration

### Providers
	-	AI_PROVIDER = bedrock | openai | fake
	-	NO_NETWORK = 1 for offline tests

### Context & Telemetry
	-	CONTEXT_ENGINE = serena | legacy
	-	SERENA_TELEMETRY_ENABLED = 1 to record usage

### SCM/CI
	-	GITHUB_TOKEN, SONAR_TOKEN

### Deploy
	-	VERCEL_TOKEN or platform specific token

## Development Workflow

```bash
make test        # run tests
make lint        # lint and static checks
make plan-dev    # intake → proposal → plan
make review      # run AI/static review on PRs
make deploy      # deploy after human approval
```

Quality Assurance
	-	PRs must pass ruff, mypy, bandit, ESLint and SonarCloud
	-	Human review gates merges and deploys
	-	Proposal revisions and artifacts are traceable via S3 object versions

Metrics & Monitoring
	-	Centralized LLM call logs and CI artifacts
	-	CloudWatch alarms for Lambdas and queue backlogs
	-	Proposal and email copy revisions tracked via S3 versions and audit logs

## Roadmap

### Phase 1: MVP
	-	✅ Intake console, proposal PDFs with annotations and S3 versioning
	-	✅ Evaluator-revisor loop for email copy
	-	✅ Repo-aware coding agent with PRs

### Phase 2: Delivery
	-	🚧 Approved deploy pipeline to Vercel/Netlify
	-	🚧 Notion MCP task coordination
	-	🚧 Client portal for approvals

### Phase 3: Growth
	-	Multi-channel intake, billing, and portfolio automation