const ReactPDF = require('@react-pdf/renderer');

// Sanitize metadata values for S3 compatibility
const sanitizeMetadata = (metadata) => {
  const sanitized = {};
  for (const [key, value] of Object.entries(metadata)) {
    if (value != null) {
      // Replace hyphens and other problematic characters with underscores
      sanitized[key] = String(value).replace(/[^a-zA-Z0-9_.]/g, '_');
    }
  }
  return sanitized;
};


const React = require('react');
const S3DocumentHelper = require('./s3-helpers');
const { getStripeHelper } = require('./stripe-helpers');
const { createLogger } = require('./logger');
const {
  generatePDFFromTemplate,
  validateTemplateData,
  getTemplateMetadata
} = require('./template-handler');

const { Document, Page, Text, View, StyleSheet, renderToBuffer } = ReactPDF;

// Initialize helpers
const BUCKET_NAME = process.env.DOCUMENT_BUCKET || 'solopilot-dev-documents';
const s3Helper = new S3DocumentHelper(BUCKET_NAME, process.env.AWS_REGION || 'us-east-1');
const stripeHelper = getStripeHelper();

// Create logger
const logger = createLogger();

// Create styles
const styles = StyleSheet.create({
  page: {
    padding: 40,
    fontSize: 12,
    fontFamily: 'Helvetica',
  },
  title: {
    fontSize: 24,
    marginBottom: 20,
    fontWeight: 'bold',
  },
  heading: {
    fontSize: 18,
    marginTop: 15,
    marginBottom: 10,
    fontWeight: 'bold',
  },
  paragraph: {
    marginBottom: 10,
    lineHeight: 1.5,
  },
  errorTitle: {
    fontSize: 20,
    marginBottom: 20,
    fontWeight: 'bold',
    color: '#d32f2f',
  },
  errorMessage: {
    fontSize: 14,
    marginBottom: 10,
    lineHeight: 1.5,
    color: '#666666',
  },
});

// Input validation
const validateInput = (body) => {
  const errors = [];

  // Check if this is a template-based request
  if (body.template) {
    // Template-based validation
    if (!body.clientId || typeof body.clientId !== 'string') {
      errors.push('clientId is required and must be a string');
    }

    // Validate template exists
    const templateMeta = getTemplateMetadata(body.template);
    if (!templateMeta) {
      errors.push(`Unknown template: ${body.template}`);
    } else {
      // Validate template data
      const validation = validateTemplateData(body.template, body.data || {});
      if (!validation.valid) {
        errors.push(...validation.errors);
      }
    }
  } else {
    // Markdown-based validation (existing)
    if (!body.clientId || typeof body.clientId !== 'string') {
      errors.push('clientId is required and must be a string');
    }

    if (!body.docType || typeof body.docType !== 'string') {
      errors.push('docType is required and must be a string');
    }

    if (!body.filename || typeof body.filename !== 'string') {
      errors.push('filename is required and must be a string');
    }

    if (!body.markdown || typeof body.markdown !== 'string') {
      errors.push('markdown is required and must be a string');
    }

    // Check markdown size (100KB limit)
    if (body.markdown && Buffer.byteLength(body.markdown, 'utf8') > 100 * 1024) {
      errors.push('markdown exceeds 100KB limit');
    }
  }

  // Validate Stripe fields if createInvoice is true
  if (body.createInvoice) {
    if (!body.customerEmail || typeof body.customerEmail !== 'string') {
      errors.push('customerEmail is required when createInvoice is true');
    }

    if (body.customerEmail && !body.customerEmail.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
      errors.push('customerEmail must be a valid email address');
    }
  }

  return errors;
};

// Sanitize filename
const sanitizeFilename = (filename) => {
  // Remove path traversal attempts and special characters
  return filename
    .replace(/\.\./g, '')
    .replace(/[\/\\]/g, '-')
    .replace(/[^a-zA-Z0-9\-_.]/g, '_')
    .substring(0, 255); // Limit filename length
};

// Create error PDF document
const createErrorPDF = (errorId) => {
  return React.createElement(
    Document,
    {},
    React.createElement(
      Page,
      { size: "A4", style: styles.page },
      React.createElement(
        View,
        {},
        React.createElement(
          Text,
          { style: styles.errorTitle },
          'Document Parse Error'
        ),
        React.createElement(
          Text,
          { style: styles.errorMessage },
          'We encountered an error while processing your document.'
        ),
        React.createElement(
          Text,
          { style: styles.errorMessage },
          'Please contact support for assistance.'
        ),
        React.createElement(
          Text,
          { style: { ...styles.errorMessage, marginTop: 20, fontSize: 12, color: '#999999' } },
          `Error ID: ${errorId}`
        )
      )
    )
  );
};

// Simple markdown parser
const parseMarkdown = (markdown) => {
  if (!markdown || typeof markdown !== 'string') {
    throw new Error('Invalid markdown input: must be a non-empty string');
  }

  const lines = markdown.split('\n');
  const elements = [];

  lines.forEach((line, index) => {
    if (line.startsWith('# ')) {
      elements.push({
        type: 'title',
        content: line.substring(2).trim(),
        key: `title-${index}`
      });
    } else if (line.startsWith('## ')) {
      elements.push({
        type: 'heading',
        content: line.substring(3).trim(),
        key: `heading-${index}`
      });
    } else if (line.trim() !== '') {
      elements.push({
        type: 'paragraph',
        content: line.trim(),
        key: `para-${index}`
      });
    }
  });

  return elements;
};

// Generate PDF from markdown
const generatePDF = async (markdown, errorId = null) => {
  let doc;
  let isError = false;

  try {
    // Parse markdown
    const elements = parseMarkdown(markdown);

    // Create PDF document
    const textElements = elements.map(element => {
      switch (element.type) {
        case 'title':
          return React.createElement(Text, { key: element.key, style: styles.title }, element.content);
        case 'heading':
          return React.createElement(Text, { key: element.key, style: styles.heading }, element.content);
        case 'paragraph':
          return React.createElement(Text, { key: element.key, style: styles.paragraph }, element.content);
        default:
          return null;
      }
    }).filter(el => el !== null);

    doc = React.createElement(
      Document,
      {},
      React.createElement(
        Page,
        { size: "A4", style: styles.page },
        React.createElement(
          View,
          {},
          ...textElements
        )
      )
    );
  } catch (parseError) {
    logger.error('Markdown parsing error', { error: parseError.message, stack: parseError.stack });
    doc = createErrorPDF(errorId);
    isError = true;
  }

  const pdfBuffer = await renderToBuffer(doc);
  return { pdfBuffer, isError };
};

// Lambda handler
exports.handler = async (event, context) => {
  const startTime = Date.now();
  const requestId = context.requestId;

  // Initialize logger with request context
  logger.setContext({ requestId });

  try {
    // Parse request body
    const body = event.body ? JSON.parse(event.body) : event;

    // Add clientId to logger context
    if (body.clientId) {
      logger.setContext({ clientId: body.clientId });
    }

    logger.info('Processing document generation request', {
      clientId: body.clientId,
      docType: body.docType,
      filename: body.filename,
      template: body.template,
      markdownLength: body.markdown ? body.markdown.length : 0
    });

    // Validate input
    const validationErrors = validateInput(body);
    if (validationErrors.length > 0) {
      logger.warn('Input validation failed', { errors: validationErrors });
      return {
        statusCode: 400,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          success: false,
          errors: validationErrors
        })
      };
    }

    // Determine filename and generate PDF
    let sanitizedFilename, pdfBuffer, isError = false;

    if (body.template) {
      // Template-based generation
      const templateMeta = getTemplateMetadata(body.template);
      sanitizedFilename = sanitizeFilename(body.filename || templateMeta.defaultFilename);
      if (!sanitizedFilename.endsWith('.pdf')) {
        sanitizedFilename += '.pdf';
      }

      try {
        logger.info('Generating PDF from template', { template: body.template });
        pdfBuffer = await generatePDFFromTemplate(body.template, body.data || {});
      } catch (templateError) {
        logger.error('Template generation error', {
          error: templateError.message,
          stack: templateError.stack
        });
        // Fall back to error PDF
        const errorDoc = createErrorPDF(requestId);
        pdfBuffer = await renderToBuffer(errorDoc);
        isError = true;
      }
    } else {
      // Markdown-based generation (existing)
      sanitizedFilename = sanitizeFilename(body.filename);
      if (!sanitizedFilename.endsWith('.pdf')) {
        sanitizedFilename += '.pdf';
      }

      logger.info('Generating PDF from markdown');
      const result = await generatePDF(body.markdown, requestId);
      pdfBuffer = result.pdfBuffer;
      isError = result.isError;
    }

    // Generate S3 key
    const docType = body.docType || (body.template ? 'template' : 'document');
    const s3Key = s3Helper.generateDocumentKey(
      body.clientId,
      docType,
      sanitizedFilename
    );

    logger.info('Generated PDF', { s3Key, size: pdfBuffer.length, isError });

    // Upload to S3
    logger.info('Uploading to S3', {
      bucketName: BUCKET_NAME,
      key: s3Key,
      size: pdfBuffer.length
    });

    await s3Helper.uploadDocument(
      s3Key,
      pdfBuffer,
      'application/pdf',
      sanitizeMetadata({
        clientId: body.clientId,
        docType: body.docType,
        originalFilename: body.filename,
        isError: isError.toString(),
        requestId: requestId
      })
    );

    // Generate signed URL
    const signedUrl = await s3Helper.getSignedDownloadUrl(s3Key, 86400); // 24 hours

    // Create Stripe invoice if requested
    let invoiceData = null;
    if (body.createInvoice && !isError) {
      try {
        logger.info('Creating Stripe invoice', {
          clientId: body.clientId,
          customerEmail: body.customerEmail
        });

        // Create or get customer
        const customer = await stripeHelper.createOrGetCustomer({
          clientId: body.clientId,
          email: body.customerEmail,
          name: body.customerName || body.clientId
        });

        // Parse line items from markdown
        const lineItems = stripeHelper.parseLineItems(body.markdown);

        // Create invoice with document URL reference
        const { invoice, pdfAttached } = await stripeHelper.createInvoice({
          customer,
          lineItems,
          description: body.invoiceDescription || `Document: ${body.filename}`,
          metadata: {
            clientId: body.clientId,
            docType: body.docType,
            s3Key,
            documentUrl: signedUrl
          },
          daysUntilDue: body.daysUntilDue || 30
        });

        invoiceData = {
          invoiceId: invoice.id,
          invoiceNumber: invoice.number,
          status: invoice.status,
          total: invoice.total,
          currency: invoice.currency,
          dueDate: invoice.due_date ? new Date(invoice.due_date * 1000).toISOString() : null,
          hostedInvoiceUrl: invoice.hosted_invoice_url,
          invoicePdf: invoice.invoice_pdf,
          customerId: customer.id,
          customerEmail: customer.email,
          documentUrlAttached: pdfAttached
        };

        logger.info('Stripe invoice created successfully', {
          invoiceId: invoice.id,
          total: invoice.total
        });
      } catch (stripeError) {
        logger.error('Failed to create Stripe invoice', {
          error: stripeError.message,
          type: stripeError.type,
          code: stripeError.code
        });

        // Don't fail the entire request if Stripe fails
        invoiceData = {
          error: 'Failed to create invoice',
          errorMessage: stripeError.message,
          errorCode: stripeError.code
        };
      }
    }

    const processingTime = Date.now() - startTime;

    logger.info('Document generation completed', {
      processingTimeMs: processingTime,
      pdfSize: pdfBuffer.length,
      isError,
      invoiceCreated: !!invoiceData && !invoiceData.error
    });

    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        success: true,
        documentUrl: signedUrl,
        s3Key,
        pdfSize: pdfBuffer.length,
        pdf: pdfBuffer.toString('base64'), // Include base64 PDF for direct attachment
        isError,
        template: body.template,
        invoice: invoiceData,
        metrics: {
          processingTimeMs: processingTime,
          requestId
        }
      })
    };

  } catch (error) {
    const processingTime = Date.now() - startTime;

    logger.error('Document generation failed', {
      error: error.message,
      stack: error.stack,
      processingTimeMs: processingTime
    });

    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        success: false,
        error: 'Internal server error',
        requestId
      })
    };
  }
};
