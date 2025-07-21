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
CONTEXT_ENGINE=serena SERENA_BALANCED_TARGET=2000 python scripts/run_dev_agent.py

# CI/Production (strict limits)
CONTEXT_ENGINE=serena SERENA_CONTEXT_MODE=MINIMAL python scripts/run_dev_agent.py
```

### Email Intake Management
- Frontend: `http://localhost:5173` after `npm run dev`
- Manual mode by default for new conversations
- Review LLM prompts in conversation details
- PDF proposals auto-generated for proposal phase

### Testing Hierarchy
1. `make lint` - Fast, run frequently
2. `NO_NETWORK=1 make test` - Offline tests
3. `make test` - Full test suite
4. `make demo` - End-to-end validation

## Success Metrics
- **Response Time**: <2 hours from email to proposal
- **Quality Score**: 0 critical bugs in production
- **Cost per Project**: <$5 in LLM + <$1 in infrastructure
- **Client Satisfaction**: 5-star reviews, repeat business
- **Portfolio Growth**: 1 case study per completed project

## Current Sprint Focus
Check Notion roadmap for active sprint items. Update status after each work session.

Remember: We're building a system that makes freelancers superhuman, not replacing them. Every line of code should serve that vision.