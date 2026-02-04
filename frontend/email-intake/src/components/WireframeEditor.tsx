import { useRef, useState, useEffect } from 'react';
import html2canvas from 'html2canvas';
import { PdfAnnotation } from '../types';

// Reuse existing types or define new ones
export interface WireframeEditorProps {
    screenUrl: string;
    screenId: string;
    screenName: string;
    onCancel: () => void;
    onSubmitStart?: () => boolean | void;
    onSubmitVision: (payload: { screenshots: { screenId: string; imageBase64: string }[]; annotations: any[]; prompt: string }) => Promise<void> | void;
}

const HIGHLIGHT_COLOR = '#3B82F6'; // Blue for wireframes

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

const WireframeEditor: React.FC<WireframeEditorProps> = ({
    screenUrl,
    screenId,
    screenName,
    onCancel,
    onSubmitStart,
    onSubmitVision
}) => {
    const [htmlContent, setHtmlContent] = useState<string>('');
    const [annotations, setAnnotations] = useState<PdfAnnotation[]>([]);
    const [prompt, setPrompt] = useState<string>('');
    const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
    const [isDrawing, setIsDrawing] = useState<boolean>(false);
    const [startPt, setStartPt] = useState<{ x: number; y: number } | null>(null);
    const [currentRect, setCurrentRect] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const containerRef = useRef<HTMLDivElement | null>(null);
    const iframeRef = useRef<HTMLIFrameElement | null>(null);

    // Fetch HTML content to render in iframe (avoid CORS issues with direct src)
    useEffect(() => {
        const fetchContent = async () => {
            try {
                setLoading(true);
                const response = await fetch(screenUrl);
                if (!response.ok) throw new Error('Failed to load wireframe');
                const text = await response.text();
                // Inject base tag to handle relative links if needed, though usually wireframes are self-contained or use absolute CDN links
                setHtmlContent(text);
            } catch (err) {
                console.error('Error fetching wireframe:', err);
                setError('Failed to load wireframe content');
            } finally {
                setLoading(false);
            }
        };
        fetchContent();
    }, [screenUrl]);

    const handleMouseDown = (e: React.MouseEvent) => {
        if (!containerRef.current) return;
        const rect = containerRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        setIsDrawing(true);
        setStartPt({ x, y });
    };

    const handleMouseUp = (e: React.MouseEvent) => {
        if (!isDrawing || !startPt || !containerRef.current) return;
        const rect = containerRef.current.getBoundingClientRect();
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
            setAnnotations((prev) => [
                ...prev,
                {
                    pageIndex: 0, // Single screen treated as page 0
                    screenId: screenId, // Store screenId
                    x: nx,
                    y: ny,
                    width: nwidth,
                    height: nheight,
                    type: 'highlight',
                    color: HIGHLIGHT_COLOR,
                    opacity: 0.55,
                },
            ]);
        }

        setIsDrawing(false);
        setStartPt(null);
        setCurrentRect(null);
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        if (!isDrawing || !startPt || !containerRef.current) return;
        const rect = containerRef.current.getBoundingClientRect();
        const endX = e.clientX - rect.left;
        const endY = e.clientY - rect.top;
        const left = Math.min(startPt.x, endX);
        const top = Math.min(startPt.y, endY);
        const width = Math.abs(endX - startPt.x);
        const height = Math.abs(endY - startPt.y);
        setCurrentRect({ x: left, y: top, width, height });
    };

    const captureScreen = async (): Promise<{ success: boolean; data?: string; error?: string }> => {
        console.log('[WireframeEditor] Starting screen capture...');

        // Try to access iframe content - may fail due to cross-origin
        let iframeBody: HTMLElement | null = null;
        try {
            iframeBody = iframeRef.current?.contentDocument?.body || null;
            console.log('[WireframeEditor] Iframe body accessible:', !!iframeBody);
        } catch (corsError) {
            console.warn('[WireframeEditor] Cross-origin access blocked:', corsError);
        }

        // If we can't access iframe body (cross-origin), capture the container div instead
        const captureTarget = iframeBody || containerRef.current;

        if (!captureTarget) {
            console.error('[WireframeEditor] No capture target available');
            return { success: false, error: 'Cannot capture screen: iframe not accessible (cross-origin restriction)' };
        }

        try {
            console.log('[WireframeEditor] Capturing with html2canvas...');
            // Capture the target element
            const canvas = await html2canvas(captureTarget, {
                useCORS: true,
                scale: 1,
                logging: false, // Reduce console noise
                allowTaint: false,
                foreignObjectRendering: true, // Enable for better iframe capture
            });

            console.log('[WireframeEditor] Canvas captured, dimensions:', canvas.width, 'x', canvas.height);

            // Create composite canvas with annotations
            const compositeCanvas = document.createElement('canvas');
            compositeCanvas.width = canvas.width;
            compositeCanvas.height = canvas.height;
            const ctx = compositeCanvas.getContext('2d');
            if (!ctx) {
                console.error('[WireframeEditor] Failed to create canvas context');
                return { success: false, error: 'Failed to create canvas context' };
            }

            // Draw wireframe
            ctx.drawImage(canvas, 0, 0);

            // Draw annotations
            annotations.forEach((a, idx) => {
                const x = a.x * canvas.width;
                const y = a.y * canvas.height;
                const w = a.width * canvas.width;
                const h = a.height * canvas.height;

                // Draw Highlight
                ctx.fillStyle = applyAlpha(a.color || HIGHLIGHT_COLOR, 0.4);
                ctx.fillRect(x, y, w, h);
                ctx.strokeStyle = applyAlpha(a.color || HIGHLIGHT_COLOR, 1);
                ctx.lineWidth = 2;
                ctx.strokeRect(x, y, w, h);

                // Draw Badge
                const badgeSize = 20;
                ctx.fillStyle = '#111827';
                ctx.beginPath();
                ctx.arc(x + w, y, badgeSize / 2, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 12px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(String(idx + 1), x + w, y);
            });

            const dataUrl = compositeCanvas.toDataURL('image/png');
            console.log('[WireframeEditor] Screenshot captured successfully, data length:', dataUrl.length);
            return { success: true, data: dataUrl.split(',')[1] || dataUrl };

        } catch (e: any) {
            console.error('[WireframeEditor] Screenshot failed:', e);
            return { success: false, error: e.message || 'Screenshot capture failed' };
        }
    };

    const submit = async () => {
        setIsSubmitting(true);
        setError(null); // Clear previous errors
        const shouldProceed = onSubmitStart?.();
        if (shouldProceed === false) {
            setIsSubmitting(false);
            return;
        }

        const result = await captureScreen();
        if (result.success && result.data) {
            try {
                await onSubmitVision({
                    screenshots: [{ screenId, imageBase64: result.data }],
                    annotations,
                    prompt
                });
                // Note: onSubmitVision handles success (closes modal). 
                // If it throws, we catch it here.
            } catch (err: any) {
                console.error('Submission error:', err);
                setError(err.message || 'Submission failed');
                setIsSubmitting(false);
            }
        } else {
            console.error('Failed to capture screenshot:', result.error);
            setError(`Failed to capture screenshot: ${result.error}`);
            setIsSubmitting(false);
        }
    };

    return (
        <div className={`fixed inset-0 z-50 bg-black bg-opacity-75 flex items-center justify-center p-4 ${isSubmitting ? 'cursor-wait' : ''}`}>
            <div className="bg-white w-full max-w-7xl h-[90vh] rounded-xl shadow-2xl flex overflow-hidden">
                {/* Main Editor Area */}
                <div className="flex-1 flex flex-col border-r bg-gray-100 relative">
                    {/* Header */}
                    <div className="bg-white p-3 border-b flex items-center justify-between shadow-sm z-10">
                        <div className="flex items-center gap-3">
                            <span className="font-bold text-gray-800">Edit Wireframe</span>
                            <span className="text-gray-400">|</span>
                            <span className="font-medium text-gray-600">{screenName}</span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span className="bg-blue-100 text-blue-700 px-2 py-1 rounded">Vision Edit</span>
                        </div>
                    </div>

                    {/* Canvas Area */}
                    <div className="flex-1 overflow-hidden relative flex items-center justify-center p-8">
                        {loading && <div className="text-gray-500 flex items-center gap-2"><div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full"></div> Loading screen...</div>}
                        {error && <div className="text-red-500">{error}</div>}

                        {!loading && !error && (
                            <div
                                ref={containerRef}
                                onMouseDown={handleMouseDown}
                                onMouseUp={handleMouseUp}
                                onMouseMove={handleMouseMove}
                                onMouseLeave={() => { if (isDrawing) { setIsDrawing(false); setStartPt(null); setCurrentRect(null); } }}
                                className="relative shadow-lg bg-white"
                                style={{
                                    width: '100%',
                                    height: '100%',
                                    maxWidth: '1024px', // Standard desktop width
                                    cursor: 'crosshair',
                                    userSelect: 'none',
                                    overflow: 'hidden' // Clip iframe
                                }}
                            >
                                {/* The Iframe Display */}
                                <iframe
                                    ref={iframeRef}
                                    srcDoc={htmlContent}
                                    title="Wireframe Editor"
                                    className="w-full h-full border-0 pointer-events-none" // pointer-events-none to let container handle mouse events for drawing
                                    sandbox="allow-scripts allow-same-origin" // Allow scripts and same-origin access for screenshot capture
                                />

                                {/* Drawing Overlay (Annotations) */}
                                {annotations.map((a, idx) => (
                                    <div
                                        key={idx}
                                        style={{
                                            position: 'absolute',
                                            left: `${a.x * 100}%`,
                                            top: `${a.y * 100}%`,
                                            width: `${a.width * 100}%`,
                                            height: `${a.height * 100}%`,
                                            backgroundColor: applyAlpha(HIGHLIGHT_COLOR, 0.2),
                                            border: `2px solid ${HIGHLIGHT_COLOR}`,
                                            pointerEvents: 'none'
                                        }}
                                    >
                                        <div className="absolute -top-3 -right-3 w-6 h-6 bg-gray-900 text-white rounded-full flex items-center justify-center text-xs font-bold border-2 border-white shadow-sm">
                                            {idx + 1}
                                        </div>
                                    </div>
                                ))}

                                {/* Current Drawing Rect */}
                                {currentRect && (
                                    <div
                                        style={{
                                            position: 'absolute',
                                            left: currentRect.x,
                                            top: currentRect.y,
                                            width: currentRect.width,
                                            height: currentRect.height,
                                            backgroundColor: 'rgba(59, 130, 246, 0.2)',
                                            border: '2px dashed rgba(59, 130, 246, 0.8)',
                                            pointerEvents: 'none',
                                        }}
                                    />
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {/* Sidebar */}
                <div className="w-80 bg-white flex flex-col z-20 shadow-xl">
                    <div className="p-4 border-b">
                        <h3 className="font-semibold text-gray-800">Annotations</h3>
                        <p className="text-xs text-gray-500 mt-1">Draw boxes on the screen to add comments.</p>
                    </div>

                    <div className="flex-1 overflow-auto p-4 space-y-4">
                        {annotations.length === 0 && (
                            <div className="text-center py-8 text-gray-400 bg-gray-50 rounded-lg border border-dashed border-gray-200">
                                <p>No annotations yet</p>
                                <p className="text-xs mt-1">Click and drag on the preview</p>
                            </div>
                        )}

                        {annotations.map((a, idx) => (
                            <div key={idx} className="bg-white border rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow relative group">
                                <div className="flex items-center gap-2 mb-2">
                                    <span className="w-5 h-5 bg-gray-900 text-white rounded-full flex items-center justify-center text-xs font-bold">
                                        {idx + 1}
                                    </span>
                                    <span className="text-xs font-medium text-gray-500">
                                        Screen Area
                                    </span>
                                    <button
                                        onClick={() => setAnnotations(prev => prev.filter((_, i) => i !== idx))}
                                        className="ml-auto text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                                        title="Remove annotation"
                                    >
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                </div>
                                <textarea
                                    value={a.comment || ''}
                                    onChange={(e) => setAnnotations(prev => prev.map((item, i) => i === idx ? { ...item, comment: e.target.value } : item))}
                                    placeholder="What should change here?"
                                    className="w-full text-sm border-gray-200 rounded focus:ring-blue-500 focus:border-blue-500 min-h-[60px] resize-y"
                                    autoFocus={!a.comment}
                                />
                            </div>
                        ))}
                    </div>

                    <div className="p-4 border-t bg-gray-50 space-y-3">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Overall Instructions (Optional)
                            </label>
                            <textarea
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                placeholder="E.g. Make the colors warmer, increase spacing..."
                                className="w-full text-sm border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 h-20"
                            />
                        </div>

                        <div className="flex gap-3 pt-2">
                            <button
                                onClick={onCancel}
                                disabled={isSubmitting}
                                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-100 font-medium transition-colors disabled:opacity-50"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={submit}
                                disabled={isSubmitting}
                                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium shadow-sm transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                            >
                                {isSubmitting ? (
                                    <>
                                        <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
                                        Saving...
                                    </>
                                ) : (
                                    <>
                                        <span>Apply Edits</span>
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default WireframeEditor;
