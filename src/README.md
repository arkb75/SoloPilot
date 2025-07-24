# Source Code Directory

This directory contains all the source code for the SoloPilot platform.

## Directory Structure

- **agents/** - Agent implementations for different stages of the freelance pipeline
- **providers/** - AI provider integrations (Bedrock, OpenAI, etc.)
- **common/** - Shared utilities used across agents
- **utils/** - General utility functions

## Import Convention

All imports should use the `src` prefix:

```python
from src.agents.dev import dev_agent
from src.providers.bedrock import BedrockProvider
from src.common.bedrock_client import get_bedrock_client
```

## Development Guidelines

1. Follow the KISS principle - keep implementations simple
2. Use type hints for all function parameters and returns
3. Write docstrings for all public functions and classes
4. Ensure all code passes pre-commit hooks before committing
