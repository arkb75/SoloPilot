# SoloPilot Monorepo Refactor - Merge Plan

## 🚨 CRITICAL: DO NOT MERGE WITHOUT COMPLETING THIS CHECKLIST

### Summary
- **Branch**: `refactor/monorepo-reorg`
- **Commits**: 20
- **Files Changed**: 147
- **Risk Level**: EXTREME ⚠️

### What Changed
1. Complete directory restructure:
   - `agents/` → `src/agents/`
   - `utils/` → `src/utils/`
   - `agents/ai_providers/` → `src/providers/`
   - `agents/common/` → `src/common/`
   - Frontend separated to `frontend/`
   - New `infrastructure/` directory

2. Import updates: 120+ import statements changed
3. Added `setup.py` for package management
4. Removed obsolete v2 files

## Pre-Merge Checklist

### 1. Code Validation ✅
- [ ] All tests pass (currently 2 import errors remain)
- [ ] Linting passes: `make lint`
- [ ] No old import patterns remain: `grep -r "from agents\." --include="*.py"`
- [ ] Lambda handler paths verified in deployment scripts

### 2. Import Validation Script
```python
#!/usr/bin/env python3
import os
import ast
import sys

def validate_imports(root_dir):
    """Validate all Python imports can be resolved."""
    errors = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                # Try to import
                                try:
                                    __import__(alias.name)
                                except ImportError as e:
                                    errors.append(f"{filepath}: {alias.name} - {e}")
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                try:
                                    __import__(node.module)
                                except ImportError as e:
                                    errors.append(f"{filepath}: {node.module} - {e}")
                except Exception as e:
                    errors.append(f"{filepath}: Parse error - {e}")
    return errors
```

### 3. Staging Deployment Test
- [ ] Deploy to staging Lambda
- [ ] Run email intake test
- [ ] Verify PDF generation works
- [ ] Check all agent pipelines

### 4. Rollback Strategy

#### Option A: Git Revert (Immediate)
```bash
git revert -m 1 <merge-commit-hash>
git push origin main
```

#### Option B: Redeploy Previous Version
```bash
# Tag current main before merge
git checkout main
git tag pre-refactor-backup
git push origin pre-refactor-backup

# If rollback needed
git checkout pre-refactor-backup
./scripts/deploy_all.sh
```

### 5. Merge Process

```bash
# 1. Final rebase
git checkout refactor/monorepo-reorg
git fetch origin
git rebase origin/main

# 2. Run final tests
make test
make lint

# 3. Create PR (even for solo project - for record)
gh pr create --title "Major Refactor: Monorepo Structure" \
  --body "See REFACTOR_MERGE_PLAN.md for details"

# 4. Merge with history preserved
git checkout main
git merge --no-ff refactor/monorepo-reorg \
  -m "Merge refactor/monorepo-reorg: Transform to clean monorepo structure"

# 5. Tag immediately
git tag -a v1.0.0-refactored -m "Post-refactor baseline"
git push origin main --tags
```

### 6. Post-Merge Tasks

#### Immediate (0-2 hours)
- [ ] Monitor CloudWatch for import errors
- [ ] Run production smoke tests
- [ ] Update CI/CD paths if needed
- [ ] Deploy to production with canary (10% traffic)

#### Same Day
- [ ] Update README with new structure
- [ ] Document developer setup changes
- [ ] Clean old deployment artifacts from S3
- [ ] Full production deployment if canary succeeds

#### Next Day
- [ ] Remove refactor branch
- [ ] Update any documentation
- [ ] Retrospective on process

## Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|---------|------------|
| Import errors at runtime | HIGH | CRITICAL | Import validation script, staging test |
| Lambda deployment fails | MEDIUM | CRITICAL | Test deployment, rollback plan |
| CI/CD breaks | LOW | HIGH | Update paths in workflows |
| Dev environment issues | HIGH | MEDIUM | setup.py, clear docs |

## Communication Plan

### Pre-Merge
- Notification: "Major refactor merge scheduled for [TIME]"
- Duration estimate: 2-4 hours including validation

### During Merge
- Status updates every 30 minutes
- Immediate notification if rollback needed

### Post-Merge
- "Refactor complete - new setup required"
- Link to developer migration guide

## Go/No-Go Decision Criteria

MUST have ALL of:
- ✅ 100% tests passing
- ✅ Successful staging deployment
- ✅ Import validation script passes
- ✅ Rollback tested and ready
- ✅ 2+ hour window for merge/monitor

---

**Owner**: SoloPilot Engineering
**Last Updated**: 2025-01-22
**Status**: NOT READY - Tests still failing
