// TODO: Migrate to AWS SDK v3 for better performance and smaller bundle size
// @aws-sdk/client-s3 provides modular imports that will reduce Lambda package size
const AWS = require('aws-sdk');

/**
 * S3 Helper Functions for Document Management
 */
class S3DocumentHelper {
  constructor(bucketName, region = 'us-east-1') {
    this.bucketName = bucketName;
    this.s3 = new AWS.S3({
      region,
      signatureVersion: 'v4'
    });
  }

  /**
   * Generate a signed URL for downloading a document
   * @param {string} key - S3 object key
   * @param {number} expiresIn - URL expiration in seconds (default: 24 hours)
   * @returns {Promise<string>} Signed URL
   */
  async getSignedDownloadUrl(key, expiresIn = 86400) {
    const params = {
      Bucket: this.bucketName,
      Key: key,
      Expires: expiresIn
    };

    return new Promise((resolve, reject) => {
      this.s3.getSignedUrl('getObject', params, (err, url) => {
        if (err) reject(err);
        else resolve(url);
      });
    });
  }

  /**
   * Generate a signed URL for uploading a document
   * @param {string} key - S3 object key
   * @param {string} contentType - MIME type of the document
   * @param {number} expiresIn - URL expiration in seconds (default: 1 hour)
   * @returns {Promise<string>} Signed URL
   */
  async getSignedUploadUrl(key, contentType, expiresIn = 3600) {
    const params = {
      Bucket: this.bucketName,
      Key: key,
      Expires: expiresIn,
      ContentType: contentType
    };

    return new Promise((resolve, reject) => {
      this.s3.getSignedUrl('putObject', params, (err, url) => {
        if (err) reject(err);
        else resolve(url);
      });
    });
  }

  /**
   * Upload a document to S3
   * @param {string} key - S3 object key
   * @param {Buffer|string} body - Document content
   * @param {string} contentType - MIME type of the document
   * @param {Object} metadata - Additional metadata
   * @returns {Promise<Object>} S3 upload response
   */
  async uploadDocument(key, body, contentType, metadata = {}) {
    const params = {
      Bucket: this.bucketName,
      Key: key,
      Body: body,
      ContentType: contentType,
      Metadata: metadata
    };

    return this.s3.putObject(params).promise();
  }

  /**
   * Download a document from S3
   * @param {string} key - S3 object key
   * @returns {Promise<Object>} S3 object with Body, ContentType, etc.
   */
  async downloadDocument(key) {
    const params = {
      Bucket: this.bucketName,
      Key: key
    };

    return this.s3.getObject(params).promise();
  }

  /**
   * List document versions
   * @param {string} key - S3 object key
   * @returns {Promise<Array>} Array of version objects
   */
  async listVersions(key) {
    const params = {
      Bucket: this.bucketName,
      Prefix: key
    };

    const result = await this.s3.listObjectVersions(params).promise();
    return result.Versions || [];
  }

  /**
   * Generate document key with proper structure
   * @param {string} conversationId - Conversation identifier
   * @param {string} docType - Document type (invoice, report, etc.)
   * @param {string} filename - Original filename
   * @returns {string} Structured S3 key
   */
  generateDocumentKey(conversationId, docType, filename) {
    const date = new Date();
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const timestamp = Date.now();

    return `${conversationId}/${year}/${month}/${docType}/${timestamp}-${filename}`;
  }
}

module.exports = S3DocumentHelper;
