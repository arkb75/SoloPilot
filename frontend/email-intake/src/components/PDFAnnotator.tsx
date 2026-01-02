import { useCallback, useMemo, useRef, useState } from 'react';
import html2canvas from 'html2canvas';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import { PdfAnnotation } from '../types';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

interface PDFAnnotatorProps {
  fileUrl: string;
  onCancel: () => void;
  onSubmitStart?: () => boolean | void;
  onSubmitVision: (payload: { pages: { pageIndex: number; imageBase64: string }[]; annotations: PdfAnnotation[]; prompt: string }) => Promise<void> | void;
}

const HIGHLIGHT_COLOR = '#FFEB3B';

const applyAlpha = (color: string, alpha: number): string => {
  if (!color.startsWith('#')) return color;
  const raw = color.slice(1);
  const hex = raw.length === 3 ? raw.split('').map((c) => c + c).join('') : raw;
  if (hex.length !== 6) return color;
  const r = Number.parseInt(hex.slice(0, 2), 16);
  const g = Number.parseInt(hex.slice(2, 4), 16);
  const b = Number.parseInt(hex.slice(4, 6), 16);
  const safeAlpha = Math.min(1, Math.max(0, alpha));
  return `rgba(${r}, ${g}, ${b}, ${safeAlpha})`;
};

type DisplayAnnotation = PdfAnnotation & { _idx: number; _displayIndex: number };

const buildDisplayAnnotations = (annotations: PdfAnnotation[], pageIndex: number): DisplayAnnotation[] => {
  const filtered = annotations
    .map((a, i) => ({ ...a, _idx: i }))
    .filter((a) => a.pageIndex === pageIndex);
  return filtered.map((a, i) => ({ ...a, _displayIndex: i + 1 }));
};

const PDFAnnotator: React.FC<PDFAnnotatorProps> = ({ fileUrl, onCancel, onSubmitStart, onSubmitVision }) => {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [annotations, setAnnotations] = useState<PdfAnnotation[]>([]);
  const [prompt, setPrompt] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [startPt, setStartPt] = useState<{ x: number; y: number } | null>(null);
  const [currentRect, setCurrentRect] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  const pageContainerRef = useRef<HTMLDivElement | null>(null);
  const pageNumberRef = useRef<number>(pageNumber);
  const lastRenderedPageRef = useRef<number | null>(null);
  const renderTargetRef = useRef<number | null>(null);
  const renderResolveRef = useRef<(() => void) | null>(null);

  pageNumberRef.current = pageNumber;

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setPageNumber(1);
  }, []);

  const handlePageRenderSuccess = useCallback(() => {
    lastRenderedPageRef.current = pageNumberRef.current;
    if (renderTargetRef.current === pageNumberRef.current) {
      renderResolveRef.current?.();
      renderResolveRef.current = null;
      renderTargetRef.current = null;
    }
  }, []);

  const getZone = (ny: number): 'title' | 'subtitle' | 'body' => {
    if (ny < 0.25) return 'title';
    if (ny < 0.35) return 'subtitle';
    return 'body';
  };

  const getTextInRect = (rect: DOMRect): { selectedText?: string; surroundingText?: string } => {
    if (!pageContainerRef.current) return {};
    const container = pageContainerRef.current;
    const textLayer = container.querySelector('.react-pdf__Page__textContent') as HTMLElement | null;
    if (!textLayer) return {};
    const spans = Array.from(textLayer.querySelectorAll('span')) as HTMLSpanElement[];
    const lines: string[] = [];
    spans.forEach((sp) => {
      const b = sp.getBoundingClientRect();
      const intersects = !(b.right < rect.left || b.left > rect.right || b.bottom < rect.top || b.top > rect.bottom);
      if (intersects) {
        const t = sp.textContent || '';
        if (t.trim()) lines.push(t);
      }
    });
    const selectedText = lines.join(' ').replace(/\s+/g, ' ').trim() || undefined;

    const ctxRect = new DOMRect(
      rect.left - 24,
      rect.top - 24,
      rect.width + 48,
      rect.height + 48
    );
    const ctxLines: string[] = [];
    spans.forEach((sp) => {
      const b = sp.getBoundingClientRect();
      const intersects = !(b.right < ctxRect.left || b.left > ctxRect.right || b.bottom < ctxRect.top || b.top > ctxRect.bottom);
      if (intersects) {
        const t = sp.textContent || '';
        if (t.trim()) ctxLines.push(t);
      }
    });
    const surroundingText = ctxLines.join(' ').replace(/\s+/g, ' ').trim() || undefined;
    return { selectedText, surroundingText };
  };

  const getImageCropForRect = (norm: { x: number; y: number; width: number; height: number }): string | undefined => {
    if (!pageContainerRef.current) return undefined;
    const canvas = pageContainerRef.current.querySelector('canvas') as HTMLCanvasElement | null;
    if (!canvas) return undefined;
    const cw = canvas.width;
    const ch = canvas.height;
    if (!cw || !ch) return undefined;
    const sx = Math.max(0, Math.floor(norm.x * cw));
    const sy = Math.max(0, Math.floor(norm.y * ch));
    const sw = Math.max(1, Math.floor(norm.width * cw));
    const sh = Math.max(1, Math.floor(norm.height * ch));
    const off = document.createElement('canvas');
    off.width = sw;
    off.height = sh;
    const ctx = off.getContext('2d');
    if (!ctx) return undefined;
    ctx.drawImage(canvas, sx, sy, sw, sh, 0, 0, sw, sh);
    try {
      const dataUrl = off.toDataURL('image/png');
      const base64 = dataUrl.split(',')[1] || dataUrl;
      return base64;
    } catch (e) {
      return undefined;
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (!pageContainerRef.current) return;
    const rect = pageContainerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setIsDrawing(true);
    setStartPt({ x, y });
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!isDrawing || !startPt || !pageContainerRef.current) return;
    const rect = pageContainerRef.current.getBoundingClientRect();
    const endX = e.clientX - rect.left;
    const endY = e.clientY - rect.top;

    const left = Math.min(startPt.x, endX);
    const top = Math.min(startPt.y, endY);
    const width = Math.abs(endX - startPt.x);
    const height = Math.abs(endY - startPt.y);

    const nx = left / rect.width;
    const ny = top / rect.height;
    const nwidth = width / rect.width;
    const nheight = height / rect.height;

    if (nwidth > 0.002 && nheight > 0.002) {
      const absRect = new DOMRect(rect.left + left, rect.top + top, width, height);
      const { selectedText, surroundingText } = getTextInRect(absRect);
      const zone = getZone(ny);
      const imageData = getImageCropForRect({ x: nx, y: ny, width: nwidth, height: nheight });
      setAnnotations((prev) => [
        ...prev,
        {
          pageIndex: pageNumber - 1,
          x: nx,
          y: ny,
          width: nwidth,
          height: nheight,
          type: 'highlight',
          color: HIGHLIGHT_COLOR,
          opacity: 0.55,
          selectedText,
          surroundingText,
          zone,
          imageData,
        },
      ]);
    }

    setIsDrawing(false);
    setStartPt(null);
    setCurrentRect(null);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDrawing || !startPt || !pageContainerRef.current) return;
    const rect = pageContainerRef.current.getBoundingClientRect();
    const endX = e.clientX - rect.left;
    const endY = e.clientY - rect.top;
    const left = Math.min(startPt.x, endX);
    const top = Math.min(startPt.y, endY);
    const width = Math.abs(endX - startPt.x);
    const height = Math.abs(endY - startPt.y);
    setCurrentRect({ x: left, y: top, width, height });
  };

  const pageAnnotations = useMemo(() => {
    return buildDisplayAnnotations(annotations, pageNumber - 1);
  }, [annotations, pageNumber]);

  const waitForPageRender = (targetPage: number) => {
    if (lastRenderedPageRef.current === targetPage) {
      return Promise.resolve();
    }
    return new Promise<void>((resolve) => {
      renderTargetRef.current = targetPage;
      renderResolveRef.current = resolve;
    });
  };

  const waitForPaint = () => new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve());
  });

  const buildPageComposite = async (keyAnnotations: DisplayAnnotation[]): Promise<string | undefined> => {
    if (!pageContainerRef.current) return undefined;
    try {
      const container = pageContainerRef.current;
      const composite = await html2canvas(container, {
        backgroundColor: '#ffffff',
        scale: 2,
        useCORS: true,
      });
      const scale = composite.width / container.clientWidth;
      const keyWidth = Math.round(260 * scale);
      const margin = Math.round(12 * scale);
      const titleSize = Math.round(14 * scale);
      const textSize = Math.round(12 * scale);
      const lineHeight = Math.round(16 * scale);

      const out = document.createElement('canvas');
      out.width = composite.width + keyWidth;
      out.height = composite.height;
      const ctx = out.getContext('2d');
      if (!ctx) return undefined;

      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, out.width, out.height);
      ctx.drawImage(composite, 0, 0);

      ctx.strokeStyle = '#e5e7eb';
      ctx.lineWidth = Math.max(1, Math.round(1 * scale));
      ctx.beginPath();
      ctx.moveTo(composite.width + 0.5, margin);
      ctx.lineTo(composite.width + 0.5, out.height - margin);
      ctx.stroke();

      const keyX = composite.width + margin;
      let cursorY = margin + titleSize;
      ctx.fillStyle = '#111827';
      ctx.font = `600 ${titleSize}px sans-serif`;
      ctx.fillText('Annotations', keyX, cursorY);
      cursorY += margin + lineHeight;

      const wrapText = (text: string, x: number, y: number, maxWidth: number, height: number) => {
        const words = text.split(/\s+/);
        let line = '';
        let lineY = y;
        for (let i = 0; i < words.length; i += 1) {
          const word = words[i];
          const testLine = line ? `${line} ${word}` : word;
          const metrics = ctx.measureText(testLine);
          if (metrics.width > maxWidth && line) {
            ctx.fillText(line, x, lineY);
            line = word;
            lineY += height;
          } else {
            line = testLine;
          }
        }
        if (line) {
          ctx.fillText(line, x, lineY);
          lineY += height;
        }
        return lineY;
      };

      ctx.font = `${textSize}px sans-serif`;
      const badgeRadius = Math.round(10 * scale);
      const badgeDiameter = badgeRadius * 2;
      const textX = keyX + badgeDiameter + Math.round(6 * scale);
      const maxTextWidth = keyWidth - (textX - composite.width) - margin;

      keyAnnotations.forEach((a) => {
        if (cursorY + lineHeight > out.height - margin) {
          return;
        }
        const label = (a.comment || '').trim() || '(no comment)';

        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(keyX + badgeRadius, cursorY - badgeRadius + 2, badgeRadius, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#111827';
        ctx.lineWidth = Math.max(2, Math.round(1.5 * scale));
        ctx.stroke();

        ctx.fillStyle = '#111827';
        ctx.font = `700 ${Math.round(12 * scale)}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(String(a._displayIndex), keyX + badgeRadius, cursorY - badgeRadius + 2);

        ctx.fillStyle = '#111827';
        ctx.font = `${textSize}px sans-serif`;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'alphabetic';
        cursorY = wrapText(label, textX, cursorY, maxTextWidth, lineHeight);
        cursorY += Math.round(6 * scale);
      });

      const dataUrl = out.toDataURL('image/png');
      return (dataUrl.split(',')[1] || dataUrl);
    } catch (e) {
      return undefined;
    }
  };

  const buildCompositesForPages = async () => {
    const annotatedPages = Array.from(new Set(annotations.map((a) => a.pageIndex))).sort((a, b) => a - b);
    const targetPages = annotatedPages.length > 0 ? annotatedPages : [pageNumberRef.current - 1];
    const originalPage = pageNumberRef.current;
    const pages: { pageIndex: number; imageBase64: string }[] = [];

    for (const pageIndex of targetPages) {
      const targetPage = pageIndex + 1;
      if (pageNumberRef.current !== targetPage) {
        setPageNumber(targetPage);
      }
      await waitForPageRender(targetPage);
      await waitForPaint();
      const keyAnnotations = buildDisplayAnnotations(annotations, pageIndex);
      const imageBase64 = await buildPageComposite(keyAnnotations);
      if (imageBase64) {
        pages.push({ pageIndex, imageBase64 });
      }
    }

    if (pageNumberRef.current !== originalPage) {
      setPageNumber(originalPage);
    }

    return pages;
  };

  const submit = async () => {
    setIsSubmitting(true);
    const shouldProceed = onSubmitStart?.();
    if (shouldProceed === false) {
      setIsSubmitting(false);
      return;
    }
    const pages = await buildCompositesForPages();
    await onSubmitVision({ pages, annotations, prompt });
  };

  return (
    <div className={`fixed inset-0 z-50 bg-black bg-opacity-50 flex items-center justify-center p-4 ${isSubmitting ? 'opacity-0 pointer-events-none' : ''}`}>
      <div className="bg-white w-full max-w-6xl h-[90vh] rounded-lg shadow-lg flex overflow-hidden">
        <div className="flex-1 flex flex-col border-r">
          <div className="p-3 flex items-center gap-2 border-b">
            <span className="text-sm font-medium">PDF Editor</span>
          </div>
          <div className="flex items-center justify-between p-2 text-sm">
            <div className="flex items-center gap-2">
              <button onClick={() => setPageNumber(p => Math.max(1, p - 1))} className="px-2 py-1 border rounded" disabled={pageNumber <= 1}>Prev</button>
              <button onClick={() => setPageNumber(p => Math.min(numPages, p + 1))} className="px-2 py-1 border rounded" disabled={pageNumber >= numPages}>Next</button>
              <span>Page {pageNumber} / {numPages || '--'}</span>
            </div>
            <button onClick={() => setAnnotations([])} className="px-2 py-1 border rounded">Clear</button>
          </div>
          <div className="flex-1 overflow-auto flex items-center justify-center bg-gray-50">
            <div
              ref={pageContainerRef}
              onMouseDown={handleMouseDown}
              onMouseUp={handleMouseUp}
              onMouseMove={handleMouseMove}
              onMouseLeave={() => { if (isDrawing) { setIsDrawing(false); setStartPt(null); setCurrentRect(null); } }}
              className="relative select-none"
              style={{ cursor: 'crosshair', userSelect: 'none' }}
            >
              <Document file={fileUrl} onLoadSuccess={onDocumentLoadSuccess} loading={<div className="p-4 text-gray-500">Loading PDF…</div>}>
                <Page pageNumber={pageNumber} renderAnnotationLayer={false} renderTextLayer={false} width={720} onRenderSuccess={handlePageRenderSuccess} />
              </Document>
              {/* Selection preview while dragging */}
              {currentRect && (
                <div
                  style={{
                    position: 'absolute',
                    left: `${currentRect.x}px`,
                    top: `${currentRect.y}px`,
                    width: `${currentRect.width}px`,
                    height: `${currentRect.height}px`,
                    backgroundColor: 'rgba(255, 235, 59, 0.4)',
                    border: '2px dashed rgba(245, 158, 11, 0.9)',
                    pointerEvents: 'none',
                  }}
                />
              )}
              {pageContainerRef.current && pageAnnotations.map((a) => {
                const rect = pageContainerRef.current!.getBoundingClientRect();
                const badgeSize = 18;
                const badgeOffset = 6;
                const highlightLeft = a.x * rect.width;
                const highlightTop = a.y * rect.height;
                const highlightWidth = a.width * rect.width;
                const highlightHeight = a.height * rect.height;
                const fillOpacity = Math.max(a.opacity ?? 0.6, 0.45);
                const style: React.CSSProperties = {
                  position: 'absolute',
                  left: `${highlightLeft}px`,
                  top: `${highlightTop}px`,
                  width: `${highlightWidth}px`,
                  height: `${highlightHeight}px`,
                  backgroundColor: applyAlpha(a.color || HIGHLIGHT_COLOR, fillOpacity),
                  opacity: 1,
                  border: '2px solid rgba(245, 158, 11, 0.9)',
                  boxShadow: '0 0 0 1px rgba(0, 0, 0, 0.08)',
                  pointerEvents: 'none',
                };
                const candidates = [
                  { left: highlightLeft - (badgeSize / 2), top: highlightTop - badgeSize - badgeOffset },
                  { left: highlightLeft + highlightWidth + badgeOffset, top: highlightTop - (badgeSize / 2) },
                  { left: highlightLeft - badgeSize - badgeOffset, top: highlightTop - (badgeSize / 2) },
                  { left: highlightLeft - (badgeSize / 2), top: highlightTop + highlightHeight + badgeOffset },
                ];
                const within = (left: number, top: number) => (
                  left >= 0 && top >= 0 && left + badgeSize <= rect.width && top + badgeSize <= rect.height
                );
                const fallbackLeft = Math.min(Math.max(0, highlightLeft), rect.width - badgeSize);
                const fallbackTop = Math.min(Math.max(0, highlightTop), rect.height - badgeSize);
                const candidate = candidates.find((pos) => within(pos.left, pos.top));
                const badgeLeft = candidate ? candidate.left : fallbackLeft;
                const badgeTop = candidate ? candidate.top : fallbackTop;
                const badgeStyle: React.CSSProperties = {
                  position: 'absolute',
                  left: `${badgeLeft}px`,
                  top: `${badgeTop}px`,
                  width: `${badgeSize}px`,
                  height: `${badgeSize}px`,
                  backgroundColor: '#ffffff',
                  color: '#111827',
                  fontSize: '11px',
                  fontWeight: 700,
                  lineHeight: 1,
                  borderRadius: '9999px',
                  border: '2px solid #111827',
                  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.35)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  pointerEvents: 'none',
                };
                return (
                  <div key={a._idx}>
                    <div style={style} title={a.comment || ''} />
                    <div style={badgeStyle}>{a._displayIndex}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        <div className="w-96 flex flex-col">
          <div className="p-3 border-b">
            <div className="text-sm font-medium">Annotations</div>
          </div>
          <div className="flex-1 overflow-auto p-3 space-y-3">
            {annotations.length === 0 && <div className="text-sm text-gray-500">Draw on the page to add highlights or notes.</div>}
            {annotations.map((a, idx) => (
              <div key={idx} className="border rounded p-2">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-gray-600">{a.type} • Page {a.pageIndex + 1} • {a.zone || 'body'}</span>
                  <button className="text-red-600" onClick={() => setAnnotations(prev => prev.filter((_, i) => i !== idx))}>Remove</button>
                </div>
                <input type="text" value={a.comment || ''} onChange={(e) => setAnnotations(prev => prev.map((p, i) => i === idx ? { ...p, comment: e.target.value } : p))} placeholder="Add a comment (optional)" className="w-full border rounded px-2 py-1 text-sm" />
                {a.selectedText && <div className="mt-1 text-[11px] text-gray-500">Sel: {a.selectedText.slice(0, 80)}{a.selectedText.length > 80 ? '…' : ''}</div>}
              </div>
            ))}
          </div>
          <div className="p-3 border-t space-y-2">
            <label className="text-sm font-medium">Edit Prompt (optional)</label>
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Describe the changes; this will be sent to the vision model." className="w-full border rounded px-2 py-1 text-sm h-24" />
            <div className="flex justify-end gap-2">
              <button onClick={onCancel} className="px-3 py-2 border rounded">Cancel</button>
              <button onClick={submit} className="px-3 py-2 bg-blue-600 text-white rounded">Save Edits</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PDFAnnotator;
