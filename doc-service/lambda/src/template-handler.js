/**
 * Template handler for different PDF templates
 */
const React = require('react');
const { renderToBuffer } = require('@react-pdf/renderer');

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
  getTemplateMetadata
};
