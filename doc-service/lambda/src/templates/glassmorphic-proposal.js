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

const getHeaderHeight = () => (FONT.h1 * 1.2) + FONT.h1Margin;

const fitExecutiveSummaryLayout = (paragraphs) => {
  const safeParagraphs = Array.isArray(paragraphs) ? paragraphs.filter(Boolean) : [];
  const headerHeight = getHeaderHeight();
  const availableHeight = CONTENT_HEIGHT - headerHeight - SECTION_BOTTOM_BUFFER;

  const measureParagraphs = (scale, content) => {
    const panelPadding = PANEL.padding * scale;
    const bodySize = FONT.body * scale;
    const paragraphGap = 15 * scale;
    const textWidth = CONTENT_WIDTH - (panelPadding * 2);
    const charsPerLine = estimateCharsPerLine(textWidth, bodySize);
    const paragraphHeights = content.map((paragraph) => (
      estimateLineCount(paragraph, charsPerLine) * bodySize * FONT.bodyLine
    ));
    const totalHeight = paragraphHeights.reduce((sum, height, idx) => (
      sum + height + (idx > 0 ? paragraphGap : 0)
    ), 0);
    return {
      panelPadding,
      bodySize,
      paragraphGap,
      charsPerLine,
      paragraphHeights,
      totalHeight: (panelPadding * 2) + totalHeight,
      scale,
    };
  };

  for (const scale of SCALE_STEPS) {
    const metrics = measureParagraphs(scale, safeParagraphs);
    if (metrics.totalHeight <= availableHeight) {
      return { ...metrics, pages: [safeParagraphs] };
    }
  }

  const scaleForPage = SCALE_STEPS.find((scale) => {
    const metrics = measureParagraphs(scale, safeParagraphs);
    const maxParagraph = Math.max(...metrics.paragraphHeights, 0);
    return (metrics.panelPadding * 2) + maxParagraph <= availableHeight;
  }) || SCALE_STEPS[SCALE_STEPS.length - 1];

  const metrics = measureParagraphs(scaleForPage, safeParagraphs);
  const pages = [];
  let current = [];
  let currentHeight = 0;
  metrics.paragraphHeights.forEach((height, idx) => {
    const nextHeight = current.length === 0
      ? (metrics.panelPadding * 2) + height
      : currentHeight + metrics.paragraphGap + height;
    if (current.length > 0 && nextHeight > availableHeight) {
      pages.push(current);
      current = [safeParagraphs[idx]];
      currentHeight = (metrics.panelPadding * 2) + height;
    } else {
      current.push(safeParagraphs[idx]);
      currentHeight = nextHeight;
    }
  });
  if (current.length) pages.push(current);
  return { ...metrics, pages };
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

  const measureCards = (scale, content) => {
    const cardPadding = SCOPE_CARD.padding * scale;
    const cardGap = SCOPE_CARD.gap * scale;
    const titleSize = FONT.scopeTitle * scale;
    const titleMargin = FONT.scopeTitleMargin * scale;
    const descSize = FONT.scopeDesc * scale;
    const textWidth = CONTENT_WIDTH - (cardPadding * 2) - (SCOPE_CARD.indent * scale);
    const charsPerLine = estimateCharsPerLine(textWidth, descSize);
    const descLineCounts = content.map((item) => estimateLineCount(item.description, charsPerLine));
    const titleHeight = titleSize * 1.2;
    const cardHeights = descLineCounts.map((lines) => (
      (cardPadding * 2) + titleHeight + titleMargin + (lines * descSize * FONT.scopeDescLine)
    ));
    const totalHeight = cardHeights.reduce((sum, height, idx) => (
      sum + height + (idx < cardHeights.length - 1 ? cardGap : 0)
    ), 0);
    return {
      cardPadding,
      cardGap,
      titleSize,
      titleMargin,
      descSize,
      charsPerLine,
      descLineCounts,
      cardHeights,
      totalHeight,
      scale,
      titleHeight,
    };
  };

  for (const scale of SCALE_STEPS) {
    const metrics = measureCards(scale, safeItems);
    if (metrics.totalHeight <= availableHeight) {
      return { ...metrics, pages: [safeItems] };
    }
  }

  const scaleForPage = SCALE_STEPS.find((scale) => {
    const metrics = measureCards(scale, safeItems);
    const maxCard = Math.max(...metrics.cardHeights, 0);
    return maxCard <= availableHeight;
  }) || SCALE_STEPS[SCALE_STEPS.length - 1];

  const metrics = measureCards(scaleForPage, safeItems);
  const pages = [];
  let current = [];
  let currentHeight = 0;
  metrics.cardHeights.forEach((height, idx) => {
    const nextHeight = current.length === 0
      ? height
      : currentHeight + metrics.cardGap + height;
    if (current.length > 0 && nextHeight > availableHeight) {
      pages.push(current);
      current = [safeItems[idx]];
      currentHeight = height;
    } else {
      current.push(safeItems[idx]);
      currentHeight = nextHeight;
    }
  });
  if (current.length) pages.push(current);
  return { ...metrics, pages };
};

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
      return { ...metrics, pages: [safeRows] };
    }
  }

  const scaleForPage = SCALE_STEPS.find((scale) => {
    const metrics = measure(scale, safeRows.length);
    return metrics.totalRowHeight + metrics.totalMargin <= availableHeight;
  }) || SCALE_STEPS[SCALE_STEPS.length - 1];

  const metrics = measure(scaleForPage, safeRows.length);
  const availableForRows = availableHeight - metrics.totalRowHeight - metrics.totalMargin;
  const slotHeight = metrics.rowHeight + metrics.rowGap;
  const maxRows = Math.max(1, Math.floor((availableForRows + metrics.rowGap) / slotHeight));
  const pages = [];
  for (let i = 0; i < safeRows.length; i += maxRows) {
    pages.push(safeRows.slice(i, i + maxRows));
  }
  if (pages.length === 0) pages.push([]);
  return { ...metrics, pages };
};

const fitNextStepsLayout = (steps, metricsList) => {
  const safeSteps = Array.isArray(steps) ? steps.filter(Boolean) : [];
  const safeMetrics = Array.isArray(metricsList) ? metricsList.filter(Boolean) : [];
  const headerHeight = getHeaderHeight();
  const availableHeight = CONTENT_HEIGHT - headerHeight - SECTION_BOTTOM_BUFFER;

  const buildItems = (items, prefix) => items.map((item, idx) => ({
    text: `${prefix}${idx + 1}. ${item}`,
    raw: item,
    index: idx,
  }));

  const stepItems = buildItems(safeSteps, '');
  const metricItems = safeMetrics.map((item, idx) => ({
    text: `• ${item}`,
    raw: item,
    index: idx,
  }));

  const measurePanels = (scale, stepEntries, metricEntries) => {
    const panelPadding = PANEL.padding * scale;
    const panelGap = NEXT_STEPS.panelGap * scale;
    const h2Size = FONT.h2 * scale;
    const h2Margin = FONT.h2Margin * scale;
    const bodySize = FONT.body * scale;
    const textWidth = CONTENT_WIDTH - (panelPadding * 2);
    const charsPerLine = estimateCharsPerLine(textWidth, bodySize);
    const lineHeight = bodySize * FONT.bodyLine;
    const panelFixed = (panelPadding * 2) + (h2Size * 1.2) + h2Margin;
    const stepHeight = panelFixed + stepEntries.reduce((sum, entry) => (
      sum + (estimateLineCount(entry.text, charsPerLine) * lineHeight)
    ), 0);
    const metricHeight = panelFixed + metricEntries.reduce((sum, entry) => (
      sum + (estimateLineCount(entry.text, charsPerLine) * lineHeight)
    ), 0);
    return {
      panelPadding,
      panelGap,
      h2Size,
      h2Margin,
      bodySize,
      charsPerLine,
      lineHeight,
      panelFixed,
      stepHeight,
      metricHeight,
      totalHeight: stepHeight + metricHeight + panelGap,
      scale,
    };
  };

  for (const scale of SCALE_STEPS) {
    const metrics = measurePanels(scale, stepItems, metricItems);
    if (metrics.totalHeight <= availableHeight) {
      return {
        ...metrics,
        pages: [
          {
            panels: [
              { title: 'Immediate Actions', items: stepItems },
              { title: 'Success Metrics', items: metricItems },
            ],
          },
        ],
      };
    }
  }

  const scaleForPage = SCALE_STEPS.find((scale) => {
    const metrics = measurePanels(scale, stepItems, metricItems);
    const maxItemLines = Math.max(
      ...stepItems.map((item) => estimateLineCount(item.text, metrics.charsPerLine)),
      ...metricItems.map((item) => estimateLineCount(item.text, metrics.charsPerLine)),
      1
    );
    const maxItemHeight = metrics.panelFixed + (maxItemLines * metrics.lineHeight);
    return maxItemHeight <= availableHeight;
  }) || SCALE_STEPS[SCALE_STEPS.length - 1];

  const metrics = measurePanels(scaleForPage, stepItems, metricItems);
  const panelEntries = [];

  const splitItems = (items, title) => {
    let current = [];
    let currentHeight = metrics.panelFixed;
    items.forEach((entry) => {
      const itemHeight = estimateLineCount(entry.text, metrics.charsPerLine) * metrics.lineHeight;
      const nextHeight = currentHeight + itemHeight;
      if (current.length > 0 && nextHeight > availableHeight) {
        panelEntries.push({ title, items: current });
        current = [entry];
        currentHeight = metrics.panelFixed + itemHeight;
      } else {
        current.push(entry);
        currentHeight = nextHeight;
      }
    });
    if (current.length) {
      panelEntries.push({ title, items: current });
    }
  };

  splitItems(stepItems, 'Immediate Actions');
  splitItems(metricItems, 'Success Metrics');

  const pages = [];
  let currentPage = [];
  let currentHeight = 0;
  panelEntries.forEach((panel) => {
    const panelHeight = metrics.panelFixed + panel.items.reduce((sum, entry) => (
      sum + (estimateLineCount(entry.text, metrics.charsPerLine) * metrics.lineHeight)
    ), 0);
    const nextHeight = currentPage.length === 0
      ? panelHeight
      : currentHeight + metrics.panelGap + panelHeight;
    if (currentPage.length > 0 && nextHeight > availableHeight) {
      pages.push({ panels: currentPage });
      currentPage = [panel];
      currentHeight = panelHeight;
    } else {
      currentPage.push(panel);
      currentHeight = nextHeight;
    }
  });
  if (currentPage.length) pages.push({ panels: currentPage });

  return { ...metrics, pages };
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

  const pageNumberText = (value) => React.createElement(Text, { style: styles.pageNumber }, String(value));

  const pages = [];

  pages.push(
    React.createElement(
      Page,
      { size: "A4", style: [styles.page, styles.coverPage] },
      React.createElement(View, { style: styles.coverBackground }),
      React.createElement(Text, { style: styles.coverTitle }, projectTitle),
      React.createElement(Text, { style: styles.coverSubtitle }, `Project Proposal for ${clientName}`),
      React.createElement(Text, { style: [styles.coverSubtitle, { marginTop: 40, fontSize: 16 }] }, proposalDate)
    )
  );

  let pageNumber = 2;

  execSummaryLayout.pages.forEach((paragraphs, pageIndex) => {
    pages.push(
      React.createElement(
        Page,
        { key: `exec-${pageIndex}`, size: "A4", style: [styles.page, styles.contentPage] },
        React.createElement(Text, { style: styles.h1 }, "Executive Summary"),
        React.createElement(
          View,
          { style: [styles.glassPanel, { padding: execSummaryLayout.panelPadding }], wrap: false },
          ...paragraphs.map((paragraph, index) =>
            React.createElement(
              Text,
              {
                key: `summary-${pageIndex}-${index}`,
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
        pageNumberText(pageNumber)
      )
    );
    pageNumber += 1;
  });

  scopeLayout.pages.forEach((itemsPage, pageIndex) => {
    pages.push(
      React.createElement(
        Page,
        { key: `scope-${pageIndex}`, size: "A4", style: [styles.page, styles.contentPage] },
        React.createElement(Text, { style: styles.h1 }, "Project Scope"),
        React.createElement(
          View,
          { style: styles.scopeGrid },
          ...itemsPage.map((item, index) =>
            React.createElement(
              View,
              {
                key: `scope-card-${pageIndex}-${index}`,
                style: [
                  styles.scopeCard,
                  {
                    padding: scopeLayout.cardPadding,
                    borderRadius: SCOPE_CARD.radius * scopeLayout.scale,
                    marginLeft: index * SCOPE_CARD.indent * scopeLayout.scale,
                    marginBottom: index < itemsPage.length - 1 ? scopeLayout.cardGap : 0,
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
        pageNumberText(pageNumber)
      )
    );
    pageNumber += 1;
  });

  pages.push(
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
      pageNumberText(pageNumber)
    )
  );
  pageNumber += 1;

  pricingLayout.pages.forEach((rowsPage, pageIndex) => {
    const isLast = pageIndex === pricingLayout.pages.length - 1;
    pages.push(
      React.createElement(
        Page,
        { key: `pricing-${pageIndex}`, size: "A4", style: [styles.page, styles.contentPage] },
        React.createElement(Text, { style: styles.h1 }, "Cost Breakdown"),
        React.createElement(
          View,
          { style: styles.pricingTable },
          ...rowsPage.map((item, index) =>
            React.createElement(
              View,
              {
                key: `pricing-row-${pageIndex}-${index}`,
                style: [
                  styles.pricingRow,
                  {
                    padding: pricingLayout.rowPadding,
                    borderRadius: PRICING_ROW.radius * pricingLayout.scale,
                    marginBottom: index < rowsPage.length - 1 ? pricingLayout.rowGap : 0,
                  },
                ],
                wrap: false,
              },
              React.createElement(Text, { style: [styles.pricingItem, { fontSize: pricingLayout.itemSize }] }, item.item),
              React.createElement(Text, { style: [styles.pricingAmount, { fontSize: pricingLayout.amountSize }] }, item.amount)
            )
          ),
          isLast
            ? React.createElement(
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
                React.createElement(Text, { style: [styles.pricingAmount, { fontSize: pricingLayout.totalSize }] }, calculateTotal(pricing))
              )
            : null
        ),
        pageNumberText(pageNumber)
      )
    );
    pageNumber += 1;
  });

  pages.push(
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
      pageNumberText(pageNumber)
    )
  );
  pageNumber += 1;

  nextStepsLayout.pages.forEach((pageData, pageIndex) => {
    pages.push(
      React.createElement(
        Page,
        { key: `next-${pageIndex}`, size: "A4", style: [styles.page, styles.contentPage] },
        React.createElement(Text, { style: styles.h1 }, "Next Steps"),
        ...pageData.panels.map((panel, panelIndex) =>
          React.createElement(
            View,
            {
              key: `panel-${pageIndex}-${panelIndex}`,
              style: [
                styles.glassPanel,
                {
                  marginTop: panelIndex === 0 ? 0 : nextStepsLayout.panelGap,
                  padding: nextStepsLayout.panelPadding,
                },
              ],
              wrap: false,
            },
            React.createElement(
              Text,
              { style: [styles.h2, { fontSize: nextStepsLayout.h2Size, marginBottom: nextStepsLayout.h2Margin }] },
              panel.title
            ),
            ...panel.items.map((entry, idx) =>
              React.createElement(
                Text,
                {
                  key: `panel-item-${pageIndex}-${panelIndex}-${idx}`,
                  style: [styles.body, { fontSize: nextStepsLayout.bodySize, lineHeight: FONT.bodyLine }],
                },
                entry.text
              )
            )
          )
        ),
        pageNumberText(pageNumber)
      )
    );
    pageNumber += 1;
  });

  pages.push(
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
      pageNumberText(pageNumber)
    )
  );

  return React.createElement(Document, {}, ...pages);
};

module.exports = GlassmorphicProposal;
