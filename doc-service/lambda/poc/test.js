const { handler } = require('./index');
const fs = require('fs');
const path = require('path');

async function testLambda() {
  console.log('Testing React-PDF Lambda PoC...\n');
  
  const testMarkdown = `# Hello World

This is a test document to validate our React-PDF Lambda implementation.

## Key Features

- Markdown to PDF conversion
- Small package size
- Fast cold starts
- Low memory usage

## Technical Details

The Lambda uses React-PDF to generate PDFs from markdown input. This approach provides better control over styling and formatting compared to traditional HTML-to-PDF solutions.

### Performance Targets
- Package size: < 15MB
- Memory usage: < 128MB
- Cold start: < 1 second`;

  const event = {
    body: JSON.stringify({
      markdown: testMarkdown
    })
  };

  console.log('Input markdown length:', testMarkdown.length, 'characters\n');
  
  try {
    const startTime = Date.now();
    const result = await handler(event);
    const totalTime = Date.now() - startTime;
    
    const response = JSON.parse(result.body);
    
    if (response.success) {
      console.log('✅ PDF generation successful!');
      console.log('\nMetrics:');
      console.log(`- PDF size: ${(response.pdfSize / 1024).toFixed(2)}KB`);
      console.log(`- Processing time: ${response.metrics.processingTimeMs}ms`);
      console.log(`- Memory used: ${response.metrics.memoryUsedMB}MB`);
      console.log(`- Total execution time: ${totalTime}ms`);
      
      // Save PDF for manual inspection
      const pdfBuffer = Buffer.from(response.pdfBase64, 'base64');
      const outputPath = path.join(__dirname, 'test-output.pdf');
      fs.writeFileSync(outputPath, pdfBuffer);
      console.log(`\n📄 PDF saved to: ${outputPath}`);
      
      // Check package size
      console.log('\nChecking package size...');
      const { execSync } = require('child_process');
      
      try {
        // Install production dependencies
        execSync('npm ci --production', { stdio: 'inherit' });
        
        // Create zip and check size
        execSync('zip -r function.zip . -x "*.git*" -x "test*" -x "*.pdf"', { stdio: 'pipe' });
        const stats = fs.statSync('function.zip');
        const sizeMB = stats.size / 1024 / 1024;
        
        console.log(`\n📦 Lambda package size: ${sizeMB.toFixed(2)}MB`);
        
        if (sizeMB < 15) {
          console.log('✅ Package size is within target (<15MB)');
        } else {
          console.log('❌ Package size exceeds target (>15MB)');
        }
        
        // Clean up
        fs.unlinkSync('function.zip');
      } catch (error) {
        console.error('Error checking package size:', error.message);
      }
      
    } else {
      console.log('❌ PDF generation failed:', response.error);
    }
  } catch (error) {
    console.error('❌ Test failed:', error);
  }
}

// Test with invalid markdown
async function testInvalidMarkdown() {
  console.log('\n\n================================================');
  console.log('Testing Error Handling with Invalid Markdown...');
  console.log('================================================\n');
  
  const testCases = [
    {
      name: 'Null markdown',
      markdown: null,
      description: 'Testing with null input'
    },
    {
      name: 'Number instead of string',
      markdown: 12345,
      description: 'Testing with numeric input'
    },
    {
      name: 'Object instead of string',
      markdown: { invalid: 'data' },
      description: 'Testing with object input'
    },
    {
      name: 'Empty string',
      markdown: '',
      description: 'Testing with empty string'
    },
    {
      name: 'Undefined markdown',
      markdown: undefined,
      description: 'Testing with undefined input'
    }
  ];
  
  for (const testCase of testCases) {
    console.log(`\n🧪 Test Case: ${testCase.name}`);
    console.log(`   ${testCase.description}`);
    
    const event = {
      body: JSON.stringify({
        markdown: testCase.markdown
      })
    };
    
    try {
      const startTime = Date.now();
      const result = await handler(event);
      const totalTime = Date.now() - startTime;
      
      const response = JSON.parse(result.body);
      
      if (response.success) {
        if (response.isError) {
          console.log('   ✅ Error handled gracefully - Fallback PDF generated');
          console.log(`   - PDF size: ${(response.pdfSize / 1024).toFixed(2)}KB`);
          console.log(`   - Processing time: ${response.metrics.processingTimeMs}ms`);
          
          // Save error PDF for inspection
          const pdfBuffer = Buffer.from(response.pdfBase64, 'base64');
          const outputPath = path.join(__dirname, `test-error-${testCase.name.replace(/\s+/g, '-').toLowerCase()}.pdf`);
          fs.writeFileSync(outputPath, pdfBuffer);
          console.log(`   - Error PDF saved to: ${outputPath}`);
        } else {
          console.log('   ✅ PDF generated successfully (no error detected)');
        }
      } else {
        console.log('   ❌ Lambda returned failure:', response.error);
      }
    } catch (error) {
      console.log('   ❌ Lambda crashed:', error.message);
    }
  }
  
  console.log('\n================================================');
  console.log('Error Handling Tests Complete');
  console.log('================================================');
}

// Run all tests
async function runAllTests() {
  await testLambda();
  await testInvalidMarkdown();
  
  // Clean up error PDFs
  console.log('\nCleaning up test files...');
  const files = fs.readdirSync(__dirname);
  files.forEach(file => {
    if (file.startsWith('test-error-') && file.endsWith('.pdf')) {
      fs.unlinkSync(path.join(__dirname, file));
      console.log(`Removed: ${file}`);
    }
  });
}

// Run all tests
runAllTests();