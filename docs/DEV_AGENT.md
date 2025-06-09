# SoloPilot Dev Agent v0

The Dev Agent transforms planning output into milestone-based code structure with skeleton implementations, bridging the gap between project planning and actual development.

## Overview

[![CI Status](https://github.com/your-username/SoloPilot/workflows/CI/badge.svg)](https://github.com/your-username/SoloPilot/actions)

The Dev Agent takes structured planning output (JSON) and generates:
- **Milestone directories** with skeleton code implementations
- **Unit test frameworks** for each milestone
- **Context7 insights** (optional) for enhanced development guidance
- **Comprehensive documentation** for each milestone

## Architecture

```
/agents/dev/
├── dev_agent.py          # Core agent implementation
├── context7_bridge.py    # MCP adapter for Context7 integration
└── __init__.py

/scripts/
└── run_dev_agent.py      # CLI wrapper

/output/dev/<timestamp>/
├── milestone-1/
│   ├── implementation.js # Generated skeleton code
│   ├── test.js          # Unit test framework
│   └── README.md        # Milestone documentation
├── milestone-2/
│   └── ...
├── unit_tests/
│   └── integration.test.js
└── manifest.json        # Generation metadata
```

## Features

### Core Generation
- **Language Detection**: Automatically infers programming language from tech stack
- **Skeleton Code**: Generates foundational code structure with TODO markers
- **Test Framework**: Creates comprehensive unit test suites
- **Documentation**: Auto-generates README files for each milestone

### LLM Integration
- **Primary**: AWS Bedrock Claude 3.5 Haiku with exponential backoff retry
- **Fallback**: Stub code generation (if Bedrock fails)
- **Retry Logic**: 3 attempts with 2^attempt + jitter backoff for stability
- **Credentials**: Requires AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or ~/.aws/credentials
- **SDK Compatibility**: Dev-Agent first attempts modern `inferenceProfileArn`; if SDK too old it automatically retries legacy mode (ARN as modelId)

### Context7 Enhancement (Optional)
- **Pitfall Analysis**: Identifies common implementation mistakes
- **Pattern Guidance**: Suggests best practices and architectural patterns
- **Testing Strategies**: Recommends testing approaches for each milestone
- **Automated Installation**: Can auto-install Context7 if needed

## Usage

### Basic Commands

```bash
# Process latest planning output
make dev

# Full end-to-end pipeline
make plan-dev  # analyser → planner → dev agent

# Enable Context7 insights
make dev-scout

# Direct CLI usage
python scripts/run_dev_agent.py
python scripts/run_dev_agent.py --planning path/to/planning.json
```

### CLI Options

```bash
python scripts/run_dev_agent.py [OPTIONS]

Options:
  --planning PATH     Specific planning file (default: latest)
  --output PATH       Custom output directory
  --config PATH       Model configuration file
  --verbose          Enable detailed output
  --install-context7  Install Context7 globally
  --scout-status      Show Context7 bridge status
```

### Environment Variables

- `C7_SCOUT=1`: Enable Context7 scouting for enhanced insights

## Configuration

Uses the same `config/model_config.yaml` as other agents:

```yaml
llm:
  bedrock:
    model_id: "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    region: "us-east-2"
    model_kwargs:
      temperature: 0.1
      max_tokens: 2048
# OpenAI configuration removed - Bedrock only
```

## Output Structure

### Generated Files

Each milestone generates:

1. **Implementation File** (`implementation.{ext}`)
   - Skeleton code with proper structure
   - TODO comments for development guidance
   - Language-appropriate imports and patterns

2. **Test File** (`test.{ext}`)
   - Jest-style unit test framework
   - Test cases for main functionality
   - Integration test patterns

3. **README.md**
   - Milestone description and tasks
   - Generated file overview
   - Context7 insights (if enabled)
   - Next steps guidance

### Language Support

Automatically detects and generates appropriate code:

- **JavaScript/TypeScript**: React, Node.js, Express
- **Python**: Django, Flask, FastAPI
- **Java**: Spring Boot
- **C#**: .NET
- **SQL**: Database schemas

## Context7 Integration

### Setup

```bash
# Install Context7 globally
npm install -g context7

# Enable scouting
export C7_SCOUT=1
make dev
```

### Enhanced Insights

When enabled, Context7 provides:

- **Common Pitfalls**: 5 most frequent implementation mistakes
- **Best Practices**: Architecture and code organization patterns
- **Testing Strategies**: Unit, integration, and e2e testing approaches

Insights are automatically integrated into milestone README files.

## Testing

### Unit Tests

```bash
# Run dev agent tests
pytest tests/dev_agent_test.py -v

# Run all tests
make test
```

### Test Coverage

- ✅ Core dev agent functionality
- ✅ Language inference and file generation
- ✅ LLM fallback mechanisms
- ✅ Context7 bridge integration
- ✅ End-to-end smoke tests

## Performance

### Time Targets

- **`make dev`**: < 2 minutes for typical 5-milestone project
- **`make plan-dev`**: < 10 minutes end-to-end (includes analyser + planner)
- **Bedrock quota error**: Automatic fallback to stub code

### Resource Usage

- **Memory**: ~100MB during generation
- **Storage**: ~1-5MB per milestone (depending on code complexity)
- **Network**: Minimal (only LLM API calls)

## Error Handling

### Robust Fallbacks

1. **Bedrock unavailable** → Stub code generation
2. **Context7 unavailable** → Standard generation without insights
3. **Invalid planning data** → Clear error messages with guidance
4. **Missing AWS credentials** → Clear runtime error with setup guidance

### Common Issues

- **No planning output**: Run `make plan` first
- **AWS credentials**: Ensure Bedrock access configured
- **Context7 not found**: Auto-install via `npm install -g context7`

## Integration

### With Other Agents

- **Input**: Planning agent output (`planning_output.json`)
- **Dependencies**: Analyser → Planner → Dev Agent
- **Output**: Ready for code implementation and testing

### Workflow Integration

```bash
# Complete pipeline
make plan-dev     # Full workflow
make dev          # Dev agent only
make dev-scout    # With Context7 insights
```

## Roadmap

### v0.1 (Current)
- ✅ Core milestone generation
- ✅ Multi-language support
- ✅ Context7 integration
- ✅ Comprehensive testing

### Future Enhancements
- Code quality analysis integration
- CI/CD pipeline generation
- Docker containerization templates
- API documentation generation
- Database migration scripts

## Examples

### Input (Planning Output)
```json
{
  "project_title": "E-Commerce Platform",
  "milestones": [
    {
      "name": "Authentication System",
      "description": "User login and registration",
      "tasks": [...]
    }
  ],
  "tech_stack": ["Node.js", "React", "PostgreSQL"]
}
```

### Output Structure
```
output/dev/20250608_143021/
├── milestone-1/
│   ├── implementation.js    # Auth service skeleton
│   ├── test.js             # Auth tests
│   └── README.md           # Auth milestone docs
├── unit_tests/
│   └── integration.test.js
└── manifest.json
```

### Generated Code Sample
```javascript
// === Authentication Service Implementation ===
class AuthenticationService {
    constructor() {
        // TODO: Initialize database connection
        // TODO: Configure JWT settings
    }
    
    async register(userData) {
        // TODO: Validate user input
        // TODO: Hash password
        // TODO: Save to database
        throw new Error('Not implemented');
    }
    
    async login(credentials) {
        // TODO: Validate credentials
        // TODO: Generate JWT token
        throw new Error('Not implemented');
    }
}

// === Unit Tests ===
describe('AuthenticationService', () => {
    test('should register new user', async () => {
        // TODO: Test user registration
        expect(true).toBe(true);
    });
    
    test('should login existing user', async () => {
        // TODO: Test user login
        expect(true).toBe(true);
    });
});
```

## Using Inference Profiles

The Dev Agent now requires AWS Bedrock inference profiles for all model access. Configure your `config/model_config.yaml` with the full inference profile ARN instead of model IDs. This provides better access control and regional availability. See the complete inference profile mapping in [CLAUDE.md](../CLAUDE.md#-inference-profile-map--us-east-2) for all available models and their corresponding ARNs.

---

**Generated**: 2025-06-08  
**Version**: v0.1  
**Branch**: `feature/dev-agent-v0`