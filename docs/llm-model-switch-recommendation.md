# LLM Model Switch Recommendation for Metadata Extraction

## Current State
- **Model**: Claude 3.5 Haiku (via AWS Bedrock)
- **Cost**: $0.25/$1.25 per million tokens (input/output)
- **Latency**: 0.52 seconds
- **Integration**: Already implemented in `metadata_extractor.py`

## Recommended Alternative: GPT-4o-mini

### Cost Comparison
- **GPT-4o-mini**: $0.15/$0.60 per million tokens
- **Savings**: 40% on input, 52% on output tokens
- **Monthly estimate**: ~$30-50 savings at current volume

### Performance Comparison
| Metric | Claude Haiku | GPT-4o-mini | Winner |
|--------|-------------|-------------|---------|
| MMLU (reasoning) | 73.8% | 82.0% | GPT-4o-mini |
| Math reasoning | 71.7% | 87.0% | GPT-4o-mini |
| Coding (HumanEval) | 75.9% | 87.2% | GPT-4o-mini |
| Latency | 0.52s | 0.56s | Claude (marginal) |
| Cost | $0.25/$1.25 | $0.15/$0.60 | GPT-4o-mini |

### Implementation Steps

1. **Add OpenAI Provider** (if not exists):
```python
# src/providers/openai_provider.py
class OpenAIProvider(BaseProvider):
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
    
    def generate_code(self, prompt: str, context: List[str]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}  # Force JSON output
        )
        return response.choices[0].message.content
```

2. **Update MetadataExtractor**:
```python
# In metadata_extractor.py __init__
if USE_AI_PROVIDER:
    # Switch to OpenAI for better reasoning at lower cost
    self.provider = get_provider("openai")  # Instead of "bedrock"
    self.model = "gpt-4o-mini"
```

3. **Environment Variables**:
```bash
OPENAI_API_KEY=your-key-here
AI_PROVIDER=openai  # For local testing
```

4. **Lambda Deployment**:
- Add OpenAI Python SDK to Lambda layer
- Set OPENAI_API_KEY in Lambda environment
- Update IAM permissions if needed

### Benefits of Switching
1. **Better Reasoning**: 8-15% improvement on reasoning benchmarks
2. **Cost Savings**: 40-52% reduction in LLM costs
3. **JSON Mode**: Native JSON output enforcement
4. **Proven Reliability**: Widely used in production

### Risks & Mitigation
1. **Vendor Lock-in**: Mitigated by provider abstraction layer
2. **Latency**: 0.04s increase is negligible for this use case
3. **Migration Effort**: ~2-4 hours of development and testing

## Recommendation
**Switch to GPT-4o-mini** for metadata extraction:
- Superior reasoning performance for intent understanding
- Significant cost savings (40-52%)
- Minimal latency impact (0.04s)
- Better suited for the reasoning-based prompt approach

The improved reasoning capability is particularly important now that we've moved from pattern matching to logical reasoning in the extraction prompt.