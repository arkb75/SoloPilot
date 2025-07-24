# AI Pair Reviewer CI Integration

This document describes the AI Code Review integration implemented for SoloPilot.

## Overview

The AI Pair Reviewer provides automated code review on all pull requests, working alongside SonarCloud to ensure code quality before merging.

## Components

### 1. GitHub Workflows

#### `.github/workflows/review.yml`
- **Trigger**: Pull requests to `main` or `staging` branches
- **Jobs**:
  - `ai-review`: Runs AI code review on changed files
  - `sonarcloud`: Performs static analysis and coverage checks
  - `review-status`: Combined status check for branch protection

#### `.github/workflows/ci.yml`
- Contains existing `code-review` job for backward compatibility
- `promote` job depends on review passing

### 2. Review Scripts

- **`scripts/check_review_status.py`**: Extracts pass/fail status from review reports
- **`scripts/post_review_to_pr.py`**: Posts review comments to GitHub PRs
- **`scripts/test_review_system.py`**: Local testing of review system

### 3. GitHub Integration

- **`utils/github_review.py`**: GitHub API wrapper for posting reviews
- Uses GitHub CLI (`gh`) when available
- Falls back gracefully in offline mode

### 4. Branch Protection

Configure required status checks in GitHub:
- ✅ AI Code Review / Review Status Check
- ✅ SonarCloud Analysis
- ✅ CI tests (Ubuntu and macOS)

## Usage

### Running Reviews Locally

```bash
# Review latest milestone
make review

# Test review system
python scripts/test_review_system.py
```

### CI Integration

Reviews run automatically on:
1. New pull requests
2. Updates to existing PRs
3. Manual workflow dispatch

### Review Output

The AI reviewer provides:
- **Status**: PASS or FAIL
- **Static Analysis**: Ruff, Black, isort results
- **AI Insights**: Code quality recommendations
- **Inline Comments**: Specific issues with file/line references

## SonarCloud Integration

### Badges
Add these to your README:
```markdown
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=solopilot_ai_automation&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=solopilot_ai_automation)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=solopilot_ai_automation&metric=coverage)](https://sonarcloud.io/summary/new_code?id=solopilot_ai_automation)
```

### Configuration
- Project key: `solopilot_ai_automation`
- Organization: `solopilot`
- Quality gate: Configured to fail on critical issues

## Testing

A test file with intentional issues is provided:
- `tests/test_bad_code_example.py`

This file contains:
- Security vulnerabilities (hardcoded credentials, SQL injection)
- Code quality issues (bare except, missing type hints)
- Performance problems (memory leaks, blocking I/O)
- Style violations (magic numbers, code duplication)

## Status Checks

The review creates these GitHub status checks:
1. **AI Code Review**: Individual check showing pass/fail
2. **Review Status Check**: Combined status for branch protection

## Environment Variables

- `AI_PROVIDER`: LLM provider (default: `fake` in CI)
- `NO_NETWORK`: Set to `1` for offline mode
- `GITHUB_TOKEN`: Required for posting PR comments
- `SONAR_TOKEN`: Required for SonarCloud analysis

## Next Steps

1. Configure branch protection rules in GitHub
2. Add `SONAR_TOKEN` to repository secrets
3. Update SonarCloud project settings
4. Test with a real pull request

## Troubleshooting

### Review Not Running
- Check workflow triggers in `.github/workflows/review.yml`
- Ensure PR is targeting `main` or `staging`
- Verify GitHub Actions are enabled

### Reviews Not Posting
- Check `GITHUB_TOKEN` permissions
- Verify PR has write access for actions
- Check workflow permissions in YAML

### SonarCloud Issues
- Ensure `SONAR_TOKEN` is set in secrets
- Verify project key matches configuration
- Check organization settings in SonarCloud
