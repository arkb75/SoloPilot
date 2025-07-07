const AWS = require('aws-sdk');
const Stripe = require('stripe');
const { createLogger } = require('./logger');

const logger = createLogger();
const secretsManager = new AWS.SecretsManager();

/**
 * Stripe Helper Functions for Invoice Management
 */
class StripeHelper {
  constructor() {
    this.stripe = null;
    this.secretName = process.env.STRIPE_SECRET_NAME || 'solopilot/stripe/test';
  }
  
  /**
   * Initialize Stripe with keys from Secrets Manager
   */
  async initialize() {
    if (this.stripe) {
      return this.stripe;
    }
    
    try {
      logger.info('Retrieving Stripe keys from Secrets Manager', { 
        secretName: this.secretName 
      });
      
      const secret = await secretsManager.getSecretValue({
        SecretId: this.secretName
      }).promise();
      
      const secretData = JSON.parse(secret.SecretString);
      
      if (!secretData.secret_key) {
        throw new Error('Stripe secret key not found in secrets');
      }
      
      this.stripe = new Stripe(secretData.secret_key, {
        apiVersion: '2023-10-16',
        appInfo: {
          name: 'SoloPilot Document Generator',
          version: '1.0.0'
        }
      });
      
      logger.info('Stripe initialized successfully');
      return this.stripe;
    } catch (error) {
      logger.error('Failed to initialize Stripe', {
        error: error.message,
        stack: error.stack
      });
      throw error;
    }
  }
  
  /**
   * Create or retrieve a Stripe customer
   * @param {Object} customerData - Customer information
   * @returns {Promise<Object>} Stripe customer object
   */
  async createOrGetCustomer(customerData) {
    await this.initialize();
    
    const { clientId, email, name } = customerData;
    
    try {
      // Search for existing customer by clientId in metadata
      const existingCustomers = await this.stripe.customers.search({
        query: `metadata['clientId']:'${clientId}'`,
        limit: 1
      });
      
      if (existingCustomers.data.length > 0) {
        logger.info('Found existing Stripe customer', {
          customerId: existingCustomers.data[0].id,
          clientId
        });
        return existingCustomers.data[0];
      }
      
      // Create new customer
      const customer = await this.stripe.customers.create({
        email,
        name,
        metadata: {
          clientId,
          source: 'solopilot_doc_generator'
        }
      });
      
      logger.info('Created new Stripe customer', {
        customerId: customer.id,
        clientId
      });
      
      return customer;
    } catch (error) {
      logger.error('Failed to create/get Stripe customer', {
        error: error.message,
        clientId
      });
      throw error;
    }
  }
  
  /**
   * Upload a file to Stripe
   * @param {Buffer} fileBuffer - File content
   * @param {string} filename - File name
   * @param {string} purpose - File purpose (e.g., 'invoice_statement')
   * @returns {Promise<Object>} Stripe file object
   */
  async uploadFile(fileBuffer, filename, purpose = 'invoice_statement') {
    await this.initialize();
    
    try {
      logger.info('Uploading file to Stripe', { 
        filename,
        size: fileBuffer.length,
        purpose
      });
      
      // Note: Stripe file uploads require multipart/form-data
      // In production, you might need to use FormData or similar
      // For now, we'll skip the actual file upload and just log it
      logger.warn('File upload to Stripe not implemented - would upload:', {
        filename,
        size: fileBuffer.length
      });
      
      // Return mock file object for development
      return {
        id: 'file_mock_' + Date.now(),
        filename: filename,
        purpose: purpose,
        url: 'https://files.stripe.com/mock/' + filename
      };
      
    } catch (error) {
      logger.error('Failed to upload file to Stripe', {
        error: error.message,
        filename
      });
      throw error;
    }
  }
  
  /**
   * Parse line items from markdown content
   * @param {string} markdown - Markdown content
   * @returns {Array} Array of line items
   */
  parseLineItems(markdown) {
    const lineItems = [];
    const lines = markdown.split('\n');
    
    // Simple parser looking for patterns like "- Service: $1,000"
    const pricePattern = /[-•]\s*(.+?):\s*\$?([\d,]+(?:\.\d{2})?)/;
    
    lines.forEach(line => {
      const match = line.match(pricePattern);
      if (match) {
        const description = match[1].trim();
        const amount = parseInt(match[2].replace(/,/g, ''), 10) * 100; // Convert to cents
        
        if (!isNaN(amount) && amount > 0) {
          lineItems.push({
            description,
            amount,
            currency: 'usd',
            quantity: 1
          });
        }
      }
    });
    
    // If no line items found, create a default one
    if (lineItems.length === 0) {
      lineItems.push({
        description: 'Professional Services',
        amount: 0,
        currency: 'usd',
        quantity: 1
      });
    }
    
    return lineItems;
  }
  
  /**
   * Create a draft invoice with PDF attachment
   * @param {Object} invoiceData - Invoice information
   * @returns {Promise<Object>} Created invoice with URLs
   */
  async createInvoice(invoiceData) {
    await this.initialize();
    
    const {
      customer,
      lineItems,
      description,
      metadata = {},
      daysUntilDue = 30,
      pdfBuffer,
      pdfFilename
    } = invoiceData;
    
    try {
      // Create the invoice
      const invoice = await this.stripe.invoices.create({
        customer: customer.id,
        auto_advance: false, // Keep as draft
        collection_method: 'send_invoice',
        days_until_due: daysUntilDue,
        description,
        metadata: {
          ...metadata,
          source: 'solopilot_doc_generator'
        }
      });
      
      logger.info('Created Stripe invoice', {
        invoiceId: invoice.id,
        customerId: customer.id
      });
      
      // Add line items
      for (const item of lineItems) {
        await this.stripe.invoiceItems.create({
          customer: customer.id,
          invoice: invoice.id,
          description: item.description,
          amount: item.amount,
          currency: item.currency,
          quantity: item.quantity
        });
      }
      
      // Add PDF URL reference if provided
      let pdfAttached = false;
      if (metadata.documentUrl) {
        // Update invoice metadata with document URL
        await this.stripe.invoices.update(invoice.id, {
          metadata: {
            ...invoice.metadata,
            documentUrl: metadata.documentUrl,
            s3Key: metadata.s3Key
          },
          custom_fields: [{
            name: 'Document',
            value: metadata.documentUrl
          }]
        });
        
        pdfAttached = true;
        
        logger.info('Added document URL to invoice', {
          invoiceId: invoice.id,
          documentUrl: metadata.documentUrl
        });
      }
      
      // Fetch updated invoice with line items
      const updatedInvoice = await this.stripe.invoices.retrieve(invoice.id);
      
      logger.info('Invoice created successfully', {
        invoiceId: updatedInvoice.id,
        total: updatedInvoice.total,
        status: updatedInvoice.status,
        pdfAttached
      });
      
      return {
        invoice: updatedInvoice,
        pdfAttached
      };
    } catch (error) {
      logger.error('Failed to create invoice', {
        error: error.message,
        customerId: customer.id
      });
      throw error;
    }
  }
  
  /**
   * Finalize and send an invoice
   * @param {string} invoiceId - Stripe invoice ID
   * @returns {Promise<Object>} Finalized invoice
   */
  async finalizeInvoice(invoiceId) {
    await this.initialize();
    
    try {
      const invoice = await this.stripe.invoices.finalizeInvoice(invoiceId);
      
      logger.info('Invoice finalized', {
        invoiceId: invoice.id,
        status: invoice.status,
        hostedInvoiceUrl: invoice.hosted_invoice_url
      });
      
      return invoice;
    } catch (error) {
      logger.error('Failed to finalize invoice', {
        error: error.message,
        invoiceId
      });
      throw error;
    }
  }
}

// Export singleton instance
let stripeHelper;

exports.getStripeHelper = () => {
  if (!stripeHelper) {
    stripeHelper = new StripeHelper();
  }
  return stripeHelper;
};