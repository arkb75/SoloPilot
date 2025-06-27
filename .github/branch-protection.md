# Branch Protection Rules

This document describes the recommended branch protection rules for SoloPilot.

## Main Branch Protection

Configure the following protection rules for the `main` branch:

### Required Status Checks
- **AI Code Review / Review Status Check** - Must pass before merging
- **SonarCloud Analysis** - Must pass quality gate
- **CI / test (ubuntu-latest, 3.13)** - All tests must pass
- **CI / test (macos-latest, 3.13)** - All tests must pass

### Pull Request Requirements
- ✅ Require pull request reviews before merging
- ✅ Dismiss stale pull request approvals when new commits are pushed
- ✅ Require review from code owners (optional)
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up to date before merging

### Additional Settings
- ✅ Include administrators (enforce rules for everyone)
- ✅ Restrict who can push to matching branches (optional)
- ❌ Allow force pushes (should be disabled)
- ❌ Allow deletions (should be disabled)

## Staging Branch Protection

Similar rules apply to the `staging` branch with relaxed requirements:
- Required status checks same as main
- Allow direct pushes from CI (GitHub Actions bot)

## How to Configure

1. Go to Settings → Branches in your GitHub repository
2. Add a branch protection rule for `main`
3. Configure the settings as described above
4. Add required status checks:
   - Search for "Review Status Check" and add it
   - Search for "SonarCloud" and add it
   - Add test jobs from CI workflow
5. Save the protection rule

## CI Integration

The AI Review workflow creates these status checks:
- **AI Code Review** - Check run that shows pass/fail status
- **Review Status Check** - Overall status combining AI review and SonarCloud

These checks will automatically appear once the workflow runs on a PR.