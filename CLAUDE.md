# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

**Current Status**: Full analyser → planner → dev agent workflow implemented and tested.

The analyser module contains three main components:
- `TextParser`: Handles text documents (MD, TXT, DOCX) with LLM-based extraction and keyword fallback
- `ImageParser`: Processes images using pytesseract OCR
- `SpecBuilder`: Constructs JSON specifications and generates Mermaid diagrams/wireframes

The dev agent (agents/dev/) includes:
- `DevAgent`: Transforms planning output into milestone-based code structure with skeleton implementations
- `Context7Bridge`: MCP adapter for enhanced development insights and best practices

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
make test         # Run test suite (40 tests)
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