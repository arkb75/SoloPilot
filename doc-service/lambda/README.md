# SoloPilot Document Generation Lambda

Full-featured Lambda function that converts Markdown to PDF, stores in S3, and optionally creates Stripe invoices.

## Features

✅ **Markdown to PDF conversion** using React-PDF
✅ **S3 integration** with automatic upload and versioning
✅ **Signed URL generation** (24-hour expiry)
✅ **Stripe invoice creation** with PDF attachments
✅ **Customer management** (create or reuse existing)
✅ **Line item parsing** from markdown content
✅ **Input validation** with 100KB markdown limit
✅ **Filename sanitization** to prevent path traversal
✅ **CloudWatch logging** with conversationId context
✅ **Error handling** with fallback PDF generation
✅ **Unit tests** with mocked AWS SDK and Stripe

## API

### Request

```json
{
  "conversationId": "conv-123",
  "docType": "invoice",
  "filename": "invoice-001.pdf",
  "markdown": "# Invoice\n\nContent here...",

  // Optional Stripe fields
  "createInvoice": true,
  "customerEmail": "customer@example.com",
  "customerName": "ACME Corporation",
  "invoiceDescription": "Services for January 2025",
  "daysUntilDue": 30
}
```

### Response (Success)

```json
{
  "success": true,
  "documentUrl": "https://bucket.s3.amazonaws.com/signed-url",
  "s3Key": "conv-123/2025/01/invoice/1234567890-invoice-001.pdf",
  "pdfSize": 2500,
  "isError": false,
  "invoice": {
    "invoiceId": "in_1234567890",
    "invoiceNumber": "INV-0001",
    "status": "draft",
    "total": 900000,
    "currency": "usd",
    "dueDate": "2025-02-06T12:00:00.000Z",
    "hostedInvoiceUrl": "https://invoice.stripe.com/i/acct_123/test_123",
    "invoicePdf": "https://pay.stripe.com/invoice/acct_123/test_123/pdf",
    "customerId": "cus_123456",
    "customerEmail": "customer@example.com",
    "fileAttached": true
  },
  "metrics": {
    "processingTimeMs": 850,
    "requestId": "abc-123"
  }
}
```

### Response (Validation Error)

```json
{
  "success": false,
  "errors": [
    "conversationId is required and must be a string",
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
   - `STRIPE_SECRET_NAME`: Secrets Manager secret name (default: `solopilot/stripe/test`)
4. Attach IAM policy with:
   - S3 permissions (see terraform output)
   - Secrets Manager read permission for Stripe keys
5. Set memory to 256MB and timeout to 30 seconds (increased for Stripe API calls)

## S3 Document Structure

Documents are stored with the following key structure:

```
{conversationId}/{year}/{month}/{docType}/{timestamp}-{filename}
```

Example: `conv-123/2025/01/invoice/1704123456789-invoice-001.pdf`

## Input Validation

- **conversationId**: Required string
- **docType**: Required string
- **filename**: Required string (sanitized automatically)
- **markdown**: Required string, max 100KB

## Stripe Invoice Features

When `createInvoice: true` is set:

1. **Customer Management**:
   - Creates new Stripe customer or finds existing by conversationId
   - Stores conversationId in customer metadata for future lookups

2. **Line Item Parsing**:
   - Automatically extracts prices from markdown (e.g., `- Service: $1,000`)
   - Supports comma-separated amounts and decimals
   - Falls back to "Professional Services" if no items found

3. **PDF Attachment**:
   - Uploads generated PDF to Stripe Files API
   - Attaches as custom field on invoice
   - Accessible via hosted invoice page

4. **Draft Status**:
   - Invoices created as drafts (not sent automatically)
   - Can be reviewed and sent manually via Stripe Dashboard
   - Net 30 payment terms by default

## Performance

- Package size: ~9MB (with React-PDF + Stripe)
- Memory usage: ~80-120MB with Stripe calls
- Processing time: 500-1500ms (includes Stripe API)
- Cold start: <2 seconds

## Security

- Filename sanitization prevents path traversal
- Signed URLs expire after 24 hours
- All documents encrypted at rest (S3 default)
- CloudWatch logs include conversationId for audit trail

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
