# Test Suite

Comprehensive test coverage for the SoloPilot platform.

## Test Organization

Tests mirror the source code structure:
- Unit tests for individual components
- Integration tests for agent pipelines
- Performance benchmarks
- Regression tests for complex scenarios

## Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run specific test file
poetry run pytest tests/dev_agent_test.py

# Run in offline mode (no network calls)
NO_NETWORK=1 poetry run pytest

# Run with markers
poetry run pytest -m "not slow"
```

## Test Categories

### Unit Tests
- Fast, isolated tests for individual functions
- Mock external dependencies
- Use `fake` AI provider

### Integration Tests
- Test full agent pipelines
- May use real AI providers (with limits)
- Marked with `@pytest.mark.integration`

### Performance Tests
- Benchmark token usage and response times
- Located in `tests/performance/`
- Run with `python tests/performance/benchmark_suite.py`

### Regression Tests
- Complex real-world scenarios
- Located in `tests/regression/`
- Ensure fixes stay fixed

## Writing Tests

1. Use descriptive test names: `test_dev_agent_handles_missing_context`
2. Follow AAA pattern: Arrange, Act, Assert
3. Mock external services (AWS, APIs)
4. Use fixtures for common setup
5. Test both success and failure paths

## CI/CD Integration

Tests run automatically on:
- Every push to main
- All pull requests
- Multiple Python versions (3.9-3.12)
- Ubuntu and macOS
