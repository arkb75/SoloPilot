const AWSMock = require('aws-sdk-mock');
const AWS = require('aws-sdk');
const S3DocumentHelper = require('../src/s3-helpers');

describe('S3DocumentHelper', () => {
  const bucketName = 'test-bucket';
  const region = 'us-east-1';
  let s3Helper;

  beforeEach(() => {
    // Create new instance for each test
    s3Helper = new S3DocumentHelper(bucketName, region);
  });

  afterEach(() => {
    // Restore all mocks
    AWSMock.restore();
  });

  describe('getSignedDownloadUrl', () => {
    it('should generate a signed download URL', async () => {
      const mockUrl = 'https://test-bucket.s3.amazonaws.com/test.pdf?signature=xyz';

      AWSMock.mock('S3', 'getSignedUrl', (method, params, callback) => {
        expect(method).toBe('getObject');
        expect(params.Bucket).toBe(bucketName);
        expect(params.Key).toBe('test.pdf');
        expect(params.Expires).toBe(86400);
        callback(null, mockUrl);
      });

      const url = await s3Helper.getSignedDownloadUrl('test.pdf');
      expect(url).toBe(mockUrl);
    });

    it('should use custom expiration time', async () => {
      const mockUrl = 'https://test-bucket.s3.amazonaws.com/test.pdf?signature=xyz';
      const customExpiry = 3600;

      AWSMock.mock('S3', 'getSignedUrl', (method, params, callback) => {
        expect(params.Expires).toBe(customExpiry);
        callback(null, mockUrl);
      });

      const url = await s3Helper.getSignedDownloadUrl('test.pdf', customExpiry);
      expect(url).toBe(mockUrl);
    });

    it('should handle errors', async () => {
      const mockError = new Error('S3 error');

      AWSMock.mock('S3', 'getSignedUrl', (method, params, callback) => {
        callback(mockError);
      });

      await expect(s3Helper.getSignedDownloadUrl('test.pdf'))
        .rejects.toThrow('S3 error');
    });
  });

  describe('uploadDocument', () => {
    it('should upload a document to S3', async () => {
      const mockResponse = { ETag: '"abc123"' };
      const testContent = Buffer.from('test content');
      const metadata = { clientId: 'client123' };

      AWSMock.mock('S3', 'putObject', (params, callback) => {
        expect(params.Bucket).toBe(bucketName);
        expect(params.Key).toBe('test.pdf');
        expect(params.Body).toEqual(testContent);
        expect(params.ContentType).toBe('application/pdf');
        expect(params.Metadata).toEqual(metadata);
        callback(null, mockResponse);
      });

      const result = await s3Helper.uploadDocument(
        'test.pdf',
        testContent,
        'application/pdf',
        metadata
      );

      expect(result).toEqual(mockResponse);
    });

    it('should handle upload errors', async () => {
      const mockError = new Error('Upload failed');

      AWSMock.mock('S3', 'putObject', (params, callback) => {
        callback(mockError);
      });

      await expect(
        s3Helper.uploadDocument('test.pdf', 'content', 'application/pdf')
      ).rejects.toThrow('Upload failed');
    });
  });

  describe('downloadDocument', () => {
    it('should download a document from S3', async () => {
      const mockResponse = {
        Body: Buffer.from('test content'),
        ContentType: 'application/pdf',
        Metadata: { clientId: 'client123' }
      };

      AWSMock.mock('S3', 'getObject', (params, callback) => {
        expect(params.Bucket).toBe(bucketName);
        expect(params.Key).toBe('test.pdf');
        callback(null, mockResponse);
      });

      const result = await s3Helper.downloadDocument('test.pdf');
      expect(result).toEqual(mockResponse);
    });

    it('should handle download errors', async () => {
      const mockError = new Error('Download failed');

      AWSMock.mock('S3', 'getObject', (params, callback) => {
        callback(mockError);
      });

      await expect(s3Helper.downloadDocument('test.pdf'))
        .rejects.toThrow('Download failed');
    });
  });

  describe('generateDocumentKey', () => {
    it('should generate a properly structured S3 key', () => {
      // Mock Date to ensure consistent output
      const mockDate = new Date('2025-01-06T12:00:00Z');
      const originalDate = Date;
      global.Date = jest.fn(() => mockDate);
      global.Date.now = jest.fn(() => mockDate.getTime());

      const key = s3Helper.generateDocumentKey(
        'conv-123',
        'invoice',
        'invoice-001.pdf'
      );

      expect(key).toMatch(/^conv-123\/2025\/01\/invoice\/\d+-invoice-001\.pdf$/);

      // Restore original Date
      global.Date = originalDate;
    });

    it('should handle different document types', () => {
      const key = s3Helper.generateDocumentKey(
        'conv-456',
        'report',
        'monthly-report.pdf'
      );

      expect(key).toMatch(/^conv-456\/\d{4}\/\d{2}\/report\/\d+-monthly-report\.pdf$/);
    });
  });

  describe('getSignedUploadUrl', () => {
    it('should generate a signed upload URL', async () => {
      const mockUrl = 'https://test-bucket.s3.amazonaws.com/test.pdf?signature=xyz';

      AWSMock.mock('S3', 'getSignedUrl', (method, params, callback) => {
        expect(method).toBe('putObject');
        expect(params.Bucket).toBe(bucketName);
        expect(params.Key).toBe('test.pdf');
        expect(params.ContentType).toBe('application/pdf');
        expect(params.Expires).toBe(3600);
        callback(null, mockUrl);
      });

      const url = await s3Helper.getSignedUploadUrl('test.pdf', 'application/pdf');
      expect(url).toBe(mockUrl);
    });
  });

  describe('listVersions', () => {
    it('should list document versions', async () => {
      const mockVersions = [
        { VersionId: 'v1', LastModified: new Date() },
        { VersionId: 'v2', LastModified: new Date() }
      ];

      AWSMock.mock('S3', 'listObjectVersions', (params, callback) => {
        expect(params.Bucket).toBe(bucketName);
        expect(params.Prefix).toBe('test.pdf');
        callback(null, { Versions: mockVersions });
      });

      const versions = await s3Helper.listVersions('test.pdf');
      expect(versions).toEqual(mockVersions);
    });

    it('should return empty array when no versions exist', async () => {
      AWSMock.mock('S3', 'listObjectVersions', (params, callback) => {
        callback(null, {});
      });

      const versions = await s3Helper.listVersions('test.pdf');
      expect(versions).toEqual([]);
    });
  });
});
