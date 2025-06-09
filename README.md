# ☑️ SoloPilot – A-to-Z Freelance Automation System

[![CI Status](https://github.com/your-username/SoloPilot/workflows/CI/badge.svg)](https://github.com/your-username/SoloPilot/actions)

**SoloPilot** is a modular automation system that transforms raw client requirements into production-ready code. This system orchestrates multiple AI agents to handle the complete freelance development lifecycle.

## 🚀 Quick Start

### Local Development (Recommended)

```bash
# Clone and setup
git clone <repo-url>
cd SoloPilot

# Create virtual environment (avoids PEP 668 restrictions)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install system dependencies (macOS)
brew install tesseract

# Run requirement analysis
python scripts/run_analyser.py --path ./sample_input
```

### Docker Alternative (Zero Host Setup)

```bash
# Start local stack with Ollama + analyser
docker-compose up --build

# The compose file handles all dependencies automatically
```

## 🏗️ Architecture

```mermaid
flowchart TD
    subgraph "Input Processing"
        A[Client Briefs<br/>Text + Images] --> B[Requirement Analyser]
    end
    
    subgraph "Planning & Development"
        B --> C[Planning Agent JSON]
        C --> D[Development Agent]
        D --> E[Code Generation]
    end
    
    subgraph "Marketing & Outreach"
        F[Marketing Agent] --> G[Content Creation]
        H[Outreach Agent] --> I[Client Communication]
    end
    
    subgraph "Coordination"
        J[Coordination Agent] --> B
        J --> C
        J --> D
        J --> F
        J --> H
    end
```

## 📂 Module Overview

| Module | Status | Purpose |
|--------|--------|---------|
| **analyser** | ✅ Active | Parse client requirements into machine-readable specs |
| **planning** | 🔄 Planned | Convert specs into development roadmaps |
| **dev** | 🔄 Planned | Generate production-ready code |
| **marketing** | 🔄 Planned | Create marketing materials and content |
| **outreach** | 🔄 Planned | Handle client communication and proposals |
| **coordination** | 🔄 Planned | Orchestrate multi-agent workflows |

## 🧩 Tech Stack

- **LLM**: AWS Bedrock Claude 3.5 Haiku (Bedrock only - no fallbacks)
- **OCR**: pytesseract + Pillow for image analysis
- **Vector Search**: FAISS for similarity lookups
- **Orchestration**: LangChain (lightweight usage)
- **Infrastructure**: Docker + AWS Bedrock for scalable deployment

## 📋 Current Sprint: Requirement Analyser

The analyser module ingests:
- Plain text briefs (MD, TXT, DOCX with full table support)
- Images (screenshots, mockups) with OCR
- ZIP archives or multipart uploads

And outputs structured JSON:
```json
{
  "title": "Project Name",
  "summary": "Brief description",
  "features": [{"name": "Feature", "desc": "Description"}],
  "constraints": ["Technical constraints"],
  "assets": {"images": [...], "docs": [...]}
}
```

Plus auto-generated artifacts:
- Mermaid component diagrams
- Task flow charts
- Optional UI wireframes

## 🔧 Development

```bash
# Setup virtual environment (first time only)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Activate environment (subsequent sessions)
source .venv/bin/activate

# Run tests
pytest tests/

# Local development
python scripts/run_analyser.py --path ./tests/fixtures

# Quick demo with sample data
./scripts/demo.sh

# Docker development
docker-compose up --build
```

## 📝 Contributing

This is the initial sprint focusing on MVP-sized projects (≤ 2 weeks dev time). Future sprints will add video/audio processing, authentication, and production deployment.