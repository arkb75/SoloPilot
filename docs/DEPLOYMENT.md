# Deployment Guide - SoloPilot to Vercel

This guide covers the automated deployment pipeline from GitHub to Vercel.

## Overview

The deployment pipeline automatically deploys the SoloPilot application to Vercel when:
- Code is pushed to the `production` branch
- Manual deployment is triggered via GitHub Actions

## Setup

### 1. Vercel Project Setup

1. Create a new project on Vercel:
   ```bash
   vercel link
   ```

2. Note your project details:
   - Organization ID: Found in Vercel dashboard → Settings → General
   - Project ID: Found in project settings
   - API Token: Generate at https://vercel.com/account/tokens

### 2. GitHub Secrets Configuration

Add these secrets to your GitHub repository (Settings → Secrets → Actions):

```yaml
VERCEL_TOKEN: your_vercel_api_token
VERCEL_ORG_ID: your_organization_id
VERCEL_PROJECT_ID: your_project_id

# Production environment variables
VERCEL_PRODUCTION_DATABASE_URL: postgresql://...
VERCEL_PRODUCTION_NEXTAUTH_SECRET: generated_secret
VERCEL_PRODUCTION_AWS_ACCESS_KEY_ID: your_key
VERCEL_PRODUCTION_AWS_SECRET_ACCESS_KEY: your_secret

# Custom domain
VERCEL_CUSTOM_DOMAIN: solopilot.ai
VERCEL_ADDITIONAL_DOMAINS: www.solopilot.ai,app.solopilot.ai
```

### 3. Environment Configuration

1. Copy environment templates:
   ```bash
   cp .env.production.template .env.production
   cp .env.preview.template .env.preview
   ```

2. Fill in the values for each environment

3. **Never commit** actual `.env.production` or `.env.preview` files

## Deployment Process

### Automatic Deployment

1. **Production Deployment**:
   ```bash
   git checkout production
   git merge main
   git push origin production
   ```

   This triggers:
   - Build and test
   - Deploy to Vercel
   - Configure custom domains
   - Run smoke tests
   - Post-deployment validation

2. **Preview Deployment**:
   - Automatically created for pull requests
   - Deployed to `preview.solopilot.ai`

### Manual Deployment

Trigger deployment from GitHub Actions:

1. Go to Actions → Deploy to Vercel
2. Click "Run workflow"
3. Select environment (production/preview)
4. Click "Run workflow"

### Deployment Script

For local deployment (not recommended for production):

```bash
python scripts/deploy_to_vercel.py \
  --token $VERCEL_TOKEN \
  --org-id $VERCEL_ORG_ID \
  --project-id $VERCEL_PROJECT_ID \
  --environment production \
  --branch main \
  --commit $(git rev-parse HEAD)
```

## Deployment Validation

The pipeline automatically validates:

1. **Health Checks**:
   - HTTP 200 response
   - SSL certificate validity
   - API endpoint availability

2. **Performance**:
   - Page load time < 3 seconds
   - Core Web Vitals

3. **Security Headers**:
   - X-Content-Type-Options
   - X-Frame-Options
   - X-XSS-Protection
   - Strict-Transport-Security

## Custom Domains

### Production Domains

Configured automatically:
- `solopilot.ai` (primary)
- `www.solopilot.ai`
- `app.solopilot.ai`

### SSL Certificates

- Automatically provisioned by Vercel
- Let's Encrypt certificates
- Auto-renewal enabled

### DNS Configuration

Add these records to your DNS provider:

```
A     @     76.76.21.21
A     www   76.76.21.21
CNAME app   cname.vercel-dns.com
```

## Monitoring

### Deployment Status

- GitHub Actions: Check workflow runs
- Vercel Dashboard: Real-time deployment logs
- Email notifications on failure

### Logs

Access logs via:
- Vercel Dashboard → Functions → Logs
- GitHub Actions → Workflow runs

### Metrics

Monitor via Vercel Analytics:
- Page views
- Core Web Vitals
- Function invocations
- Error rates

## Rollback

### Quick Rollback

1. Via Vercel Dashboard:
   - Go to Deployments
   - Find previous stable deployment
   - Click "Promote to Production"

2. Via Git:
   ```bash
   git checkout production
   git reset --hard <previous-commit>
   git push --force origin production
   ```

### Rollback Checklist

- [ ] Identify the issue
- [ ] Check error logs
- [ ] Verify previous deployment stability
- [ ] Perform rollback
- [ ] Notify team
- [ ] Create incident report

## Troubleshooting

### Common Issues

1. **Build Failures**:
   - Check Node.js version (should be 18.x)
   - Verify all dependencies are installed
   - Check build logs in GitHub Actions

2. **Environment Variables**:
   - Ensure all required vars are set
   - Check for typos in variable names
   - Verify secrets in GitHub Settings

3. **Domain Issues**:
   - Verify DNS propagation
   - Check domain ownership in Vercel
   - Ensure no conflicting records

### Debug Commands

```bash
# Check Vercel CLI version
vercel --version

# List deployments
vercel ls

# Check deployment logs
vercel logs <deployment-url>

# Inspect build output
vercel inspect <deployment-url>
```

## Security Best Practices

1. **Secrets Management**:
   - Use GitHub Secrets for sensitive data
   - Rotate API tokens regularly
   - Never commit secrets to git

2. **Access Control**:
   - Limit Vercel API token permissions
   - Use deployment protection rules
   - Enable 2FA on all accounts

3. **Monitoring**:
   - Set up alerts for failed deployments
   - Monitor for suspicious activity
   - Regular security audits

## Cost Optimization

1. **Function Optimization**:
   - Set appropriate timeout limits
   - Use edge functions where possible
   - Monitor function invocations

2. **Bandwidth**:
   - Enable caching headers
   - Optimize images and assets
   - Use CDN for static files

3. **Build Minutes**:
   - Cache dependencies
   - Optimize build process
   - Use incremental builds

## Maintenance

### Regular Tasks

- [ ] Weekly: Review deployment metrics
- [ ] Monthly: Update dependencies
- [ ] Monthly: Rotate API tokens
- [ ] Quarterly: Security audit

### Update Checklist

Before major updates:
1. Test in preview environment
2. Review breaking changes
3. Update documentation
4. Plan rollback strategy
5. Schedule during low-traffic period

---

For urgent issues, contact: devops@solopilot.ai
