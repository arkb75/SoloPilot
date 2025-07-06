const ReactPDF = require('@react-pdf/renderer');
const React = require('react');
const MarkdownIt = require('markdown-it');

const { Document, Page, Text, View, StyleSheet, renderToBuffer } = ReactPDF;
const md = new MarkdownIt();

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
});

// Simple markdown parser that returns text content
const parseMarkdown = (markdown) => {
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

// Lambda handler
exports.handler = async (event) => {
  const startTime = Date.now();
  const memoryStart = process.memoryUsage().heapUsed;
  
  try {
    // Extract markdown from event body
    const body = event.body ? JSON.parse(event.body) : event;
    const markdown = body.markdown || '# Default Document\n\nNo content provided.';
    
    console.log('Processing markdown:', markdown.substring(0, 100) + '...');
    
    // Parse markdown
    const elements = parseMarkdown(markdown);
    
    // Create PDF document using React.createElement
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
    
    const doc = React.createElement(
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
    
    // Generate PDF buffer
    const pdfBuffer = await renderToBuffer(doc);
    
    // Calculate metrics
    const processingTime = Date.now() - startTime;
    const memoryUsed = (process.memoryUsage().heapUsed - memoryStart) / 1024 / 1024;
    
    console.log(`PDF generated: ${pdfBuffer.length} bytes`);
    console.log(`Processing time: ${processingTime}ms`);
    console.log(`Memory used: ${memoryUsed.toFixed(2)}MB`);
    
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        success: true,
        pdfSize: pdfBuffer.length,
        pdfBase64: pdfBuffer.toString('base64'),
        metrics: {
          processingTimeMs: processingTime,
          memoryUsedMB: parseFloat(memoryUsed.toFixed(2)),
          lambdaMemoryMB: parseInt(process.env.AWS_LAMBDA_FUNCTION_MEMORY_SIZE || '128'),
        }
      }),
    };
  } catch (error) {
    console.error('Error generating PDF:', error);
    
    return {
      statusCode: 500,
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        success: false,
        error: error.message,
      }),
    };
  }
};