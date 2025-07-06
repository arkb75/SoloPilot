# Document Service S3 Infrastructure

This Terraform module creates the S3 infrastructure for the SoloPilot document generation service.

## Features

- ✅ S3 bucket with versioning enabled
- ✅ Server-side encryption (AES256)
- ✅ Public access blocked
- ✅ Lifecycle rules for old version cleanup (30 days)
- ✅ IAM policy for Lambda access
- ✅ Helper functions for signed URLs

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured with appropriate credentials
- AWS account with permissions to create S3 buckets and IAM policies

## Usage

### 1. Initialize Terraform

```bash
terraform init
```

### 2. Plan the Infrastructure

```bash
# Review what will be created
terraform plan

# With custom variables
terraform plan -var="environment=prod" -var="bucket_name=my-custom-bucket"
```

### 3. Apply (Create Infrastructure)

```bash
# ⚠️ DO NOT APPLY YET - For review only
terraform apply

# To generate the plan without applying:
terraform plan -out=tfplan
```

### 4. Using the S3 Helper in Lambda

```javascript
const S3DocumentHelper = require('./s3_helpers');

// Initialize with bucket name from Terraform output
const s3Helper = new S3DocumentHelper(process.env.DOCUMENT_BUCKET);

// Generate signed download URL (24h expiry)
const downloadUrl = await s3Helper.getSignedDownloadUrl('path/to/document.pdf');

// Upload a document
const key = s3Helper.generateDocumentKey('client123', 'invoice', 'invoice-001.pdf');
await s3Helper.uploadDocument(key, pdfBuffer, 'application/pdf', {
  clientId: 'client123',
  invoiceNumber: '001'
});

// Get signed URL for the uploaded document
const url = await s3Helper.getSignedDownloadUrl(key, 86400); // 24 hours
```

## Variables

| Name | Description | Default |
|------|-------------|---------|
| `project_name` | Name of the project | `solopilot` |
| `environment` | Environment (dev, staging, prod) | `dev` |
| `aws_region` | AWS region | `us-east-1` |
| `bucket_name` | Custom bucket name (auto-generated if empty) | `""` |
| `lambda_function_name` | Lambda function name | `solopilot-doc-generator` |

## Outputs

| Name | Description |
|------|-------------|
| `bucket_name` | Name of the created S3 bucket |
| `bucket_arn` | ARN of the S3 bucket |
| `lambda_policy_arn` | ARN of the IAM policy for Lambda |
| `s3_bucket_details` | Complete bucket details object |

## Security Features

1. **Versioning**: All document changes are tracked
2. **Encryption**: AES256 server-side encryption
3. **Access Control**: Public access completely blocked
4. **Signed URLs**: Time-limited access to documents
5. **IAM Policy**: Least privilege access for Lambda

## Cost Optimization

- Old versions automatically deleted after 30 days
- Standard storage class (can be modified for Infrequent Access)
- Lifecycle rules to manage storage costs

## Directory Structure

```
client-id/
  └── year/
      └── month/
          └── document-type/
              └── timestamp-filename.pdf
```

Example: `client123/2025/01/invoice/1704123456789-invoice-001.pdf`