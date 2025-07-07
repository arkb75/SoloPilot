# SoloPilot Document Generation Lambda

Full-featured Lambda function that converts Markdown to PDF and stores in S3 with signed URL generation.

## Features

✅ **Markdown to PDF conversion** using React-PDF  
✅ **S3 integration** with automatic upload and versioning  
✅ **Signed URL generation** (24-hour expiry)  
✅ **Input validation** with 100KB markdown limit  
✅ **Filename sanitization** to prevent path traversal  
✅ **CloudWatch logging** with clientId context  
✅ **Error handling** with fallback PDF generation  
✅ **Unit tests** with mocked AWS SDK

## API

### Request

```json
{
  "clientId": "client123",
  "docType": "invoice",
  "filename": "invoice-001.pdf",
  "markdown": "# Invoice\n\nContent here..."
}
```

### Response (Success)

```json
{
  "success": true,
  "documentUrl": "https://bucket.s3.amazonaws.com/signed-url",
  "s3Key": "client123/2025/01/invoice/1234567890-invoice-001.pdf",
  "pdfSize": 2500,
  "isError": false,
  "metrics": {
    "processingTimeMs": 250,
    "requestId": "abc-123"
  }
}
```

### Response (Validation Error)

```json
{
  "success": false,
  "errors": [
    "clientId is required and must be a string",
    "markdown exceeds 100KB limit"
  ]
}
```

## Directory Structure

```
lambda/
├── src/
│   ├── index.js        # Main Lambda handler
│   ├── logger.js       # CloudWatch logger utility
│   └── s3-helpers.js   # S3 helper functions
├── test/
│   ├── index.test.js   # Handler unit tests
│   └── s3-helpers.test.js # S3 helper tests
├── package.json
├── test-local.js       # Local testing script
└── README.md
```

## Local Development

### Prerequisites

- Node.js 18.x
- AWS CLI configured with credentials
- S3 bucket created (or permissions to create)

### Setup

```bash
npm install
```

### Run Tests

```bash
# Run all tests
npm test

# Run with coverage
npm test:coverage

# Watch mode
npm test:watch
```

### Local Testing

```bash
# Set environment variables
export DOCUMENT_BUCKET=your-bucket-name
export AWS_REGION=us-east-1

# Run local test
node test-local.js
```

## Deployment

### Build Lambda Package

```bash
# Install production dependencies
npm run build

# Create deployment zip
npm run zip

# Check package size
ls -lh function.zip
```

### Deploy to AWS

1. Create/Update Lambda function with Node.js 18.x runtime
2. Set handler to `src/index.handler`
3. Configure environment variables:
   - `DOCUMENT_BUCKET`: S3 bucket name
   - `AWS_REGION`: AWS region
4. Attach IAM policy with S3 permissions (see terraform output)
5. Set memory to 128MB and timeout to 30 seconds

## S3 Document Structure

Documents are stored with the following key structure:

```
{clientId}/{year}/{month}/{docType}/{timestamp}-{filename}
```

Example: `client123/2025/01/invoice/1704123456789-invoice-001.pdf`

## Input Validation

- **clientId**: Required string
- **docType**: Required string
- **filename**: Required string (sanitized automatically)
- **markdown**: Required string, max 100KB

## Performance

- Package size: ~8MB (with React-PDF)
- Memory usage: ~50-70MB typical
- Processing time: 200-500ms typical
- Cold start: <1 second

## Security

- Filename sanitization prevents path traversal
- Signed URLs expire after 24 hours
- All documents encrypted at rest (S3 default)
- CloudWatch logs include clientId for audit trail

## Error Handling

If markdown parsing fails, the Lambda generates a fallback PDF with:
- Error message: "Document Parse Error"
- Support contact instruction
- Error ID for debugging

The Lambda never crashes - it always returns a valid response.

## TODO

- [ ] Migrate to AWS SDK v3 for smaller bundle size
- [ ] Add support for more markdown features (tables, lists)
- [ ] Implement PDF templates for different document types
- [ ] Add watermark support
- [ ] Cache generated PDFs for identical inputs