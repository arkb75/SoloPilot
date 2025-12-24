/**
 * Template handler for different PDF templates
 */
const React = require('react');
const ReactPDF = require('@react-pdf/renderer');
const { renderToBuffer } = ReactPDF;
const vm = require('vm');
const fs = require('fs');
const path = require('path');

// Import templates
const GlassmorphicProposal = require('./templates/glassmorphic-proposal');
// You can add more templates here as needed
// const SimpleInvoice = require('./templates/simple-invoice');
// const ProjectReport = require('./templates/project-report');

/**
 * Generate PDF from template and data
 * @param {string} templateName - Name of the template to use
 * @param {object} data - Data to populate the template
 * @returns {Promise<Buffer>} PDF buffer
 */
async function generatePDFFromTemplate(templateName, data) {
  let TemplateComponent;

  // Select template based on name
  switch (templateName) {
    case 'glassmorphic-proposal':
      TemplateComponent = GlassmorphicProposal;
      break;

    // Add more templates as needed
    // case 'simple-invoice':
    //   TemplateComponent = SimpleInvoice;
    //   break;

    default:
      throw new Error(`Unknown template: ${templateName}`);
  }

  // Render the template with data
  const element = React.createElement(TemplateComponent, { data });
  const pdfBuffer = await renderToBuffer(element);

  return pdfBuffer;
}

/**
 * Generate PDF from a raw template module source string (JS) without redeploy.
 * Writes to /tmp and requires it dynamically.
 */
async function generatePDFFromOverride(templateSource, data) {
  // Normalize common ESM patterns to CJS for Lambda runtime
  try {
    let src = String(templateSource);
    src = src.replace(/export\s+default\s+/g, 'module.exports = ');
    src = src.replace(/import\s+React\s+from\s+['"]react['"];?/g, 'const React = require("react");');
    src = src.replace(/import\s+\{([^}]+)\}\s+from\s+['"]@react-pdf\/(renderer)['"];?/g, 'const {$1} = require("@react-pdf/renderer");');
    src = src.replace(/import\s+\*\s+as\s+(\w+)\s+from\s+['"]@react-pdf\/renderer['"];?/g, 'const $1 = require("@react-pdf/renderer");');

    const sandbox = {
      require: (name) => {
        if (name === 'react') return React;
        if (name === '@react-pdf/renderer') return ReactPDF;
        throw new Error(`Unsupported require in override: ${name}`);
      },
      module: { exports: {} },
      exports: {},
      React,
      ReactPDF,
      console,
    };
    vm.createContext(sandbox);
    const script = new vm.Script(src, { filename: 'template-override.js', displayErrors: true });
    script.runInContext(sandbox, { timeout: 1000 });
    const mod = sandbox.module.exports || sandbox.exports;
    const TemplateComponent = mod && mod.default ? mod.default : mod;
    if (typeof TemplateComponent !== 'function') {
      throw new Error('Override did not export a component');
    }
    const element = React.createElement(TemplateComponent, { data });
    const pdfBuffer = await renderToBuffer(element);
    return pdfBuffer;
  } catch (e) {
    // Re-throw to caller for fallback/error PDF handling
    throw e;
  }
}

/**
 * Validate template data
 * @param {string} templateName - Name of the template
 * @param {object} data - Data to validate
 * @returns {object} Validation result
 */
function validateTemplateData(templateName, data) {
  const errors = [];

  switch (templateName) {
    case 'glassmorphic-proposal':
      // Validate required fields for proposal
      if (!data.clientName) {
        errors.push('clientName is required');
      }
      if (!data.projectTitle) {
        errors.push('projectTitle is required');
      }
      // Other fields have defaults in the template
      break;

    default:
      errors.push(`Unknown template: ${templateName}`);
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * Get template metadata
 * @param {string} templateName - Name of the template
 * @returns {object} Template metadata
 */
function getTemplateMetadata(templateName) {
  const templates = {
    'glassmorphic-proposal': {
      name: 'Glassmorphic Proposal',
      description: 'Modern, clean proposal template with glassmorphic design',
      requiredFields: ['clientName', 'projectTitle'],
      optionalFields: ['proposalDate', 'scope', 'timeline', 'pricing', 'techStack'],
      defaultFilename: 'project-proposal.pdf'
    }
    // Add more templates here
  };

  return templates[templateName] || null;
}

module.exports = {
  generatePDFFromTemplate,
  validateTemplateData,
  getTemplateMetadata,
  generatePDFFromOverride
};
