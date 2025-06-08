# AWS Bedrock Setup Guide

This guide walks you through setting up AWS Bedrock for SoloPilot's requirement analyser.

## 🚀 Quick Setup

### 1. AWS Account & Bedrock Access

1. **Ensure you have an AWS account** with Bedrock access
2. **Request model access** in AWS Bedrock console:
   - Go to AWS Console → Amazon Bedrock → Model access
   - Request access to: **Anthropic Claude 3.5 Haiku**
   - Access is usually granted within a few minutes

### 2. AWS Credentials Setup (Choose One Method)

#### Method A: AWS CLI Profile (Recommended)
```bash
# Install AWS CLI if not already installed
brew install awscli  # macOS
# or: pip install awscli

# Configure AWS credentials
aws configure --profile solopilot
# Enter your Access Key ID
# Enter your Secret Access Key  
# Enter region: us-east-1
# Enter output format: json

# Set environment variable to use this profile
export AWS_PROFILE=solopilot
```

#### Method B: Environment Variables
```bash
# Copy and configure .env file
cp .env.example .env

# Edit .env file with your credentials:
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1
```

### 3. Update Dependencies & Test

```bash
# Update virtual environment with Bedrock dependencies
source .venv/bin/activate
pip install -r requirements.txt

# Test the setup
make demo
```

## 🔧 Configuration Options

### Model Selection
Edit `config/model_config.yaml` to change models:

```yaml
llm:
  bedrock:
    # Claude 3.5 Haiku (fast, cost-effective)
    model_id: "anthropic.claude-3-5-haiku-20241022-v1:0"
    
    # Alternative models:
    # model_id: "anthropic.claude-3-5-sonnet-20241022-v2:0"  # More capable, higher cost
    # model_id: "meta.llama3-1-8b-instruct-v1:0"            # Llama 3.1 8B, lower cost
```

### Region Configuration
Available regions for Bedrock:
- `us-east-1` (N. Virginia) - **Recommended**: Best model availability
- `us-west-2` (Oregon)
- `eu-west-1` (Ireland)
- Check [AWS Bedrock docs](https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-regions.html) for latest regions

## 💰 Cost Optimization

### Current Settings (Cost-Optimized)
- **Primary**: Claude 3.5 Haiku ($1/$5 per 1K input/output tokens)
- **Intelligent routing**: Automatically routes complex requests to appropriate models
- **Fallback**: OpenAI GPT-4o Mini for redundancy

### Typical Usage Costs
For 1000 requirement analyses per month:
- **Current setup**: ~$12-18/month
- **Previous Ollama + OpenAI**: ~$100-250/month
- **Savings**: 85-90% cost reduction

## 🔍 Troubleshooting

### "Model access denied" Error
1. Go to AWS Console → Bedrock → Model access
2. Request access to Anthropic Claude models
3. Wait for approval (usually instant)

### "Credentials not found" Error
1. Verify AWS credentials are set correctly
2. Test with: `aws sts get-caller-identity`
3. Ensure region is supported for Bedrock

### "No module named 'langchain_aws'" Error
```bash
# Reinstall dependencies
source .venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Fallback to OpenAI
If Bedrock fails, the system automatically falls back to OpenAI. Set your OpenAI API key in `.env`:
```bash
OPENAI_API_KEY=your_openai_key_here
```

## 🔐 Security Best Practices

1. **Use IAM roles** instead of access keys when possible
2. **Restrict permissions** to only Bedrock services needed
3. **Never commit credentials** to version control
4. **Rotate access keys** regularly
5. **Use AWS profiles** instead of environment variables in production

## 📊 Monitoring & Costs

1. **CloudWatch**: Monitor Bedrock usage and errors
2. **Cost Explorer**: Track Bedrock costs by model
3. **Budgets**: Set up billing alerts for unexpected usage

## ✅ Verification

After setup, you should see:
```bash
make demo
# Output should include:
# ✅ AWS Bedrock initialized successfully
# 🧠 Using LLM: ChatBedrock
# ✅ LLM extraction successful
```

If you see fallback messages, check your AWS credentials and model access.