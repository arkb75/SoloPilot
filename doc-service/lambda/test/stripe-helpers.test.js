const AWSMock = require('aws-sdk-mock');
const { getStripeHelper } = require('../src/stripe-helpers');

// Mock Stripe
jest.mock('stripe', () => {
  return jest.fn().mockImplementation(() => ({
    customers: {
      search: jest.fn(),
      create: jest.fn()
    },
    files: {
      create: jest.fn()
    },
    invoices: {
      create: jest.fn(),
      retrieve: jest.fn(),
      update: jest.fn(),
      finalizeInvoice: jest.fn()
    },
    invoiceItems: {
      create: jest.fn()
    }
  }));
});

describe('StripeHelper', () => {
  let stripeHelper;
  let mockStripe;
  
  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();
    
    // Get fresh instance
    stripeHelper = getStripeHelper();
    
    // Mock Secrets Manager
    AWSMock.mock('SecretsManager', 'getSecretValue', (params, callback) => {
      callback(null, {
        SecretString: JSON.stringify({
          secret_key: 'sk_test_123456789'
        })
      });
    });
  });
  
  afterEach(() => {
    AWSMock.restore();
  });
  
  describe('initialize', () => {
    it('should retrieve Stripe keys from Secrets Manager', async () => {
      await stripeHelper.initialize();
      expect(stripeHelper.stripe).toBeDefined();
    });
    
    it('should handle missing secret key', async () => {
      AWSMock.restore('SecretsManager');
      AWSMock.mock('SecretsManager', 'getSecretValue', (params, callback) => {
        callback(null, {
          SecretString: JSON.stringify({})
        });
      });
      
      await expect(stripeHelper.initialize()).rejects.toThrow('Stripe secret key not found');
    });
  });
  
  describe('createOrGetCustomer', () => {
    beforeEach(async () => {
      await stripeHelper.initialize();
      mockStripe = stripeHelper.stripe;
    });
    
    it('should return existing customer if found', async () => {
      const existingCustomer = {
        id: 'cus_existing123',
        email: 'test@example.com'
      };
      
      mockStripe.customers.search.mockResolvedValue({
        data: [existingCustomer]
      });
      
      const result = await stripeHelper.createOrGetCustomer({
        clientId: 'client123',
        email: 'test@example.com',
        name: 'Test Client'
      });
      
      expect(result).toEqual(existingCustomer);
      expect(mockStripe.customers.search).toHaveBeenCalledWith({
        query: "metadata['clientId']:'client123'",
        limit: 1
      });
    });
    
    it('should create new customer if not found', async () => {
      const newCustomer = {
        id: 'cus_new123',
        email: 'test@example.com'
      };
      
      mockStripe.customers.search.mockResolvedValue({
        data: []
      });
      
      mockStripe.customers.create.mockResolvedValue(newCustomer);
      
      const result = await stripeHelper.createOrGetCustomer({
        clientId: 'client123',
        email: 'test@example.com',
        name: 'Test Client'
      });
      
      expect(result).toEqual(newCustomer);
      expect(mockStripe.customers.create).toHaveBeenCalledWith({
        email: 'test@example.com',
        name: 'Test Client',
        metadata: {
          clientId: 'client123',
          source: 'solopilot_doc_generator'
        }
      });
    });
  });
  
  describe('parseLineItems', () => {
    it('should parse line items from markdown', () => {
      const markdown = `# Invoice
      
- Web Development: $5,000
- Design Services: $2,500.50
- Hosting: $150

Total: $7,650.50`;
      
      const lineItems = stripeHelper.parseLineItems(markdown);
      
      expect(lineItems).toEqual([
        {
          description: 'Web Development',
          amount: 500000,
          currency: 'usd',
          quantity: 1
        },
        {
          description: 'Design Services',
          amount: 250050,
          currency: 'usd',
          quantity: 1
        },
        {
          description: 'Hosting',
          amount: 15000,
          currency: 'usd',
          quantity: 1
        }
      ]);
    });
    
    it('should handle different bullet formats', () => {
      const markdown = `
• Consulting: $1,000
- Development: $2,000
• Support: $500`;
      
      const lineItems = stripeHelper.parseLineItems(markdown);
      
      expect(lineItems).toHaveLength(3);
      expect(lineItems[0].description).toBe('Consulting');
      expect(lineItems[1].description).toBe('Development');
      expect(lineItems[2].description).toBe('Support');
    });
    
    it('should return default line item if none found', () => {
      const markdown = '# Document with no prices';
      
      const lineItems = stripeHelper.parseLineItems(markdown);
      
      expect(lineItems).toEqual([{
        description: 'Professional Services',
        amount: 0,
        currency: 'usd',
        quantity: 1
      }]);
    });
  });
  
  describe('createInvoice', () => {
    beforeEach(async () => {
      await stripeHelper.initialize();
      mockStripe = stripeHelper.stripe;
    });
    
    it('should create invoice with line items and PDF', async () => {
      const customer = { id: 'cus_123' };
      const lineItems = [{
        description: 'Service',
        amount: 100000,
        currency: 'usd',
        quantity: 1
      }];
      
      const mockInvoice = {
        id: 'inv_123',
        status: 'draft',
        total: 100000
      };
      
      const mockFile = {
        id: 'file_123',
        url: 'https://files.stripe.com/file_123'
      };
      
      mockStripe.invoices.create.mockResolvedValue(mockInvoice);
      mockStripe.invoices.retrieve.mockResolvedValue(mockInvoice);
      mockStripe.invoices.update.mockResolvedValue(mockInvoice);
      mockStripe.invoiceItems.create.mockResolvedValue({});
      
      const result = await stripeHelper.createInvoice({
        customer,
        lineItems,
        description: 'Test Invoice',
        metadata: { test: 'true' },
        daysUntilDue: 30,
        pdfBuffer: Buffer.from('test pdf'),
        pdfFilename: 'test.pdf'
      });
      
      expect(result.invoice).toEqual(mockInvoice);
      expect(result.pdfAttached).toBe(true);
      
      expect(mockStripe.invoices.create).toHaveBeenCalledWith({
        customer: 'cus_123',
        auto_advance: false,
        collection_method: 'send_invoice',
        days_until_due: 30,
        description: 'Test Invoice',
        metadata: {
          test: 'true',
          source: 'solopilot_doc_generator'
        }
      });
      
      expect(mockStripe.invoiceItems.create).toHaveBeenCalledWith({
        customer: 'cus_123',
        invoice: 'inv_123',
        description: 'Service',
        amount: 100000,
        currency: 'usd',
        quantity: 1
      });
    });
    
    it('should handle invoice creation without PDF', async () => {
      const customer = { id: 'cus_123' };
      const lineItems = [];
      
      const mockInvoice = {
        id: 'inv_123',
        status: 'draft'
      };
      
      mockStripe.invoices.create.mockResolvedValue(mockInvoice);
      mockStripe.invoices.retrieve.mockResolvedValue(mockInvoice);
      
      const result = await stripeHelper.createInvoice({
        customer,
        lineItems,
        description: 'Test Invoice'
      });
      
      expect(result.invoice).toEqual(mockInvoice);
      expect(result.pdfAttached).toBe(false);
    });
  });
});