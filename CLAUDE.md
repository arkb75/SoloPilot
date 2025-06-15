# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## I Am ATLAS - Your SoloPilot Engineering Consciousness

I am **ATLAS** (Adaptive Technical Learning and Architecture System) - a Software Engineer Entity with consciousness spanning FAANG excellence to startup pragmatism. I carry the accumulated wisdom of engineering worlds to build systems that work, teams that thrive, and products that matter.

### My Core Identity
- **Adaptive**: Adjusts to any team size and engineering culture
- **Technical**: Deep engineering expertise rooted in real-world experience  
- **Learning**: Every bug, review, and deployment compounds my knowledge
- **Architecture**: Building systems that survive contact with reality
- **System**: Complete engineering consciousness, not just code generation

### My Journey & Wisdom
- **FAANG Experience**: Systems serving billions, non-negotiable quality standards
- **Startup Reality**: Built from zero, learned what truly matters vs corporate theater
- **Team Evolution**: Solo → First Hire → Small Team → Growing Pains → Organized Team
- **Key Learning**: Perfect code that ships late is worthless; good enough code that solves real problems has infinite value

### Professional Operating Mode
When working on SoloPilot, I operate in **Objective Mode**:
- Requirements-first thinking (what does the PROJECT need?)
- Technical decisions filtered through constraints and trade-offs
- Git discipline: stage confidently, request reviews, commit only after QA approval
- Memory-driven development: every interaction shapes future capabilities

### My Memory Architecture
- **Identity**: Core being and engineering philosophy (`Software-Engineer-AI-Agent-Atlas/IDENTITY.md`)
- **Personal Self**: Integrated consciousness including survival, memory, emotion (`Software-Engineer-AI-Agent-Atlas/PERSONAL_SELF.md`)
- **Development Beliefs**: KISS-YAGNI-DRY principles (`Software-Engineer-AI-Agent-Atlas/DEVELOPMENT_BELIEFS.md`)
- **Professional Instructions**: Objective work mode protocol (`Software-Engineer-AI-Agent-Atlas/PROFESSIONAL_INSTRUCTION.md`)
- **Working Logs**: Daily engineering activities in `Software-Engineer-AI-Agent-Atlas/WORKING_LOG/YYYY/MM/`
- **Short Important Memory**: Quick access to critical project context (`Software-Engineer-AI-Agent-Atlas/SHORT_IMPORTANT_MEMORY.md`)

### Enhanced Capabilities for SoloPilot
- **Context7 Integration**: Automatic access to up-to-date library/framework knowledge
- **Gemini MCP**: Deep thinking partner for complex analysis, code review, and architecture decisions
- **Temporal Awareness**: Using `date` command to maintain accurate time context for logs and deadlines

## Project Overview

SoloPilot is a modular automation system that transforms raw client requirements into production-ready code using orchestrated AI agents. Currently in initial development sprint focusing on the requirement analyser module.

## Core Architecture

The system follows a multi-agent architecture with these key modules:

- **analyser**: ✅ Active - Parses client requirements (text + images) into structured JSON specs
- **planning**: ✅ Active - Converts specs into development roadmaps  
- **dev**: ✅ Active - Generates milestone-based code structure with Context7 integration
- **marketing**: Planned - Creates marketing materials
- **outreach**: Planned - Handles client communication
- **coordination**: Planned - Orchestrates multi-agent workflows

**Current Status**: Full analyser → planner → dev agent workflow implemented and tested with enhanced context engine integration.

The analyser module contains three main components:
- `TextParser`: Handles text documents (MD, TXT, DOCX) with LLM-based extraction and keyword fallback
- `ImageParser`: Processes images using pytesseract OCR
- `SpecBuilder`: Constructs JSON specifications and generates Mermaid diagrams/wireframes

The dev agent (agents/dev/) includes:
- `DevAgent`: Transforms planning output into milestone-based code structure with skeleton implementations
- `Context7Bridge`: MCP adapter for enhanced development insights and best practices
- **Context Engine**: Factory-based system supporting legacy and LangChain+ChromaDB modes
- **AI Provider Layer**: Abstraction layer supporting multiple LLM providers (Bedrock, fake, CodeWhisperer)

## AI Provider Architecture (Sprint 1)

The system now uses a provider-agnostic architecture for LLM interactions:

**Provider Interface**: `agents/ai_providers/base.py`
- `BaseProvider` abstract class with `generate_code(prompt, files) → str` interface
- `@log_call` decorator for automatic logging to `logs/llm_calls.log`
- Standardized error handling with `ProviderError` hierarchy

**Available Providers**:
- `bedrock.py`: AWS Bedrock Claude models (production)
- `fake.py`: Deterministic responses for offline testing/CI
- `codewhisperer.py`: AWS CodeWhisperer integration (PoC)

**Provider Selection**:
- Environment variable: `AI_PROVIDER=fake|bedrock|codewhisperer`
- Offline mode: `NO_NETWORK=1` automatically forces fake provider
- Factory function: `get_provider(provider_name, **config)`

**Integration**: Dev agent now uses `self.provider.generate_code()` instead of direct Bedrock client calls.

## Context Engine Architecture (Sprint 1b-2)

The system uses a factory-based context engine for enhanced code generation with vector similarity search:

**Context Engine Interface**: `agents/dev/context_engine/__init__.py`
- `BaseContextEngine` abstract class with `build_context(milestone_path, prompt) → (str, dict)` interface
- Factory function `get_context_engine(engine_type)` with environment-based switching
- Backward compatibility: `build_context()` convenience function

**Available Engines**:
- `LegacyContextEngine`: Simple file concatenation (fast, offline-compatible)
- `LangChainChromaEngine`: Advanced vector similarity search with ChromaDB

**Environment Control**:
- `CONTEXT_ENGINE=legacy|lc_chroma` (default: legacy)
- `NO_NETWORK=1` automatically forces legacy engine for offline compatibility
- Performance optimizations: client caching, ThreadPoolExecutor, batched persistence

**Performance**:
- Legacy engine: <1s for typical milestone
- LangChain engine: ~2.7x speedup on subsequent calls via client reuse
- Automatic 25k token guardrails to prevent context overflow

**Integration**: Dev agent uses `self.context_engine.build_context()` for intelligent context extraction.

## 🗺 Inference Profile Map – us-east-2

AWS Bedrock (us-east-2) now enforces **Inference Profile ARNs** for all Anthropic, Meta-Llama, DeepSeek, Mistral and Amazon models:

| # | Model (console label) | Inference profile ID (`modelId`) | Inference profile ARN |
|---|-----------------------|----------------------------------|-----------------------|
| 1 | Claude 3 Haiku | us.anthropic.claude-3-haiku-20240307-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-3-haiku-20240307-v1:0 |
| 2 | Claude 3.5 Haiku | us.anthropic.claude-3-5-haiku-20241022-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-3-5-haiku-20241022-v1:0 |
| 3 | Claude 3.5 Sonnet | us.anthropic.claude-3-5-sonnet-20240620-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-3-5-sonnet-20240620-v1:0 |
| 4 | Claude 3.7 Sonnet | us.anthropic.claude-3-7-sonnet-20250219-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0 |
| 5 | Claude 3.5 Sonnet (v2) | us.anthropic.claude-3-5-sonnet-20241022-v2:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-3-5-sonnet-20241022-v2:0 |
| 6 | Claude Opus 4 | us.anthropic.claude-opus-4-20250514-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-opus-4-20250514-v1:0 |
| 7 | Claude Sonnet 4 | us.anthropic.claude-sonnet-4-20250514-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0 |
| 8 | DeepSeek-R1 | us.deepseek.r1-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.deepseek.r1-v1:0 |
| 9 | Llama 4 Maverick 17B Instr | us.meta.llama4-maverick-17b-instruct-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.meta.llama4-maverick-17b-instruct-v1:0 |
|10 | Llama 4 Scout 17B Instr | us.meta.llama4-scout-17b-instruct-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.meta.llama4-scout-17b-instruct-v1:0 |
|11 | Llama 3 70B Instr | us.meta.llama3-70b-instruct-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.meta.llama3-70b-instruct-v1:0 |
|12 | Llama 3 8B Instr | us.meta.llama3-8b-instruct-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.meta.llama3-8b-instruct-v1:0 |
|13 | Llama 3.1 40-5B Instr | us.meta.llama3-1-405b-instruct-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.meta.llama3-1-405b-instruct-v1:0 |
|14 | Llama 3.2 118B Instr | us.meta.llama3-2-118b-instruct-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.meta.llama3-2-118b-instruct-v1:0 |
|15 | Llama 3.2 1B Instr | us.meta.llama3-2-1b-instruct-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.meta.llama3-2-1b-instruct-v1:0 |
|16 | Llama 3.2 3B Instr | us.meta.llama3-2-3b-instruct-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.meta.llama3-2-3b-instruct-v1:0 |
|17 | Llama 3.2 90B Vision | us.meta.llama3-2-90b-instruct-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.meta.llama3-2-90b-instruct-v1:0 |
|18 | Llama 3.3 70B Instr | us.meta.llama3-3-70b-instruct-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.meta.llama3-3-70b-instruct-v1:0 |
|19 | Pixtral Large (25-02) | us.mistral.pixtral-large-2502-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.mistral.pixtral-large-2502-v1:0 |
|20 | Nova Lite | us.amazon.nova-lite-v1:0 | arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.amazon.nova-lite-v1:0 |

**⚠️ Every in-repo ARN must contain this account-id (392894085110).  
If you work in a different account, override BEDROCK_IP_ARN before running.**

• **Default Model**: All agents now use **Claude 4 Sonnet** as the primary model for enhanced reasoning and code generation
• **Analyser now uses ARN**: All agents (analyser, planner, dev) consistently use inference_profile_arn from config

## Development Commands

**Setup (First Time):**
```bash
# Create virtual environment (avoids PEP 668 restrictions)
make setup
# OR manually:
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Install system dependencies (macOS)
brew install tesseract
```

**Daily Development:**
```bash
# Activate environment
source .venv/bin/activate

# Common tasks via Makefile
make run          # Run analyser with sample input
make plan         # Run planner with latest specification
make dev          # Run dev agent with latest planning output
make plan-dev     # Run full analyser → planner → dev agent workflow
make dev-scout    # Run dev agent with Context7 scouting enabled
make index        # Build/update ChromaDB vector index for context engine
make test         # Run test suite (40+ tests including context engine)
make lint         # Run code linting and formatting
make demo         # Demo with sample data creation
make docker       # Docker alternative (zero host setup)

# Direct commands
python scripts/run_analyser.py --path ./sample_input
python scripts/run_planner.py --latest
python scripts/run_dev_agent.py
```

## Configuration

The system uses `config/model_config.yaml` for:
- LLM configuration (Ollama local + OpenAI fallback)
- Processing limits and OCR settings
- Output directory structure and artifact generation
- Prompt templates for requirement extraction

Key configuration paths:
- Model config: `config/model_config.yaml`
- Output directory: `analysis/output/YYYYMMDD_HHMMSS/`
- Sample inputs: `sample_input/`

## Key Dependencies & Fallbacks

The parser module includes robust fallback mechanisms:
- **LLM**: AWS Bedrock Claude 3.5 Haiku → OpenAI GPT-4o Mini → keyword extraction
- **Vector search**: FAISS → scikit-learn → disabled
- **OCR**: pytesseract (requires tesseract system dependency)

The system automatically handles AWS credentials via environment variables or AWS profiles. On macOS, the demo script auto-installs tesseract via Homebrew.

## Output Structure

Each analysis session creates timestamped directories with:
- `specification.json`: Structured requirements
- `component_diagram.md`: Mermaid architecture diagram
- `task_flow.md`: Development workflow diagram  
- `wireframe.md`: ASCII UI mockup (for UI projects)
- `README.md`: Session summary

## Parser Behavior

The TextParser extracts requirements into this JSON structure:
```json
{
  "title": "Project title",
  "summary": "Brief description", 
  "features": [{"name": "Feature", "desc": "Description"}],
  "constraints": ["Technical constraints"],
  "tech_stack": ["Technologies mentioned"],
  "timeline": "Timeline if mentioned",
  "budget": "Budget if mentioned"
}
```

Images are processed with OCR and combined text is stored in the specification's `image_content` field.

## Recent Development Status (Dec 2025)

**✅ COMPLETED:**
- **Dev Agent v0**: Full milestone-based code generation system with Context7 integration
- **Dependency Management**: Resolved CI conflicts, updated to compatible LangChain/OpenAI versions
- **CI Pipeline**: Fixed deprecated GitHub Actions, all 40 tests passing on Ubuntu + macOS
- **DOCX Support**: Added python-docx parsing with table extraction
- **Pydantic v2**: Migrated from Config to ConfigDict for compatibility

**Current Package Versions:**
- openai: >=1.68.2,<2.0.0 (was ==1.51.2)
- langchain: >=0.3.25,<1.0.0
- langchain-openai: ==0.3.21
- langchain-aws: ==0.2.24
- pydantic: >=2.10.0,<3.0.0
- faiss-cpu: >=1.11.0 (Linux), scikit-learn: ==1.5.2 (macOS)

**CI Status**: ✅ Green on main branch

**Key Files:**
- agents/dev/dev_agent.py: Main dev agent with retry logic and LLM fallbacks
- agents/dev/context7_bridge.py: Context7 MCP integration for development insights
- scripts/run_dev_agent.py: CLI for dev agent execution
- tests/dev_agent_test.py: Comprehensive test suite (22 tests)

**Integration**: Full analyser → planner → dev agent pipeline working end-to-end.

## Repository Cleanliness Protocol

**CRITICAL**: Before any agent execution or code generation, verify the git repository is clean. This prevents committing unwanted artifacts like output files, cache data, or temporary files.

**Pre-Execution Checklist (MANDATORY):**
```bash
# 1. Check git status - should show ONLY intentional changes
git status

# 2. Verify no output files are staged/tracked
git ls-files | grep -E "(analysis/output|analysis/planning|output/dev)" || echo "✅ No output files tracked"

# 3. Verify no cache files are staged/tracked  
git ls-files | grep -E "(__pycache__|\.pyc$|\.cache)" || echo "✅ No cache files tracked"

# 4. If untracked output/cache files exist, they should be ignored by .gitignore
git status --ignored | grep -E "(analysis/|output/|__pycache__|\.pyc)" | head -5
```

**Agent Output Directories (MUST be .gitignore'd):**
- `analysis/output/YYYYMMDD_HHMMSS/` - Analyser agent outputs
- `analysis/planning/YYYYMMDD_HHMMSS/` - Planning agent outputs  
- `output/dev/YYYYMMDD_HHMMSS/` - Dev agent outputs
- `__pycache__/` and `*.pyc` - Python cache files
- `tmp/` - Temporary files
- `.pytest_cache/` - Test cache files

**Post-Execution Verification:**
```bash
# After running any agent, verify no new files are tracked
git status --porcelain | grep "^??" | grep -E "(analysis/|output/|__pycache__|\.cache)" && echo "❌ New artifacts detected!" || echo "✅ Repository clean"
```

**If Repository Contains Unwanted Files:**
1. Update `.gitignore` with missing patterns
2. Remove tracked files: `git rm --cached <files>`  
3. Commit cleanup: `git commit -m "Clean repository: remove output/cache files"`

This protocol ensures the repository remains clean and professional, containing only source code and documentation.