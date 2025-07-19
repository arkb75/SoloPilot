const React = require('react');
const { Document, Page, Text, View, StyleSheet, Svg, Circle, Rect, Defs, LinearGradient, Stop } = require('@react-pdf/renderer');

// Modern color palette
const colors = {
  background: '#F6F7F8',
  backgroundLight: '#FFFFFF',
  glass: 'rgba(255, 255, 255, 0.7)',
  glassDark: 'rgba(255, 255, 255, 0.4)',
  text: '#1A1A1A',
  textLight: '#6B7280',
  accentStart: '#00C6FF',
  accentEnd: '#0072FF',
  shadow: 'rgba(0, 0, 0, 0.08)',
  neon: '#00C6FF',
};

// Create styles with glassmorphic effects
const styles = StyleSheet.create({
  page: {
    backgroundColor: colors.background,
    position: 'relative',
  },
  
  // Cover page styles
  coverPage: {
    padding: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  
  coverBackground: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.background,
  },
  
  coverLogoContainer: {
    width: 200,
    height: 200,
    borderRadius: 100,
    backgroundColor: colors.glass,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: `1px solid rgba(255, 255, 255, 0.2)`,
  },
  
  coverTitle: {
    fontSize: 48,
    fontFamily: 'Helvetica',
    fontWeight: 300,
    color: colors.text,
    marginTop: 40,
    textAlign: 'center',
  },
  
  coverSubtitle: {
    fontSize: 20,
    fontFamily: 'Helvetica',
    fontWeight: 300,
    color: colors.textLight,
    marginTop: 10,
    textAlign: 'center',
  },
  
  // Content page styles
  contentPage: {
    padding: 60,
  },
  
  // Glass panel styles
  glassPanel: {
    backgroundColor: colors.glass,
    borderRadius: 20,
    padding: 30,
    border: `1px solid rgba(255, 255, 255, 0.2)`,
    marginBottom: 20,
  },
  
  glassPanelDark: {
    backgroundColor: colors.glassDark,
  },
  
  // Typography
  h1: {
    fontSize: 36,
    fontFamily: 'Helvetica',
    fontWeight: 300,
    color: colors.text,
    marginBottom: 30,
  },
  
  h2: {
    fontSize: 24,
    fontFamily: 'Helvetica',
    fontWeight: 400,
    color: colors.text,
    marginBottom: 20,
  },
  
  h3: {
    fontSize: 18,
    fontFamily: 'Helvetica',
    fontWeight: 500,
    color: colors.text,
    marginBottom: 15,
  },
  
  body: {
    fontSize: 14,
    fontFamily: 'Helvetica',
    fontWeight: 300,
    color: colors.text,
    lineHeight: 1.6,
  },
  
  bodyLight: {
    color: colors.textLight,
  },
  
  // Scope cards
  scopeGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: 15,
  },
  
  scopeCard: {
    backgroundColor: colors.glass,
    borderRadius: 16,
    padding: 25,
    border: `1px solid rgba(255, 255, 255, 0.3)`,
  },
  
  scopeCardTitle: {
    fontSize: 18,
    fontFamily: 'Helvetica',
    fontWeight: 500,
    color: colors.text,
    marginBottom: 10,
  },
  
  scopeCardDescription: {
    fontSize: 13,
    fontFamily: 'Helvetica',
    fontWeight: 300,
    color: colors.textLight,
    lineHeight: 1.5,
  },
  
  // Timeline styles
  timeline: {
    position: 'relative',
    marginTop: 40,
    marginBottom: 40,
  },
  
  timelineTrack: {
    position: 'absolute',
    top: 25,
    left: 0,
    right: 0,
    height: 2,
    backgroundColor: colors.neon,
    opacity: 0.3,
  },
  
  timelineItems: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  
  timelineItem: {
    alignItems: 'center',
    width: 120,
  },
  
  timelineDot: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: colors.glass,
    border: `2px solid ${colors.neon}`,
    marginBottom: 10,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  
  timelineLabel: {
    fontSize: 12,
    fontFamily: 'Helvetica',
    fontWeight: 400,
    color: colors.text,
    textAlign: 'center',
  },
  
  // Pricing table
  pricingTable: {
    marginTop: 30,
  },
  
  pricingRow: {
    backgroundColor: colors.glass,
    borderRadius: 25,
    padding: 20,
    marginBottom: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    border: `1px solid rgba(255, 255, 255, 0.3)`,
  },
  
  pricingItem: {
    fontSize: 14,
    fontFamily: 'Helvetica',
    fontWeight: 400,
    color: colors.text,
  },
  
  pricingAmount: {
    fontSize: 16,
    fontFamily: 'Helvetica',
    fontWeight: 500,
    color: colors.text,
  },
  
  // Tech stack chips
  techStack: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginTop: 20,
  },
  
  techChip: {
    backgroundColor: colors.glass,
    borderRadius: 20,
    paddingHorizontal: 20,
    paddingVertical: 10,
    border: `1px solid rgba(255, 255, 255, 0.3)`,
  },
  
  techChipText: {
    fontSize: 12,
    fontFamily: 'Helvetica',
    fontWeight: 400,
    color: colors.text,
  },
  
  // Signature section
  signatureSection: {
    marginTop: 40,
    flexDirection: 'row',
    gap: 20,
  },
  
  signatureColumn: {
    flex: 1,
    backgroundColor: colors.glass,
    borderRadius: 16,
    padding: 30,
    border: `1px solid rgba(255, 255, 255, 0.2)`,
  },
  
  signatureLabel: {
    fontSize: 12,
    fontFamily: 'Helvetica',
    fontWeight: 400,
    color: colors.textLight,
    marginBottom: 30,
  },
  
  signatureLine: {
    borderBottomWidth: 1,
    borderBottomColor: colors.textLight,
    marginBottom: 10,
    opacity: 0.3,
  },
  
  // Gradient accent
  gradientAccent: {
    height: 4,
    marginVertical: 30,
    borderRadius: 2,
  },
  
  // Page number
  pageNumber: {
    position: 'absolute',
    bottom: 30,
    right: 60,
    fontSize: 10,
    fontFamily: 'Helvetica',
    fontWeight: 300,
    color: colors.textLight,
  },
});

// Gradient component
const GradientBar = () => React.createElement(
  Svg,
  { height: "4", width: "100%" },
  React.createElement(
    Defs,
    {},
    React.createElement(
      LinearGradient,
      { id: "gradient", x1: "0%", y1: "0%", x2: "100%", y2: "0%" },
      React.createElement(Stop, { offset: "0%", stopColor: colors.accentStart }),
      React.createElement(Stop, { offset: "100%", stopColor: colors.accentEnd })
    )
  ),
  React.createElement(Rect, { x: "0", y: "0", width: "100%", height: "4", fill: "url(#gradient)", rx: "2" })
);

// Logo placeholder component
const LogoPlaceholder = () => React.createElement(
  Svg,
  { width: "120", height: "120", viewBox: "0 0 120 120" },
  React.createElement(
    Defs,
    {},
    React.createElement(
      LinearGradient,
      { id: "logoGradient", x1: "0%", y1: "0%", x2: "100%", y2: "100%" },
      React.createElement(Stop, { offset: "0%", stopColor: colors.accentStart }),
      React.createElement(Stop, { offset: "100%", stopColor: colors.accentEnd })
    )
  ),
  React.createElement(Circle, { cx: "60", cy: "60", r: "50", fill: "url(#logoGradient)", opacity: "0.1" }),
  React.createElement(Text, { 
    x: "60", 
    y: "65", 
    textAnchor: "middle", 
    fontSize: "24", 
    fill: "url(#logoGradient)", 
    fontFamily: "Helvetica",
    style: { textAlign: 'center' }
  }, "LOGO")
);

// Main proposal template component
const GlassmorphicProposal = ({ data = {} }) => {
  const {
    clientName = 'Tesla Motors',
    projectTitle = 'Next-Generation Web Platform',
    proposalDate = 'January 2025',
    scope = [
      {
        title: 'Discovery & Research',
        description: 'Deep dive into user needs, competitive analysis, and technical requirements. Stakeholder interviews and journey mapping.',
      },
      {
        title: 'Design & Prototyping',
        description: 'Create high-fidelity designs with interactive prototypes. Establish design system and component library.',
      },
      {
        title: 'Development & Testing',
        description: 'Build responsive web application with modern tech stack. Implement CI/CD pipeline and comprehensive testing.',
      },
    ],
    timeline = [
      { phase: 'Discovery', duration: '2 weeks' },
      { phase: 'Design', duration: '3 weeks' },
      { phase: 'Development', duration: '8 weeks' },
      { phase: 'Testing', duration: '2 weeks' },
      { phase: 'Launch', duration: '1 week' },
    ],
    pricing = [
      { item: 'Discovery & Research', amount: '$1,500' },
      { item: 'Design & Prototyping', amount: '$3,500' },
      { item: 'Development', amount: '$12,000' },
      { item: 'Testing & QA', amount: '$2,000' },
      { item: 'Launch Support', amount: '$1,000' },
    ],
    techStack = ['React', 'Next.js', 'TypeScript', 'GraphQL', 'Node.js', 'PostgreSQL', 'Redis', 'Docker', 'AWS'],
  } = data;

  return React.createElement(
    Document,
    {},
    // Cover Page
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.coverPage] },
      React.createElement(View, { style: styles.coverBackground }),
      React.createElement(Text, { style: styles.coverTitle }, projectTitle),
      React.createElement(Text, { style: styles.coverSubtitle }, `Project Proposal for ${clientName}`),
      React.createElement(Text, { style: [styles.coverSubtitle, { marginTop: 40, fontSize: 16 }] }, proposalDate)
    ),

    // Executive Summary
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.contentPage] },
      React.createElement(Text, { style: styles.h1 }, "Executive Summary"),
      React.createElement(
        View,
        { style: styles.glassPanel },
        React.createElement(
          Text,
          { style: styles.body },
          "This proposal outlines our approach to designing and developing a next-generation web platform that embodies the principles of minimalist design, exceptional user experience, and cutting-edge technology."
        ),
        React.createElement(
          Text,
          { style: [styles.body, { marginTop: 15 }] },
          "Our solution will deliver a seamless, performant, and visually stunning digital experience that sets new standards in the industry while meeting all technical and business requirements."
        )
      ),
      React.createElement(GradientBar),
      React.createElement(Text, { style: styles.pageNumber }, "2")
    ),

    // Project Scope
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.contentPage] },
      React.createElement(Text, { style: styles.h1 }, "Project Scope"),
      React.createElement(
        View,
        { style: styles.scopeGrid },
        ...scope.map((item, index) =>
          React.createElement(
            View,
            { key: index, style: [styles.scopeCard, { marginLeft: index * 10 }] },
            React.createElement(Text, { style: styles.scopeCardTitle }, item.title),
            React.createElement(Text, { style: styles.scopeCardDescription }, item.description)
          )
        )
      ),
      React.createElement(Text, { style: styles.pageNumber }, "3")
    ),

    // Timeline
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.contentPage] },
      React.createElement(Text, { style: styles.h1 }, "Project Timeline"),
      React.createElement(
        View,
        { style: styles.timeline },
        React.createElement(View, { style: styles.timelineTrack }),
        React.createElement(
          View,
          { style: styles.timelineItems },
          ...timeline.map((item, index) =>
            React.createElement(
              View,
              { key: index, style: styles.timelineItem },
              React.createElement(
                View,
                { style: styles.timelineDot },
                React.createElement(Text, { style: { fontSize: 16, color: colors.neon } }, String(index + 1))
              ),
              React.createElement(Text, { style: styles.timelineLabel }, item.phase),
              React.createElement(Text, { style: [styles.timelineLabel, styles.bodyLight] }, item.duration)
            )
          )
        )
      ),
      React.createElement(GradientBar),
      React.createElement(Text, { style: styles.pageNumber }, "4")
    ),

    // Cost Breakdown
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.contentPage] },
      React.createElement(Text, { style: styles.h1 }, "Cost Breakdown"),
      React.createElement(
        View,
        { style: styles.pricingTable },
        ...pricing.map((item, index) =>
          React.createElement(
            View,
            { key: index, style: styles.pricingRow },
            React.createElement(Text, { style: styles.pricingItem }, item.item),
            React.createElement(Text, { style: styles.pricingAmount }, item.amount)
          )
        ),
        React.createElement(
          View,
          { style: [styles.pricingRow, { marginTop: 20, backgroundColor: colors.glassDark }] },
          React.createElement(Text, { style: [styles.pricingItem, { fontWeight: 500 }] }, "Total Cost"),
          React.createElement(Text, { style: [styles.pricingAmount, { fontSize: 20 }] }, "$20,000")
        )
      ),
      React.createElement(Text, { style: styles.pageNumber }, "5")
    ),

    // Technology Stack
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.contentPage] },
      React.createElement(Text, { style: styles.h1 }, "Technology Stack"),
      React.createElement(
        View,
        { style: styles.glassPanel },
        React.createElement(
          Text,
          { style: styles.body },
          "We've carefully selected a modern, scalable technology stack that ensures performance, maintainability, and future growth."
        ),
        React.createElement(
          View,
          { style: styles.techStack },
          ...techStack.map((tech, index) =>
            React.createElement(
              View,
              { key: index, style: styles.techChip },
              React.createElement(Text, { style: styles.techChipText }, tech)
            )
          )
        )
      ),
      React.createElement(GradientBar),
      React.createElement(Text, { style: styles.pageNumber }, "6")
    ),

    // Next Steps
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.contentPage] },
      React.createElement(Text, { style: styles.h1 }, "Next Steps"),
      React.createElement(
        View,
        { style: styles.glassPanel },
        React.createElement(Text, { style: styles.h2 }, "Immediate Actions"),
        React.createElement(Text, { style: styles.body }, "1. Schedule kickoff meeting to align on project vision"),
        React.createElement(Text, { style: styles.body }, "2. Finalize project timeline and milestones"),
        React.createElement(Text, { style: styles.body }, "3. Set up communication channels and project tools"),
        React.createElement(Text, { style: styles.body }, "4. Begin discovery phase with stakeholder interviews")
      ),
      React.createElement(
        View,
        { style: [styles.glassPanel, { marginTop: 30 }] },
        React.createElement(Text, { style: styles.h2 }, "Success Metrics"),
        React.createElement(Text, { style: styles.body }, "• Page load time under 2 seconds"),
        React.createElement(Text, { style: styles.body }, "• Mobile-first responsive design"),
        React.createElement(Text, { style: styles.body }, "• 95+ Lighthouse performance score"),
        React.createElement(Text, { style: styles.body }, "• WCAG 2.1 AA accessibility compliance")
      ),
      React.createElement(Text, { style: styles.pageNumber }, "7")
    ),

    // Signature Page
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.contentPage] },
      React.createElement(Text, { style: styles.h1 }, "Agreement"),
      React.createElement(
        View,
        { style: styles.signatureSection },
        React.createElement(
          View,
          { style: styles.signatureColumn },
          React.createElement(Text, { style: styles.signatureLabel }, "CLIENT"),
          React.createElement(View, { style: styles.signatureLine }),
          React.createElement(Text, { style: styles.bodyLight }, clientName),
          React.createElement(
            View,
            { style: { marginTop: 20 } },
            React.createElement(View, { style: styles.signatureLine }),
            React.createElement(Text, { style: styles.bodyLight }, "Date")
          )
        ),
        React.createElement(
          View,
          { style: styles.signatureColumn },
          React.createElement(Text, { style: styles.signatureLabel }, "FREELANCER"),
          React.createElement(View, { style: styles.signatureLine }),
          React.createElement(Text, { style: styles.bodyLight }, "[Your Name]"),
          React.createElement(
            View,
            { style: { marginTop: 20 } },
            React.createElement(View, { style: styles.signatureLine }),
            React.createElement(Text, { style: styles.bodyLight }, "Date")
          )
        )
      ),
      React.createElement(GradientBar),
      React.createElement(
        Text,
        { style: [styles.body, { marginTop: 30, textAlign: 'center', fontSize: 12 }] },
        "This proposal is valid for 30 days from the date of issue."
      ),
      React.createElement(Text, { style: styles.pageNumber }, "8")
    )
  );
};

module.exports = GlassmorphicProposal;