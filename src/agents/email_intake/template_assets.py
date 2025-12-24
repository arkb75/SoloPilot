"""Embedded React-PDF template assets for code-edit pipeline.

We embed the current glassmorphic-proposal.js content so the code model can
apply minimal edits against a stable snapshot. Doc-service can accept an
override of this file at render time.
"""

GLASSMORPHIC_PROPOSAL_JS = r"""
// BEGIN TEMPLATE: glassmorphic-proposal.js
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
  contentPage: {
    padding: 60,
  },
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
  timeline: { position: 'relative', marginTop: 40, marginBottom: 40 },
  timelineTrack: { position: 'absolute', top: 25, left: 0, right: 0, height: 2, backgroundColor: colors.neon, opacity: 0.3 },
  timelineItems: { flexDirection: 'row', justifyContent: 'space-between' },
  timelineItem: { alignItems: 'center', width: 120 },
  timelineDot: { width: 50, height: 50, borderRadius: 25, backgroundColor: colors.glass, border: `2px solid ${colors.neon}`, marginBottom: 10, display: 'flex', alignItems: 'center', justifyContent: 'center' },
  timelineLabel: { fontSize: 12, fontFamily: 'Helvetica', fontWeight: 400, color: colors.text, textAlign: 'center' },
  pricingTable: { marginTop: 30 },
  pricingRow: { backgroundColor: colors.glass, borderRadius: 25, padding: 20, marginBottom: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', border: `1px solid rgba(255, 255, 255, 0.3)` },
  pricingItem: { fontSize: 14, fontFamily: 'Helvetica', fontWeight: 400, color: colors.text },
  pricingAmount: { fontSize: 16, fontFamily: 'Helvetica', fontWeight: 500, color: colors.text },
  techStack: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 20 },
  techChip: { backgroundColor: colors.glass, borderRadius: 20, paddingHorizontal: 20, paddingVertical: 10, border: `1px solid rgba(255, 255, 255, 0.3)` },
  techChipText: { fontSize: 12, fontFamily: 'Helvetica', fontWeight: 400, color: colors.text },
  signatureSection: { marginTop: 40, flexDirection: 'row', gap: 20 },
  signatureColumn: { flex: 1, backgroundColor: colors.glass, borderRadius: 16, padding: 30, border: `1px solid rgba(255, 255, 255, 0.2)` },
  signatureLabel: { fontSize: 12, fontFamily: 'Helvetica', fontWeight: 400, color: colors.textLight, marginBottom: 30 },
  signatureLine: { borderBottomWidth: 1, borderBottomColor: colors.textLight, marginBottom: 10, opacity: 0.3 },
  gradientAccent: { height: 4, marginVertical: 30, borderRadius: 2 },
  pageNumber: { position: 'absolute', bottom: 30, right: 60, fontSize: 10, fontFamily: 'Helvetica', fontWeight: 300, color: colors.textLight },
});

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

const GlassmorphicProposal = ({ data = {} }) => {
  const {
    clientName = 'Tesla Motors',
    projectTitle = 'Next-Generation Web Platform',
    proposalDate = 'January 2025',
    scope = [],
    timeline = [],
    pricing = [],
    techStack = [],
  } = data;

  const calculateTotal = (items = []) => {
    try {
      const nums = items
        .map((i) => (typeof i.amount === 'string' ? i.amount.replace(/[$,]/g, '') : i.amount))
        .map((v) => parseFloat(v))
        .filter((v) => !isNaN(v));
      const sum = nums.reduce((acc, v) => acc + v, 0);
      return `$${sum.toLocaleString()}`;
    } catch (e) {
      return '';
    }
  };

  return React.createElement(
    Document,
    {},
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.coverPage] },
      React.createElement(LogoPlaceholder),
      React.createElement(Text, { style: styles.coverTitle }, projectTitle),
      React.createElement(Text, { style: styles.coverSubtitle }, clientName)
    ),
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.contentPage] },
      React.createElement(Text, { style: styles.h1 }, "Project Overview"),
      React.createElement(Text, { style: styles.body }, "This proposal outlines the scope, timeline, and pricing for your project."),
    ),
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.contentPage] },
      React.createElement(Text, { style: styles.h1 }, "Scope of Work"),
      React.createElement(
        View,
        { style: styles.scopeGrid },
        ...(scope || []).map((item, index) =>
          React.createElement(
            View,
            { key: index, style: styles.scopeCard },
            React.createElement(Text, { style: styles.scopeCardTitle }, item.title),
            React.createElement(Text, { style: styles.scopeCardDescription }, item.description)
          )
        )
      )
    ),
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.contentPage] },
      React.createElement(Text, { style: styles.h1 }, "Timeline"),
      React.createElement(View, { style: styles.timeline },
        React.createElement(View, { style: styles.timelineTrack }),
        React.createElement(View, { style: styles.timelineItems },
          ...(timeline || []).map((phase, index) =>
            React.createElement(
              View,
              { key: index, style: styles.timelineItem },
              React.createElement(View, { style: styles.timelineDot }, React.createElement(Text, null, index + 1)),
              React.createElement(Text, { style: styles.timelineLabel }, `${phase.phase} — ${phase.duration}`)
            )
          )
        )
      )
    ),
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.contentPage] },
      React.createElement(Text, { style: styles.h1 }, "Cost Breakdown"),
      React.createElement(
        View,
        { style: styles.pricingTable },
        ...(pricing || []).map((item, index) =>
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
          React.createElement(Text, { style: [styles.pricingAmount, { fontSize: 20 }] }, calculateTotal(pricing))
        )
      )
    ),
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
          ...(techStack || []).map((tech, index) =>
            React.createElement(
              View,
              { key: index, style: styles.techChip },
              React.createElement(Text, { style: styles.techChipText }, tech)
            )
          )
        )
      )
    )
  );
};

module.exports = GlassmorphicProposal;
// END TEMPLATE
"""

