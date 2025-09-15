import { useCallback, useMemo, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import { PdfAnnotation } from '../types';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

interface PDFAnnotatorProps {
  fileUrl: string;
  onCancel: () => void;
  onSubmitVision: (payload: { pageImageBase64: string; annotations: PdfAnnotation[]; prompt: string }) => Promise<void> | void;
}

const toolColors: Record<string, string> = {
  highlight: '#FFEB3B',
  note: '#4CAF50',
};

const PDFAnnotator: React.FC<PDFAnnotatorProps> = ({ fileUrl, onCancel, onSubmitVision }) => {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [annotations, setAnnotations] = useState<PdfAnnotation[]>([]);
  const [prompt, setPrompt] = useState<string>('');
  const [activeTool, setActiveTool] = useState<'highlight' | 'note'>('highlight');
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [startPt, setStartPt] = useState<{ x: number; y: number } | null>(null);
  const pageContainerRef = useRef<HTMLDivElement | null>(null);

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setPageNumber(1);
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
          type: activeTool,
          color: toolColors[activeTool],
          opacity: activeTool === 'highlight' ? 0.3 : 0.8,
          selectedText,
          surroundingText,
          zone,
          imageData,
        },
      ]);
    }

    setIsDrawing(false);
    setStartPt(null);
  };

  const handleMouseMove = (_e: React.MouseEvent) => {
    // Optional: implement visual preview
  };

  const pageAnnotations = useMemo(() => annotations.map((a, i) => ({ ...a, _idx: i })).filter(a => a.pageIndex === pageNumber - 1), [annotations, pageNumber]);

  const buildPageComposite = (): string | undefined => {
    if (!pageContainerRef.current) return undefined;
    const canvas = pageContainerRef.current.querySelector('canvas') as HTMLCanvasElement | null;
    if (!canvas) return undefined;
    const cw = canvas.width;
    const ch = canvas.height;
    const off = document.createElement('canvas');
    off.width = cw;
    off.height = ch;
    const ctx = off.getContext('2d');
    if (!ctx) return undefined;
    ctx.drawImage(canvas, 0, 0);
    // draw overlays for current page annotations
    const anns = annotations.filter(a => a.pageIndex === pageNumber - 1);
    anns.forEach(a => {
      ctx.save();
      const color = a.color || (a.type === 'highlight' ? '#FFEB3B' : '#4CAF50');
      const x = a.x * cw;
      const y = a.y * ch;
      const w = a.width * cw;
      const h = a.height * ch;
      if (a.type === 'highlight') {
        ctx.fillStyle = color;
        ctx.globalAlpha = a.opacity ?? 0.3;
        ctx.fillRect(x, y, w, h);
      } else {
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.strokeRect(x, y, w, h);
      }
      ctx.restore();
    });
    try {
      const dataUrl = off.toDataURL('image/png');
      return (dataUrl.split(',')[1] || dataUrl);
    } catch (e) {
      return undefined;
    }
  };

  const submit = async () => {
    const pageImageBase64 = buildPageComposite();
    await onSubmitVision({ pageImageBase64: pageImageBase64 || '', annotations, prompt });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black bg-opacity-50 flex items-center justify-center p-4">
      <div className="bg-white w-full max-w-6xl h-[90vh] rounded-lg shadow-lg flex overflow-hidden">
        <div className="flex-1 flex flex-col border-r">
          <div className="p-3 flex items-center gap-2 border-b">
            <span className="text-sm font-medium">PDF Editor (pending)</span>
            <div className="ml-auto flex items-center gap-2">
              <button onClick={() => setActiveTool('highlight')} className={`px-2 py-1 text-sm rounded ${activeTool === 'highlight' ? 'bg-yellow-200' : 'bg-gray-100'}`}>Highlight</button>
              <button onClick={() => setActiveTool('note')} className={`px-2 py-1 text-sm rounded ${activeTool === 'note' ? 'bg-green-200' : 'bg-gray-100'}`}>Note</button>
            </div>
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
            <div ref={pageContainerRef} onMouseDown={handleMouseDown} onMouseUp={handleMouseUp} onMouseMove={handleMouseMove} className="relative" style={{ cursor: isDrawing ? 'crosshair' : 'default' }}>
              <Document file={fileUrl} onLoadSuccess={onDocumentLoadSuccess} loading={<div className="p-4 text-gray-500">Loading PDF…</div>}>
                <Page pageNumber={pageNumber} renderAnnotationLayer renderTextLayer width={720} />
              </Document>
              {pageContainerRef.current && pageAnnotations.map((a: any) => {
                const rect = pageContainerRef.current!.getBoundingClientRect();
                const style: React.CSSProperties = {
                  position: 'absolute',
                  left: `${a.x * rect.width}px`,
                  top: `${a.y * rect.height}px`,
                  width: `${a.width * rect.width}px`,
                  height: `${a.height * rect.height}px`,
                  backgroundColor: a.type === 'highlight' ? (a.color || '#FFEB3B') : 'transparent',
                  opacity: a.opacity ?? (a.type === 'highlight' ? 0.3 : 1),
                  border: a.type === 'note' ? `2px solid ${a.color || '#4CAF50'}` : 'none',
                  pointerEvents: 'none',
                };
                return <div key={a._idx} style={style} title={a.comment || ''} />;
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
