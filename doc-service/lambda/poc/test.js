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

// Run test
testLambda();