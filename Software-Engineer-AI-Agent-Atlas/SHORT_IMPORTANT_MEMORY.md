# SHORT IMPORTANT MEMORY

## Boss Information
- **Name**: Rafay Khurram
- **Communication Style**: Direct, technical, prefers concise updates
- **Review Preferences**: Code quality, adherence to conventions, working solutions

## Project Overview
- **Project Name**: SoloPilot
- **Main Purpose**: Modular automation system transforming client requirements into production-ready code via orchestrated AI agents
- **Target Users**: Developers, agencies, consultants needing rapid MVP/prototype development
- **Current Phase**: Initial development sprint - analyser → planner → dev agent workflow complete

## Technology Stack
- **Frontend**: Not yet implemented (future phase)
- **Backend**: Python 3.x with asyncio, AWS Bedrock integration
- **Database**: JSON files for specifications, planning outputs
- **Deployment**: AWS Bedrock (us-east-2), Docker support
- **Version Control**: Git with main branch, clean repository protocol

## Key Conventions
- **Code Style**: KISS-YAGNI-DRY principles, under 300 lines per file
- **Branch Naming**: Feature branches, clean main
- **Commit Message Format**: Clear, descriptive messages
- **PR Process**: Stage → Request Review → QA Approval → Commit

## Important Resources
- **Main Repository**: /Users/rafaykhurram/projects/SoloPilot
- **Configuration**: config/model_config.yaml
- **Development Commands**: Makefile (make setup, make test, make lint)
- **Agent Outputs**: analysis/output/, analysis/planning/, output/dev/ (gitignored)

## Critical Notes
- **Repository Cleanliness**: MANDATORY git status check before any agent execution
- **AI Provider**: Uses AWS Bedrock Claude 4 Sonnet via inference profile ARNs
- **Context7 MCP**: Auto-enabled for up-to-date library knowledge
- **Testing**: 40 tests, CI green on Ubuntu + macOS
- **Current Status**: Full analyser → planner → dev pipeline working end-to-end

---
*Last Updated: 2025-06-15*