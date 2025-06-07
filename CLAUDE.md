# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SoloPilot is a modular automation system that transforms raw client requirements into production-ready code using orchestrated AI agents. Currently in initial development sprint focusing on the requirement analyser module.

## Core Architecture

The system follows a multi-agent architecture with these key modules:

- **analyser**: Active - Parses client requirements (text + images) into structured JSON specs
- **planning**: Planned - Converts specs into development roadmaps  
- **dev**: Planned - Generates production-ready code
- **marketing**: Planned - Creates marketing materials
- **outreach**: Planned - Handles client communication
- **coordination**: Planned - Orchestrates multi-agent workflows

The analyser module is the current focus and contains three main components:
- `TextParser`: Handles text documents (MD, TXT, DOCX) with LLM-based extraction and keyword fallback
- `ImageParser`: Processes images using pytesseract OCR
- `SpecBuilder`: Constructs JSON specifications and generates Mermaid diagrams/wireframes

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
make test         # Run test suite  
make demo         # Demo with sample data creation
make docker       # Docker alternative (zero host setup)

# Direct commands
python scripts/run_analyser.py --path ./sample_input
python scripts/run_analyser.py --path ./path/to/file.md --config ./config/model_config.yaml
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
- **LLM**: Ollama (local) → OpenAI (cloud) → keyword extraction
- **Vector search**: FAISS → scikit-learn → disabled
- **OCR**: pytesseract (requires tesseract system dependency)

On macOS, the demo script auto-installs tesseract via Homebrew and handles dependency fallbacks.

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