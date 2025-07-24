# AI Provider Implementations

This directory contains integrations with various AI/LLM providers.

## Architecture

All providers implement the `BaseProvider` abstract class:

```python
class BaseProvider(ABC):
    @abstractmethod
    def generate_code(self, prompt: str, context: dict) -> str:
        pass

    @abstractmethod
    def analyze_requirements(self, text: str) -> dict:
        pass
```

## Providers

### bedrock.py
- AWS Bedrock integration (primary provider)
- Supports Claude 3.5 Sonnet via inference profiles
- Includes retry logic and error handling

### openai.py
- OpenAI GPT-4 integration (fallback provider)
- Used when Bedrock is unavailable

### codewhisperer.py
- AWS CodeWhisperer for specialized code generation
- Experimental - not yet in production

### fake.py
- Mock provider for testing
- Returns predictable outputs without network calls
- Used in CI/CD and offline development

## Usage

```python
from src.providers.factory import get_provider

# Get provider based on environment
provider = get_provider()  # Uses AI_PROVIDER env var

# Generate code
code = provider.generate_code(prompt, context)
```

## Cost Tracking

All providers use the `@log_call` decorator to track:
- Token usage
- Response time
- Cost estimates
- Errors

Logs are written to `logs/llm_calls.log` for analysis.
