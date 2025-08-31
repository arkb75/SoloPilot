const AWSMock = require('aws-sdk-mock');
const { handler } = require('../src/index');

// Mock the logger
jest.mock('../src/logger', () => ({
  createLogger: () => ({
    setContext: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
    debug: jest.fn()
  })
}));

describe('Lambda Handler', () => {
  const mockContext = {
    requestId: 'test-request-id'
  };

  beforeEach(() => {
    process.env.DOCUMENT_BUCKET = 'test-bucket';
    process.env.AWS_REGION = 'us-east-1';
  });

  afterEach(() => {
    AWSMock.restore();
    jest.clearAllMocks();
  });

  describe('Input Validation', () => {
    it('should reject missing conversationId', async () => {
      const event = {
        body: JSON.stringify({
          docType: 'invoice',
          filename: 'test.pdf',
          markdown: '# Test'
        })
      };

      const result = await handler(event, mockContext);
      const body = JSON.parse(result.body);

      expect(result.statusCode).toBe(400);
      expect(body.success).toBe(false);
      expect(body.errors).toContain('conversationId is required and must be a string');
    });

    it('should reject missing docType', async () => {
      const event = {
        body: JSON.stringify({
          conversationId: 'conv-123',
          filename: 'test.pdf',
          markdown: '# Test'
        })
      };

      const result = await handler(event, mockContext);
      const body = JSON.parse(result.body);

      expect(result.statusCode).toBe(400);
      expect(body.errors).toContain('docType is required and must be a string');
    });

    it('should reject missing filename', async () => {
      const event = {
        body: JSON.stringify({
          conversationId: 'conv-123',
          docType: 'invoice',
          markdown: '# Test'
        })
      };

      const result = await handler(event, mockContext);
      const body = JSON.parse(result.body);

      expect(result.statusCode).toBe(400);
      expect(body.errors).toContain('filename is required and must be a string');
    });

    it('should reject missing markdown', async () => {
      const event = {
        body: JSON.stringify({
          conversationId: 'conv-123',
          docType: 'invoice',
          filename: 'test.pdf'
        })
      };

      const result = await handler(event, mockContext);
      const body = JSON.parse(result.body);

      expect(result.statusCode).toBe(400);
      expect(body.errors).toContain('markdown is required and must be a string');
    });

    it('should reject markdown over 100KB', async () => {
      const largeMarkdown = '#'.repeat(101 * 1024);
      const event = {
        body: JSON.stringify({
          conversationId: 'conv-123',
          docType: 'invoice',
          filename: 'test.pdf',
          markdown: largeMarkdown
        })
      };

      const result = await handler(event, mockContext);
      const body = JSON.parse(result.body);

      expect(result.statusCode).toBe(400);
      expect(body.errors).toContain('markdown exceeds 100KB limit');
    });
  });

  describe('Successful PDF Generation', () => {
    beforeEach(() => {
      // Mock S3 upload
      AWSMock.mock('S3', 'putObject', (params, callback) => {
        callback(null, { ETag: '"abc123"' });
      });

      // Mock S3 signed URL
      AWSMock.mock('S3', 'getSignedUrl', (method, params, callback) => {
        callback(null, 'https://test-bucket.s3.amazonaws.com/signed-url');
      });
    });

    it('should generate PDF and return signed URL', async () => {
      const event = {
        body: JSON.stringify({
          conversationId: 'conv-123',
          docType: 'invoice',
          filename: 'invoice-001.pdf',
          markdown: '# Invoice 001\n\nThis is a test invoice.'
        })
      };

      const result = await handler(event, mockContext);
      const body = JSON.parse(result.body);

      expect(result.statusCode).toBe(200);
      expect(body.success).toBe(true);
      expect(body.documentUrl).toBe('https://test-bucket.s3.amazonaws.com/signed-url');
      expect(body.s3Key).toMatch(/^conv-123\/\d{4}\/\d{2}\/invoice\/\d+-invoice-001\.pdf$/);
      expect(body.pdfSize).toBeGreaterThan(0);
      expect(body.isError).toBe(false);
      expect(body.metrics.requestId).toBe('test-request-id');
    });

    it('should sanitize filename', async () => {
      const event = {
        body: JSON.stringify({
          conversationId: 'conv-123',
          docType: 'invoice',
          filename: '../../../etc/passwd',
          markdown: '# Test'
        })
      };

      const result = await handler(event, mockContext);
      const body = JSON.parse(result.body);

      expect(result.statusCode).toBe(200);
      expect(body.s3Key).toMatch(/^conv-123\/\d{4}\/\d{2}\/invoice\/\d+-___etc_passwd\.pdf$/);
    });

    it('should add .pdf extension if missing', async () => {
      const event = {
        body: JSON.stringify({
          conversationId: 'conv-123',
          docType: 'invoice',
          filename: 'invoice-001',
          markdown: '# Test'
        })
      };

      const result = await handler(event, mockContext);
      const body = JSON.parse(result.body);

      expect(result.statusCode).toBe(200);
      expect(body.s3Key).toMatch(/^conv-123\/\d{4}\/\d{2}\/invoice\/\d+-invoice-001\.pdf$/);
    });
  });

  describe('Error Handling', () => {
    it('should generate error PDF for invalid markdown', async () => {
      // Mock S3 operations
      AWSMock.mock('S3', 'putObject', (params, callback) => {
        callback(null, { ETag: '"abc123"' });
      });

      AWSMock.mock('S3', 'getSignedUrl', (method, params, callback) => {
        callback(null, 'https://test-bucket.s3.amazonaws.com/signed-url');
      });

      const event = {
        body: JSON.stringify({
          conversationId: 'conv-123',
          docType: 'invoice',
          filename: 'test.pdf',
          markdown: null
        })
      };

      const result = await handler(event, mockContext);
      const body = JSON.parse(result.body);

      expect(result.statusCode).toBe(200);
      expect(body.success).toBe(true);
      expect(body.isError).toBe(true);
      expect(body.documentUrl).toBeDefined();
    });

    it('should handle S3 upload errors', async () => {
      AWSMock.mock('S3', 'putObject', (params, callback) => {
        callback(new Error('S3 upload failed'));
      });

      const event = {
        body: JSON.stringify({
          conversationId: 'conv-123',
          docType: 'invoice',
          filename: 'test.pdf',
          markdown: '# Test'
        })
      };

      const result = await handler(event, mockContext);
      const body = JSON.parse(result.body);

      expect(result.statusCode).toBe(500);
      expect(body.success).toBe(false);
      expect(body.error).toBe('Internal server error');
      expect(body.requestId).toBe('test-request-id');
    });
  });

  describe('Direct Event Handling', () => {
    it('should handle direct event object (no body wrapper)', async () => {
      AWSMock.mock('S3', 'putObject', (params, callback) => {
        callback(null, { ETag: '"abc123"' });
      });

      AWSMock.mock('S3', 'getSignedUrl', (method, params, callback) => {
        callback(null, 'https://test-bucket.s3.amazonaws.com/signed-url');
      });

      const event = {
        conversationId: 'conv-123',
        docType: 'invoice',
        filename: 'test.pdf',
        markdown: '# Test'
      };

      const result = await handler(event, mockContext);
      const body = JSON.parse(result.body);

      expect(result.statusCode).toBe(200);
      expect(body.success).toBe(true);
    });
  });
});
