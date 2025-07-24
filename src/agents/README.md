# AI Agents

This directory contains the autonomous AI agents that power the SoloPilot platform.

## Agent Pipeline

```
Email → Analyser → Planner → Dev → Review → Deploy → Marketing
```

## Agents

### analyser/
Parses client requirements from various sources (email, documents, images) into structured specifications.

### dev/
Generates code using context-aware engines (Serena LSP) to minimize token usage while maintaining quality.

### email_intake/
Handles incoming client emails, maintains conversation state, and generates proposals.

### marketing/
Creates portfolio content, case studies, and social media posts from completed projects.

### planning/
Converts requirements into actionable development plans with milestones and tasks.

### review/
Performs AI-powered code review with quality gates and integrates with CI/CD.

## Communication

Agents communicate through JSON/YAML files with standardized schemas. Each agent:
- Reads input from previous stage
- Processes using AI providers
- Writes timestamped output
- Logs telemetry for cost tracking

## Testing

Each agent has corresponding tests in `/tests/`. Run with:
```bash
poetry run pytest tests/[agent_name]_test.py
```
