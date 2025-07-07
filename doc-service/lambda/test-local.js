/**
 * Local test script for the document generation Lambda
 * Requires AWS credentials to be configured
 */
const { handler } = require('./src/index');

// Set environment variables
process.env.DOCUMENT_BUCKET = process.env.DOCUMENT_BUCKET || 'solopilot-dev-documents';
process.env.AWS_REGION = process.env.AWS_REGION || 'us-east-1';

async function testLambda() {
  console.log('Testing Document Generation Lambda...\n');
  console.log(`Bucket: ${process.env.DOCUMENT_BUCKET}`);
  console.log(`Region: ${process.env.AWS_REGION}\n`);
  
  const testCases = [
    {
      name: 'Valid Invoice',
      input: {
        clientId: 'client123',
        docType: 'invoice',
        filename: 'invoice-001.pdf',
        markdown: `# Invoice #001

**Client:** ACME Corporation  
**Date:** ${new Date().toLocaleDateString()}  
**Due Date:** ${new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toLocaleDateString()}

## Services

- Software Development: $5,000
- Technical Consulting: $2,500
- Support & Maintenance: $1,500

## Total: $9,000

Payment terms: Net 30`
      }
    },
    {
      name: 'Report Document',
      input: {
        clientId: 'client456',
        docType: 'report',
        filename: 'monthly-report.pdf',
        markdown: `# Monthly Progress Report

## Executive Summary

Project is on track with 85% completion.

## Key Achievements

- Completed user authentication module
- Deployed beta version to staging
- Conducted security audit

## Next Steps

- Final testing phase
- Production deployment
- User training`
      }
    },
    {
      name: 'Invalid Markdown (Error PDF)',
      input: {
        clientId: 'client789',
        docType: 'error-test',
        filename: 'error-doc.pdf',
        markdown: null
      }
    }
  ];
  
  const context = {
    requestId: 'local-test-' + Date.now()
  };
  
  for (const testCase of testCases) {
    console.log(`\n📋 Test Case: ${testCase.name}`);
    console.log('─'.repeat(40));
    
    try {
      const event = {
        body: JSON.stringify(testCase.input)
      };
      
      const startTime = Date.now();
      const result = await handler(event, context);
      const duration = Date.now() - startTime;
      
      const response = JSON.parse(result.body);
      
      if (result.statusCode === 200 && response.success) {
        console.log('✅ Success!');
        console.log(`📄 Document URL: ${response.documentUrl}`);
        console.log(`📁 S3 Key: ${response.s3Key}`);
        console.log(`📊 PDF Size: ${(response.pdfSize / 1024).toFixed(2)}KB`);
        console.log(`⚠️  Error PDF: ${response.isError ? 'Yes' : 'No'}`);
        console.log(`⏱️  Processing Time: ${response.metrics.processingTimeMs}ms`);
        console.log(`🔄 Total Time: ${duration}ms`);
      } else {
        console.log('❌ Failed!');
        console.log(`Status: ${result.statusCode}`);
        console.log(`Response: ${JSON.stringify(response, null, 2)}`);
      }
    } catch (error) {
      console.log('❌ Error:', error.message);
      console.log(error.stack);
    }
  }
  
  console.log('\n\n📌 Note: This test requires:');
  console.log('1. AWS credentials configured (aws configure)');
  console.log('2. S3 bucket exists or permission to create it');
  console.log('3. IAM permissions for S3 PutObject and GetObject');
}

// Run test
testLambda().catch(console.error);