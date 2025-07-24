# Documentation

Comprehensive documentation for the SoloPilot platform.

## Documentation Structure

### Architecture
- `ARCHITECTURE.md` - System design and component interactions
- `DEPLOYMENT.md` - Deployment procedures and infrastructure

### Development Guides
- `DEV_AGENT.md` - Development agent implementation details
- `PROGRESSIVE_CONTEXT.md` - Context engine optimization strategies
- `AWS_BEDROCK_SETUP.md` - Bedrock configuration guide

### Operations
- `MONITORING.md` - System monitoring and alerting
- `COST_OPTIMIZATION.md` - Strategies for reducing LLM costs
- `SECURITY.md` - Security best practices

### Integration Reports
- `real-serena-integration-report.md` - Serena LSP integration analysis
- `sonarcloud-integration.md` - Code quality metrics

## Contributing Documentation

When adding new documentation:

1. **Use clear headings** - Make content scannable
2. **Include examples** - Show, don't just tell
3. **Add diagrams** - Use Mermaid for flowcharts
4. **Keep it current** - Update docs with code changes
5. **Link related docs** - Help readers navigate

## Documentation Standards

### File Naming
- Use UPPERCASE for top-level guides
- Use lowercase with hyphens for reports
- Add dates to time-sensitive docs

### Content Structure
```markdown
# Title

## Overview
Brief description of the topic

## Background/Context
Why this matters

## Implementation/Details
The main content

## Examples
Practical demonstrations

## Troubleshooting
Common issues and solutions

## Related Documentation
Links to other relevant docs
```

## Automated Documentation

Some docs are auto-generated:
- API documentation from docstrings
- Cost reports from telemetry logs
- Performance metrics from benchmarks

Run `make docs` to regenerate.
