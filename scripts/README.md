# Development Scripts

Utility scripts for development, testing, and CI/CD.

## Core Scripts

### Pipeline Execution
- `run_analyser.py` - Run the requirements analyzer
- `run_planner.py` - Generate development plans
- `run_dev_agent.py` - Execute code generation
- `run_solopilot.py` - Full pipeline orchestration

### Validation & Quality
- `validate_imports.py` - Verify all Python imports resolve
- `ci_token_validation.py` - Check token usage in CI
- `validate_complex_projects.py` - Test complex scenarios
- `check_review_status.py` - Parse review results

### Infrastructure
- `deploy_to_vercel.py` - Deploy projects to Vercel
- `push_artifacts.py` - Upload artifacts to S3
- `post_review_to_pr.py` - Post AI reviews to GitHub

### Development Tools
- `build_index.py` - Build search indices
- `demo_progressive_context.py` - Test context engines
- `test_email_flow.py` - Test email processing

## Usage Examples

```bash
# Run full pipeline with sample input
poetry run python scripts/run_analyser.py examples/email_proposal.json
poetry run python scripts/run_planner.py analysis/output/analyzed_requirement.json
poetry run python scripts/run_dev_agent.py analysis/planning/selected_milestone_plan.json

# Deploy to Vercel
poetry run python scripts/deploy_to_vercel.py output/dev/[timestamp]/

# Validate imports after refactoring
poetry run python scripts/validate_imports.py
```

## CI/CD Scripts

These scripts are used by GitHub Actions:
- Must handle `NO_NETWORK=1` environment variable
- Should exit with proper status codes
- Log to stdout for visibility

## Writing New Scripts

1. Add shebang: `#!/usr/bin/env python3`
2. Use argparse for CLI arguments
3. Handle errors gracefully
4. Add to Makefile if frequently used
5. Document usage in script header
