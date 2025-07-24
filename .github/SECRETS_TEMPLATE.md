# GitHub Actions Secrets Template

This file lists all the secrets that need to be configured in your GitHub repository for the deployment pipeline to work.

## Required Secrets

### Vercel Configuration
- `VERCEL_TOKEN`: Your Vercel API token (generate at https://vercel.com/account/tokens)
- `VERCEL_ORG_ID`: Your Vercel organization/team ID
- `VERCEL_PROJECT_ID`: Your Vercel project ID

### Domain Configuration
- `VERCEL_CUSTOM_DOMAIN`: Primary domain (e.g., solopilot.ai)
- `VERCEL_ADDITIONAL_DOMAINS`: Comma-separated additional domains (e.g., www.solopilot.ai,app.solopilot.ai)

### AWS Configuration (Production)
- `VERCEL_PRODUCTION_AWS_ACCESS_KEY_ID`: AWS access key for production
- `VERCEL_PRODUCTION_AWS_SECRET_ACCESS_KEY`: AWS secret key for production
- `VERCEL_PRODUCTION_AWS_REGION`: AWS region (e.g., us-east-2)

### AWS Configuration (Preview/Staging)
- `VERCEL_PREVIEW_AWS_ACCESS_KEY_ID`: AWS access key for staging
- `VERCEL_PREVIEW_AWS_SECRET_ACCESS_KEY`: AWS secret key for staging

### Database Configuration
- `VERCEL_PRODUCTION_DATABASE_URL`: Production database connection string
- `VERCEL_PREVIEW_DATABASE_URL`: Staging database connection string

### Authentication
- `VERCEL_PRODUCTION_NEXTAUTH_SECRET`: Production NextAuth secret (generate with: openssl rand -base64 32)
- `VERCEL_PREVIEW_NEXTAUTH_SECRET`: Staging NextAuth secret

### Optional Secrets

### OAuth Providers
- `VERCEL_PRODUCTION_GITHUB_CLIENT_ID`: GitHub OAuth app ID
- `VERCEL_PRODUCTION_GITHUB_CLIENT_SECRET`: GitHub OAuth app secret

### Monitoring
- `VERCEL_PRODUCTION_SENTRY_DSN`: Sentry error tracking DSN
- `VERCEL_PRODUCTION_GOOGLE_ANALYTICS_ID`: Google Analytics ID

### Third-party Services
- `VERCEL_PRODUCTION_STRIPE_PUBLIC_KEY`: Stripe publishable key
- `VERCEL_PRODUCTION_STRIPE_SECRET_KEY`: Stripe secret key
- `VERCEL_PRODUCTION_CONTEXT7_API_KEY`: Context7 MCP API key

## How to Add Secrets

1. Go to your GitHub repository
2. Click on Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Add each secret with the exact name listed above
5. Paste the secret value (be careful not to include extra spaces)

## Security Notes

- Never commit actual secret values to the repository
- Rotate secrets regularly (recommended: every 90 days)
- Use different secrets for production and staging
- Enable audit logging in GitHub to track secret access
- Consider using GitHub Environments for additional protection

## Verifying Secrets

After adding all secrets, you can verify they're properly configured by:

1. Running the deployment workflow manually
2. Checking the workflow logs (secrets will be masked)
3. Verifying environment variables in Vercel dashboard
