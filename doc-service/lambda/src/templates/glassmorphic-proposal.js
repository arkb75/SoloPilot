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

const PAGE_SIZE = { width: 595.28, height: 841.89 };
const PAGE_PADDING = 60;
const CONTENT_WIDTH = PAGE_SIZE.width - (PAGE_PADDING * 2);
const CONTENT_HEIGHT = PAGE_SIZE.height - (PAGE_PADDING * 2);
const SECTION_BOTTOM_BUFFER = 60;
const SCALE_STEPS = [1, 0.95, 0.9, 0.85, 0.8, 0.75];

const FONT = {
  h1: 36,
  h1Margin: 30,
  h2: 24,
  h2Margin: 20,
  body: 14,
  bodyLine: 1.6,
  scopeTitle: 18,
  scopeTitleMargin: 10,
  scopeDesc: 13,
  scopeDescLine: 1.5,
};

const PANEL = {
  padding: 30,
  radius: 20,
};

const SCOPE_CARD = {
  padding: 25,
  radius: 16,
  gap: 15,
  indent: 10,
};

const PRICING_ROW = {
  padding: 20,
  radius: 25,
  gap: 10,
  itemSize: 14,
  amountSize: 16,
  totalSize: 20,
  totalMargin: 20,
};

const TECH_CHIP = {
  paddingX: 20,
  paddingY: 10,
  radius: 20,
  gap: 10,
  fontSize: 12,
};

const NEXT_STEPS = {
  panelGap: 30,
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
    padding: PAGE_PADDING,
  },

  // Glass panel styles
  glassPanel: {
    backgroundColor: colors.glass,
    borderRadius: PANEL.radius,
    padding: PANEL.padding,
    border: `1px solid rgba(255, 255, 255, 0.2)`,
    marginBottom: 20,
  },

  glassPanelDark: {
    backgroundColor: colors.glassDark,
  },

  // Typography
  h1: {
    fontSize: FONT.h1,
    fontFamily: 'Helvetica',
    fontWeight: 300,
    color: colors.text,
    marginBottom: FONT.h1Margin,
  },

  h2: {
    fontSize: FONT.h2,
    fontFamily: 'Helvetica',
    fontWeight: 400,
    color: colors.text,
    marginBottom: FONT.h2Margin,
  },

  h3: {
    fontSize: 18,
    fontFamily: 'Helvetica',
    fontWeight: 500,
    color: colors.text,
    marginBottom: 15,
  },

  body: {
    fontSize: FONT.body,
    fontFamily: 'Helvetica',
    fontWeight: 300,
    color: colors.text,
    lineHeight: FONT.bodyLine,
  },

  bodyLight: {
    color: colors.textLight,
  },

  // Scope cards
  scopeGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: 0,
  },

  scopeCard: {
    backgroundColor: colors.glass,
    borderRadius: SCOPE_CARD.radius,
    padding: SCOPE_CARD.padding,
    border: `1px solid rgba(255, 255, 255, 0.3)`,
  },

  scopeCardTitle: {
    fontSize: FONT.scopeTitle,
    fontFamily: 'Helvetica',
    fontWeight: 500,
    color: colors.text,
    marginBottom: FONT.scopeTitleMargin,
  },

  scopeCardDescription: {
    fontSize: FONT.scopeDesc,
    fontFamily: 'Helvetica',
    fontWeight: 300,
    color: colors.textLight,
    lineHeight: FONT.scopeDescLine,
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
    borderRadius: PRICING_ROW.radius,
    padding: PRICING_ROW.padding,
    marginBottom: PRICING_ROW.gap,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    border: `1px solid rgba(255, 255, 255, 0.3)`,
  },

  pricingItem: {
    fontSize: PRICING_ROW.itemSize,
    fontFamily: 'Helvetica',
    fontWeight: 400,
    color: colors.text,
  },

  pricingAmount: {
    fontSize: PRICING_ROW.amountSize,
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
    borderRadius: TECH_CHIP.radius,
    paddingHorizontal: TECH_CHIP.paddingX,
    paddingVertical: TECH_CHIP.paddingY,
    border: `1px solid rgba(255, 255, 255, 0.3)`,
  },

  techChipText: {
    fontSize: TECH_CHIP.fontSize,
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

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const estimateCharsPerLine = (width, fontSize) => {
  const avgCharWidth = fontSize * 0.55;
  return Math.max(12, Math.floor(width / avgCharWidth));
};

const splitTextToLines = (text, charsPerLine) => {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  const lines = [];
  let current = '';
  words.forEach((word) => {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length > charsPerLine && current) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  });
  if (current) lines.push(current);
  return lines;
};

const estimateLineCount = (text, charsPerLine) => splitTextToLines(text, charsPerLine).length || 1;

const truncateTextToLines = (text, maxLines, charsPerLine) => {
  if (maxLines <= 0) return '';
  const lines = splitTextToLines(text, charsPerLine);
  if (lines.length <= maxLines) return text;
  const truncated = lines.slice(0, maxLines).join(' ').trim();
  return `${truncated}...`;
};

const allocateLineBudget = (lineCounts, maxLinesTotal, minLinesPerItem) => {
  const count = lineCounts.length;
  if (count === 0) return [];
  const minTotal = minLinesPerItem * count;
  let remaining = Math.max(maxLinesTotal, minTotal);
  let remainingItems = count;
  return lineCounts.map((lines) => {
    const minForItem = Math.min(minLinesPerItem, lines);
    const maxAllowed = remaining - minLinesPerItem * (remainingItems - 1);
    const allowed = clamp(lines, minForItem, Math.max(minForItem, maxAllowed));
    remaining -= allowed;
    remainingItems -= 1;
    return Math.max(1, allowed);
  });
};

const getHeaderHeight = () => (FONT.h1 * 1.2) + FONT.h1Margin;

const fitExecutiveSummaryLayout = (paragraphs) => {
  const safeParagraphs = Array.isArray(paragraphs) ? paragraphs.filter(Boolean) : [];
  const headerHeight = getHeaderHeight();
  const availableHeight = CONTENT_HEIGHT - headerHeight - SECTION_BOTTOM_BUFFER;

  const measure = (scale, content) => {
    const panelPadding = PANEL.padding * scale;
    const bodySize = FONT.body * scale;
    const paragraphGap = 15 * scale;
    const textWidth = CONTENT_WIDTH - (panelPadding * 2);
    const charsPerLine = estimateCharsPerLine(textWidth, bodySize);
    const lineCounts = content.map((paragraph) => estimateLineCount(paragraph, charsPerLine));
    const textHeight = lineCounts.reduce((sum, lines, idx) => {
      const block = lines * bodySize * FONT.bodyLine;
      return sum + block + (idx > 0 ? paragraphGap : 0);
    }, 0);
    const panelHeight = (panelPadding * 2) + textHeight;
    return {
      panelHeight,
      panelPadding,
      bodySize,
      paragraphGap,
      charsPerLine,
      lineCounts,
      scale,
    };
  };

  for (const scale of SCALE_STEPS) {
    const metrics = measure(scale, safeParagraphs);
    if (metrics.panelHeight <= availableHeight) {
      return { ...metrics, paragraphs: safeParagraphs };
    }
  }

  const minScale = SCALE_STEPS[SCALE_STEPS.length - 1];
  const metrics = measure(minScale, safeParagraphs);
  const lineHeight = metrics.bodySize * FONT.bodyLine;
  const fixedHeight = (metrics.panelPadding * 2) + (metrics.paragraphGap * Math.max(0, safeParagraphs.length - 1));
  const maxLinesTotal = Math.floor((availableHeight - fixedHeight) / lineHeight);
  const minLinesPerItem = maxLinesTotal < safeParagraphs.length * 2 ? 1 : 2;
  const allocated = allocateLineBudget(metrics.lineCounts, maxLinesTotal, minLinesPerItem);
  const trimmed = safeParagraphs.map((paragraph, idx) => (
    truncateTextToLines(paragraph, allocated[idx], metrics.charsPerLine)
  ));
  return { ...metrics, paragraphs: trimmed };
};

const fitScopeLayout = (items) => {
  const safeItems = Array.isArray(items)
    ? items.map((item) => ({
        title: item.title || '',
        description: item.description || '',
      }))
    : [];
  const headerHeight = getHeaderHeight();
  const availableHeight = CONTENT_HEIGHT - headerHeight - SECTION_BOTTOM_BUFFER;

  const measure = (scale, content) => {
    const cardPadding = SCOPE_CARD.padding * scale;
    const cardGap = SCOPE_CARD.gap * scale;
    const titleSize = FONT.scopeTitle * scale;
    const titleMargin = FONT.scopeTitleMargin * scale;
    const descSize = FONT.scopeDesc * scale;
    const textWidth = CONTENT_WIDTH - (cardPadding * 2) - (SCOPE_CARD.indent * scale);
    const charsPerLine = estimateCharsPerLine(textWidth, descSize);
    const descLines = content.map((item) => estimateLineCount(item.description, charsPerLine));
    const titleHeight = titleSize * 1.2;
    const totalHeight = descLines.reduce((sum, lines, idx) => {
      const descHeight = lines * descSize * FONT.scopeDescLine;
      const cardHeight = (cardPadding * 2) + titleHeight + titleMargin + descHeight;
      return sum + cardHeight + (idx < descLines.length - 1 ? cardGap : 0);
    }, 0);
    return {
      cardPadding,
      cardGap,
      titleSize,
      titleMargin,
      descSize,
      descLines,
      charsPerLine,
      totalHeight,
      scale,
      titleHeight,
    };
  };

  for (const scale of SCALE_STEPS) {
    const metrics = measure(scale, safeItems);
    if (metrics.totalHeight <= availableHeight) {
      return { ...metrics, items: safeItems };
    }
  }

  const minScale = SCALE_STEPS[SCALE_STEPS.length - 1];
  const metrics = measure(minScale, safeItems);
  const lineHeight = metrics.descSize * FONT.scopeDescLine;
  const fixedPerCard = (metrics.cardPadding * 2) + metrics.titleHeight + metrics.titleMargin;
  const fixedHeight = (fixedPerCard * safeItems.length) + (metrics.cardGap * Math.max(0, safeItems.length - 1));
  const maxLinesTotal = Math.floor((availableHeight - fixedHeight) / lineHeight);
  const minLinesPerItem = maxLinesTotal < safeItems.length * 2 ? 1 : 2;
  const allocated = allocateLineBudget(metrics.descLines, maxLinesTotal, minLinesPerItem);
  const trimmed = safeItems.map((item, idx) => ({
    ...item,
    description: truncateTextToLines(item.description, allocated[idx], metrics.charsPerLine),
  }));
  return { ...metrics, items: trimmed };
};

const parseAmount = (value) => {
  const cleaned = String(value || '').replace(/[^0-9.-]/g, '');
  const parsed = parseFloat(cleaned);
  return Number.isFinite(parsed) ? parsed : 0;
};

const formatAmount = (value) => `$${Math.round(value).toLocaleString()}`;

const fitPricingLayout = (rows) => {
  const safeRows = Array.isArray(rows)
    ? rows.map((row) => ({ item: row.item || '', amount: row.amount || '' }))
    : [];
  const headerHeight = getHeaderHeight();
  const availableHeight = CONTENT_HEIGHT - headerHeight - SECTION_BOTTOM_BUFFER;

  const measure = (scale, rowCount) => {
    const rowPadding = PRICING_ROW.padding * scale;
    const rowGap = PRICING_ROW.gap * scale;
    const itemSize = PRICING_ROW.itemSize * scale;
    const amountSize = PRICING_ROW.amountSize * scale;
    const totalSize = PRICING_ROW.totalSize * scale;
    const rowHeight = (rowPadding * 2) + (Math.max(itemSize, amountSize) * 1.2);
    const totalRowHeight = (rowPadding * 2) + (totalSize * 1.2);
    const totalMargin = PRICING_ROW.totalMargin * scale;
    const totalHeight = (rowHeight * rowCount)
      + (rowGap * Math.max(0, rowCount - 1))
      + totalRowHeight
      + totalMargin;
    return {
      rowPadding,
      rowGap,
      itemSize,
      amountSize,
      totalSize,
      rowHeight,
      totalRowHeight,
      totalMargin,
      totalHeight,
      scale,
    };
  };

  for (const scale of SCALE_STEPS) {
    const metrics = measure(scale, safeRows.length);
    if (metrics.totalHeight <= availableHeight) {
      return { ...metrics, rows: safeRows };
    }
  }

  const minScale = SCALE_STEPS[SCALE_STEPS.length - 1];
  const metrics = measure(minScale, safeRows.length);
  const availableForRows = availableHeight - metrics.totalRowHeight - metrics.totalMargin;
  const slotHeight = metrics.rowHeight + metrics.rowGap;
  const maxRows = Math.max(1, Math.floor((availableForRows + metrics.rowGap) / slotHeight));
  let displayRows = safeRows;
  if (safeRows.length > maxRows) {
    const keepCount = Math.max(1, maxRows - 1);
    const kept = safeRows.slice(0, keepCount);
    const remaining = safeRows.slice(keepCount);
    const remainderTotal = remaining.reduce((sum, row) => sum + parseAmount(row.amount), 0);
    displayRows = kept.concat({
      item: `Additional items (${remaining.length})`,
      amount: formatAmount(remainderTotal),
    });
  }
  return { ...metrics, rows: displayRows };
};

const fitNextStepsLayout = (steps, metricsList) => {
  const safeSteps = Array.isArray(steps) ? steps.filter(Boolean) : [];
  const safeMetrics = Array.isArray(metricsList) ? metricsList.filter(Boolean) : [];
  const headerHeight = getHeaderHeight();
  const availableHeight = CONTENT_HEIGHT - headerHeight - SECTION_BOTTOM_BUFFER;

  const measure = (scale, stepsText, metricsText) => {
    const panelPadding = PANEL.padding * scale;
    const panelGap = NEXT_STEPS.panelGap * scale;
    const h2Size = FONT.h2 * scale;
    const h2Margin = FONT.h2Margin * scale;
    const bodySize = FONT.body * scale;
    const textWidth = CONTENT_WIDTH - (panelPadding * 2);
    const charsPerLine = estimateCharsPerLine(textWidth, bodySize);

    const stepLines = stepsText.map((text) => estimateLineCount(text, charsPerLine));
    const metricLines = metricsText.map((text) => estimateLineCount(text, charsPerLine));

    const panelFixed = (panelPadding * 2) + (h2Size * 1.2) + h2Margin;
    const stepHeight = panelFixed + stepLines.reduce((sum, lines) => sum + (lines * bodySize * FONT.bodyLine), 0);
    const metricHeight = panelFixed + metricLines.reduce((sum, lines) => sum + (lines * bodySize * FONT.bodyLine), 0);

    const totalHeight = stepHeight + metricHeight + panelGap;
    return {
      panelPadding,
      panelGap,
      h2Size,
      h2Margin,
      bodySize,
      charsPerLine,
      stepLines,
      metricLines,
      stepHeight,
      metricHeight,
      totalHeight,
      scale,
    };
  };

  const stepTexts = safeSteps.map((step, idx) => `${idx + 1}. ${step}`);
  const metricTexts = safeMetrics.map((metric) => `• ${metric}`);

  for (const scale of SCALE_STEPS) {
    const metrics = measure(scale, stepTexts, metricTexts);
    if (metrics.totalHeight <= availableHeight) {
      return { ...metrics, steps: safeSteps, metrics: safeMetrics };
    }
  }

  const minScale = SCALE_STEPS[SCALE_STEPS.length - 1];
  const metrics = measure(minScale, stepTexts, metricTexts);
  const lineHeight = metrics.bodySize * FONT.bodyLine;
  const panelFixed = (metrics.panelPadding * 2) + (metrics.h2Size * 1.2) + metrics.h2Margin;
  const fixedTotal = (panelFixed * 2) + metrics.panelGap;
  const maxLinesTotal = Math.floor((availableHeight - fixedTotal) / lineHeight);
  const naturalStepLines = metrics.stepLines.reduce((sum, lines) => sum + lines, 0);
  const naturalMetricLines = metrics.metricLines.reduce((sum, lines) => sum + lines, 0);
  const totalNatural = naturalStepLines + naturalMetricLines;
  const share = totalNatural > 0 ? naturalStepLines / totalNatural : 0.5;
  const stepBudget = Math.floor(maxLinesTotal * share);
  const metricBudget = Math.max(0, maxLinesTotal - stepBudget);
  const stepAllocated = allocateLineBudget(metrics.stepLines, stepBudget, 1);
  const metricAllocated = allocateLineBudget(metrics.metricLines, metricBudget, 1);

  const stepCharsPerLine = Math.max(8, metrics.charsPerLine - 4);
  const metricCharsPerLine = Math.max(8, metrics.charsPerLine - 2);
  const trimmedSteps = safeSteps.map((step, idx) => (
    truncateTextToLines(step, stepAllocated[idx], stepCharsPerLine)
  ));
  const trimmedMetrics = safeMetrics.map((metric, idx) => (
    truncateTextToLines(metric, metricAllocated[idx], metricCharsPerLine)
  ));

  return { ...metrics, steps: trimmedSteps, metrics: trimmedMetrics };
};

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
    clientName = '',
    projectTitle = '',
    proposalDate = '',
    executiveSummaryParagraphs = [],
    scope = [],
    timeline = [],
    pricing = [],
    techStackIntro = '',
    techStack = [],
    nextSteps = [],
    successMetrics = [],
    freelancerName = '',
    validityNote = '',
  } = data;

  const execSummaryLayout = fitExecutiveSummaryLayout(executiveSummaryParagraphs);
  const scopeLayout = fitScopeLayout(scope);
  const pricingLayout = fitPricingLayout(pricing);
  const nextStepsLayout = fitNextStepsLayout(nextSteps, successMetrics);

  // Calculate total from pricing items
  const calculateTotal = (pricingItems) => {
    const total = pricingItems.reduce((sum, item) => {
      // Parse the amount string (e.g., "$1,500" -> 1500)
      const cleanAmount = item.amount.replace(/[$,]/g, '');
      const amount = parseInt(cleanAmount, 10) || 0;
      return sum + amount;
    }, 0);
    
    // Format with thousands separator
    return `$${total.toLocaleString()}`;
  };

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
        { style: [styles.glassPanel, { padding: execSummaryLayout.panelPadding }], wrap: false },
        ...execSummaryLayout.paragraphs.map((paragraph, index) =>
          React.createElement(
            Text,
            {
              key: `summary-${index}`,
              style: [
                styles.body,
                { fontSize: execSummaryLayout.bodySize, lineHeight: FONT.bodyLine },
                index > 0 ? { marginTop: execSummaryLayout.paragraphGap } : null,
              ],
            },
            paragraph
          )
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
        ...scopeLayout.items.map((item, index) =>
          React.createElement(
            View,
            {
              key: index,
              style: [
                styles.scopeCard,
                {
                  padding: scopeLayout.cardPadding,
                  borderRadius: SCOPE_CARD.radius * scopeLayout.scale,
                  marginLeft: index * SCOPE_CARD.indent * scopeLayout.scale,
                  marginBottom: index < scopeLayout.items.length - 1 ? scopeLayout.cardGap : 0,
                },
              ],
              wrap: false,
            },
            React.createElement(
              Text,
              { style: [styles.scopeCardTitle, { fontSize: scopeLayout.titleSize, marginBottom: scopeLayout.titleMargin }] },
              item.title
            ),
            React.createElement(
              Text,
              { style: [styles.scopeCardDescription, { fontSize: scopeLayout.descSize, lineHeight: FONT.scopeDescLine }] },
              item.description
            )
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
        ...pricingLayout.rows.map((item, index) =>
          React.createElement(
            View,
            {
              key: index,
              style: [
                styles.pricingRow,
                {
                  padding: pricingLayout.rowPadding,
                  borderRadius: PRICING_ROW.radius * pricingLayout.scale,
                  marginBottom: index < pricingLayout.rows.length - 1 ? pricingLayout.rowGap : 0,
                },
              ],
              wrap: false,
            },
            React.createElement(Text, { style: [styles.pricingItem, { fontSize: pricingLayout.itemSize }] }, item.item),
            React.createElement(Text, { style: [styles.pricingAmount, { fontSize: pricingLayout.amountSize }] }, item.amount)
          )
        ),
        React.createElement(
          View,
          {
            style: [
              styles.pricingRow,
              {
                marginTop: PRICING_ROW.totalMargin * pricingLayout.scale,
                backgroundColor: colors.glassDark,
                padding: pricingLayout.rowPadding,
                borderRadius: PRICING_ROW.radius * pricingLayout.scale,
              },
            ],
            wrap: false,
          },
          React.createElement(Text, { style: [styles.pricingItem, { fontWeight: 500, fontSize: pricingLayout.itemSize }] }, "Total Cost"),
          React.createElement(Text, { style: [styles.pricingAmount, { fontSize: pricingLayout.totalSize }] }, calculateTotal(pricingLayout.rows))
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
        techStackIntro
          ? React.createElement(
              Text,
              { style: styles.body },
              techStackIntro
            )
          : null,
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
        { style: [styles.glassPanel, { padding: nextStepsLayout.panelPadding }], wrap: false },
        React.createElement(Text, { style: [styles.h2, { fontSize: nextStepsLayout.h2Size, marginBottom: nextStepsLayout.h2Margin }] }, "Immediate Actions"),
        ...nextStepsLayout.steps.map((step, index) =>
          React.createElement(
            Text,
            {
              key: `next-${index}`,
              style: [styles.body, { fontSize: nextStepsLayout.bodySize, lineHeight: FONT.bodyLine }],
            },
            `${index + 1}. ${step}`
          )
        )
      ),
      React.createElement(
        View,
        { style: [styles.glassPanel, { marginTop: NEXT_STEPS.panelGap * nextStepsLayout.scale, padding: nextStepsLayout.panelPadding }], wrap: false },
        React.createElement(Text, { style: [styles.h2, { fontSize: nextStepsLayout.h2Size, marginBottom: nextStepsLayout.h2Margin }] }, "Success Metrics"),
        ...nextStepsLayout.metrics.map((metric, index) =>
          React.createElement(
            Text,
            {
              key: `metric-${index}`,
              style: [styles.body, { fontSize: nextStepsLayout.bodySize, lineHeight: FONT.bodyLine }],
            },
            `• ${metric}`
          )
        )
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
          React.createElement(Text, { style: styles.bodyLight }, freelancerName),
          React.createElement(
            View,
            { style: { marginTop: 20 } },
            React.createElement(View, { style: styles.signatureLine }),
            React.createElement(Text, { style: styles.bodyLight }, "Date")
          )
        )
      ),
      React.createElement(GradientBar),
      validityNote
        ? React.createElement(
            Text,
            { style: [styles.body, { marginTop: 30, textAlign: 'center', fontSize: 12 }] },
            validityNote
          )
        : null,
      React.createElement(Text, { style: styles.pageNumber }, "8")
    )
  );
};

module.exports = GlassmorphicProposal;
