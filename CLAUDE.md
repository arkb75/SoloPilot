# CLAUDE.md

## Mission
Transform freelance development by automating everything except client relationships. Enable solo developers to deliver production-ready software from email requests at <$50/month infrastructure cost.

## Core Vision
1. **Freelancer Empowerment**: Scale from 1 to 10+ clients without hiring
2. **Quality Without Compromise**: Every deployment meets professional standards
3. **Cost-Effective**: Infrastructure that doesn't eat profits ($50/month target)
4. **Client-Centric**: Automate code, preserve human relationships
5. **Portfolio Growth**: Every project becomes a marketing asset

## AI Collaboration Rules

### MCP Partners
- **Context7** (`mcp__context7__*`): Use automatically for library documentation. When implementing features with specific frameworks/libraries:
  - ALWAYS check for latest API changes
  - Get implementation examples
  - Verify best practices
  - Especially critical for: React hooks, Next.js app router, Tailwind classes, AWS SDK changes

- **ChatGPT** (`mcp__chatgpt-mcp__chatgpt`): Architecture reasoning partner. Consult for:
  - Complex architectural decisions
  - Trade-off analysis
  - Design pattern selection
  - "Should we..." questions

- **Gemini** (`mcp__gemini__*`): Deep analysis and verification. Use for:
  - Large codebase analysis
  - Pre-commit validation
  - Security audits
  - "Did we miss anything?" checks

### Notion Roadmap Management
**CRITICAL**: Update the Engineering Roadmap (`213eec8b-5476-80ca-9971-ca7a98cffcd5`) after EVERY significant task:
- Mark completed items as "Done"
- Add new discovered tasks
- Update priorities based on progress
- Track blockers and dependencies

## Architecture Principles

### Agent Pipeline
```
[Email Intake] → Analyser → Planner → Dev → Review → Deploy/Package
[Marketing]    ↗

Two intake streams:
- Email: Client inquiries via conversational AI
- Marketing: Portfolio/social media lead generation
```
Each agent is independent, communicates via JSON/YAML, uses timestamped outputs.

### Provider Abstraction
All LLM calls through standardized interface:
- `BaseProvider.generate_code()`
- `@log_call` decorator for telemetry
- Token budgets: MINIMAL(800) → BALANCED(1500) → COMPREHENSIVE(unlimited)

### Quality Gates
1. **Dev**: Lint-fix before generation
2. **Review**: Static analysis + AI review
3. **CI**: Offline-green requirement
4. **Deploy**: Staging → Production workflow

## Development Rules

### File Management
- ✅ Run all scripts you create yourself
- ✅ Delete one-time use scripts after execution
- ❌ NEVER create v2, v3 files - edit existing ones
- ❌ NEVER commit output directories

### Git Discipline
```bash
# Before ANY work
git status  # Must be clean
git pull    # Stay synchronized

# After changes
make lint   # Must pass
make test   # Must pass offline
git add -p  # Selective staging
```

### Cost Control
- Log every LLM call to `logs/llm_calls.log`
- Enforce token budgets in context engines
- Monitor `serena_telemetry.jsonl` for usage
- Target: <$5 LLM cost per project

## Practical Tips

### Context Engine Selection
```bash
# Development (generous context)
CONTEXT_ENGINE=serena SERENA_BALANCED_TARGET=2000 poetry run python scripts/run_dev_agent.py

# CI/Production (strict limits)
CONTEXT_ENGINE=serena SERENA_CONTEXT_MODE=MINIMAL poetry run python scripts/run_dev_agent.py
```

### Email Intake Management
- Frontend: `http://localhost:5173` after `npm run dev` (DO NOT attempt to deploy - runs locally only)
- Manual mode by default for new conversations
- Review LLM prompts in conversation details
- PDF proposals auto-generated for proposal phase and stored in S3
- Proposals viewable in frontend with version history

### Testing Hierarchy
1. `poetry run pre-commit run --all-files` - Linting and formatting
2. `NO_NETWORK=1 poetry run pytest` - Offline tests
3. `poetry run pytest` - Full test suite with coverage
4. `poetry run make demo` - End-to-end validation

## Success Metrics
- **Response Time**: <2 hours from email to proposal
- **Quality Score**: 0 critical bugs in production
- **Cost per Project**: <$5 in LLM + <$1 in infrastructure
- **Client Satisfaction**: 5-star reviews, repeat business
- **Portfolio Growth**: 1 case study per completed project

## Current Sprint Focus
Check Notion roadmap for active sprint items. Update status after each work session.

### Major Refactoring Completed (Jan 2025)

#### Project Structure Reorganization
**Problem**: Codebase was a "code dumpster" with 1,462 `__pycache__` directories, duplicate files (v2, v3), and mixed concerns.

**Solution**: Complete monorepo reorganization following Python best practices:
```
SoloPilot/
├── src/                    # All source code (NEW)
│   ├── agents/            # Agent implementations
│   ├── providers/         # AI provider implementations (renamed from ai_providers)
│   ├── common/           # Shared utilities
│   └── utils/            # General utilities
├── frontend/             # Frontend applications
├── infrastructure/       # Deployment & IaC
├── tests/               # All tests in one place
├── examples/            # Example inputs (renamed from sample_input)
├── scripts/             # Development & CI scripts
├── docs/                # Documentation
└── pyproject.toml       # Poetry dependency management (NEW)
```

#### Development Improvements
1. **Migrated to Poetry**: Modern dependency management with lock file
2. **Pre-commit Hooks**: Automatic code quality checks
   - Black, isort, Ruff for formatting and linting
   - MyPy for type checking
   - Bandit for security scanning
   - Custom import validation
3. **Enhanced CI/CD**:
   - Matrix testing on Python 3.9-3.12
   - Type checking job
   - Pre-commit integration
   - Poetry-based workflows
4. **Import Convention**: All imports now use `src.` prefix:
   ```python
   from src.agents.dev import dev_agent
   from src.providers.bedrock import BedrockProvider
   ```

#### Quick Start (Updated)
```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Install pre-commit hooks
poetry run pre-commit install

# Run commands with Poetry
poetry run pytest
poetry run python scripts/run_dev_agent.py
```

### Email Intake System - Recent Changes (Jan 2025)

#### Problem Solved: PDF Proposals Not Attaching
**Issue**: In manual mode, proposals were showing detailed text instead of attaching PDFs.
**Root Cause**: PDF generation was failing due to missing `PDF_LAMBDA_ARN` env var or PDF Lambda errors. The fallback was sending the full proposal text instead of a minimal message.

#### Changes Made:
1. **Separated Email Body from Proposal Content** (`conversational_responder.py`)
   - LLM now generates two outputs: minimal email body + detailed proposal content
   - Email says "Please find the proposal attached" while PDF contains full details

2. **Enhanced Error Handling** (`api/lambda_api.py`)
   - Better logging with conversation ID and client email
   - Proper fallback messages when PDF fails
   - ERROR level logging (not WARNING) for monitoring

3. **Fixed Email Metadata** (`email_sender.py`, `lambda_function.py`)
   - Extracts structured email_body when available
   - Falls back to llm_response for backward compatibility
   - Includes client_name and sender_name for personalization

4. **Removed Hardcoded Calendly Links**
   - Only included when client explicitly requests a call
   - Added `_check_if_call_requested()` method

#### Next Steps (TODO):
1. **Verify Infrastructure**
   - Check `PDF_LAMBDA_ARN` is set in Lambda environment
   - Verify IAM permissions for PDF Lambda invocation
   - Add CloudWatch alarms for PDF generation failures

2. **Monitor & Debug**
   - Watch logs for specific error patterns
   - Track PDF success/failure rates
   - Consider adding metrics for monitoring

3. **Future Improvements**
   - Add unit tests for PDF success/failure paths
   - Consider caching PDF generation for identical proposals
   - Implement retry logic for transient PDF failures


## AWS Configuration
- **AWS Account**: 392894085110 (use `--profile root`)
- **Region**: us-east-2
- **Lambda Functions**: solopilot-email-intake, email-agent-api, solopilot-document-generation
