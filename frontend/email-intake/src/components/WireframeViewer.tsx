import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import api from '../api/client';
import WireframeEditor from './WireframeEditor';

interface WireframeViewerProps {
    conversationId: string;
    selectedVersion?: number | null;
    onSelectWireframe?: (version: number) => void;
}

interface Wireframe {
    version: number;
    created_at: string;
    screen_count: number;
}

interface Screen {
    id: string;
    name: string;
    description?: string;
    url?: string;
}

export default function WireframeViewer({
    conversationId,
    selectedVersion,
    onSelectWireframe,
}: WireframeViewerProps) {
    const [wireframes, setWireframes] = useState<Wireframe[]>([]);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentVersion, setCurrentVersion] = useState<number | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [screens, setScreens] = useState<Screen[]>([]);
    const [selectedScreen, setSelectedScreen] = useState<string | null>(null);
    const [exporting, setExporting] = useState(false);
    const [toastMessage, setToastMessage] = useState<{ message: string; tone: 'info' | 'success' | 'error' } | null>(null);

    // Share State
    const [sharing, setSharing] = useState(false);
    const [shareUrl, setShareUrl] = useState<string | null>(null);
    const [shareModalOpen, setShareModalOpen] = useState(false);

    // Editor State
    const [editingScreen, setEditingScreen] = useState<{ id: string; name: string; url: string } | null>(null);

    const showToast = (message: string, tone: 'info' | 'success' | 'error' = 'info') => {
        setToastMessage({ message, tone });
        setTimeout(() => setToastMessage(null), 3000);
    };

    const loadWireframes = async () => {
        try {
            setLoading(true);
            const response = await api.listWireframes(conversationId);
            setWireframes(response.wireframes || []);

            if (response.wireframes?.length > 0) {
                const latestVersion = response.wireframes[0].version;
                if (!currentVersion) {
                    setCurrentVersion(selectedVersion || latestVersion);
                    onSelectWireframe?.(selectedVersion || latestVersion);
                } else if (selectedVersion && selectedVersion !== currentVersion) {
                    setCurrentVersion(selectedVersion);
                }
            }
        } catch (err) {
            console.error('Failed to load wireframes:', err);
            setError('Failed to load wireframes');
        } finally {
            setLoading(false);
        }
    };

    const loadWireframePreview = async (version: number) => {
        try {
            const response = await api.getWireframeUrl(conversationId, version);
            setScreens(response.screens || []);
            if (response.screens?.length > 0) {
                // If we have a selected screen, try to keep it if it exists in new version? 
                // For now, simpler to just reset to first or keep if id matches.
                // Let's just default to first for now or keep current if valid.
                let targetScreen = response.screens[0];
                if (selectedScreen) {
                    const found = response.screens.find((s: Screen) => s.id === selectedScreen);
                    if (found) targetScreen = found;
                }

                setSelectedScreen(targetScreen.id);
                // Use the individual screen URL, not the index.html URL
                setPreviewUrl(targetScreen.url || response.url);
            } else {
                setPreviewUrl(response.url);
            }
        } catch (err) {
            console.error('Failed to load wireframe preview:', err);
            setError('Failed to load wireframe preview');
        }
    };

    const handleGenerate = async () => {
        try {
            setGenerating(true);
            setError(null);

            // Start async generation - returns immediately with job_id
            const startResponse = await api.generateWireframes(conversationId);
            const jobId = startResponse.job_id;

            if (!jobId) {
                throw new Error('No job ID returned from generation');
            }

            showToast('Wireframe generation started...', 'info');

            // Poll for completion
            const pollInterval = 3000; // 3 seconds
            const maxAttempts = 60; // 3 minutes max
            let attempts = 0;

            const pollStatus = async (): Promise<void> => {
                attempts++;

                try {
                    const statusResponse = await api.getGenerationStatus(conversationId, jobId);

                    if (statusResponse.status === 'completed') {
                        // Success - load the new wireframes
                        showToast(`Wireframes v${statusResponse.version} generated successfully!`, 'success');
                        await loadWireframes();
                        if (statusResponse.version) {
                            setCurrentVersion(statusResponse.version);
                            onSelectWireframe?.(statusResponse.version);
                        }
                        setGenerating(false);
                        return;
                    }

                    if (statusResponse.status === 'failed') {
                        throw new Error(statusResponse.error || 'Generation failed');
                    }

                    if (attempts >= maxAttempts) {
                        throw new Error('Generation timed out after 3 minutes');
                    }

                    // Still pending or in_progress - continue polling
                    setTimeout(() => {
                        pollStatus();
                    }, pollInterval);
                } catch (pollError: any) {
                    // Network error during polling - retry a few times
                    if (attempts < maxAttempts && pollError.code === 'Network Error') {
                        setTimeout(() => {
                            pollStatus();
                        }, pollInterval);
                        return;
                    }
                    throw pollError;
                }
            };

            // Start polling after a brief delay
            setTimeout(() => {
                pollStatus();
            }, 2000);
        } catch (err: any) {
            console.error('Failed to generate wireframes:', err);
            setError(err.message || 'Failed to generate wireframes');
            showToast('Failed to generate wireframes', 'error');
            setGenerating(false);
        }
    };

    const handleExport = async (format: 'react' | 'html') => {
        if (!currentVersion) return;

        try {
            setExporting(true);
            const response = await api.exportWireframes(conversationId, currentVersion, format);

            // Create downloadable content
            if (format === 'react') {
                const components = response.components || {};
                const content = Object.entries(components)
                    .map(([name, code]) => `// ${name}.jsx\n${code}`)
                    .join('\n\n// ========================\n\n');

                const blob = new Blob([content], { type: 'text/javascript' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `wireframes-v${currentVersion}-react.jsx`;
                a.click();
                URL.revokeObjectURL(url);
            } else {
                const screens = response.screens || {};
                const content = Object.entries(screens)
                    .map(([id, html]) => `<!-- ${id}.html -->\n${html}`)
                    .join('\n\n<!-- ======================== -->\n\n');

                const blob = new Blob([content], { type: 'text/html' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `wireframes-v${currentVersion}.html`;
                a.click();
                URL.revokeObjectURL(url);
            }

            showToast(`Exported wireframes as ${format.toUpperCase()}`, 'success');
        } catch (err) {
            console.error('Failed to export wireframes:', err);
            showToast('Failed to export wireframes', 'error');
        } finally {
            setExporting(false);
        }
    };

    const handleShare = async () => {
        if (!currentVersion) return;

        try {
            setSharing(true);
            const response = await api.shareWireframe(conversationId, currentVersion);
            setShareUrl(response.share_url);
            setShareModalOpen(true);
            showToast('Share link generated!', 'success');
        } catch (err) {
            console.error('Failed to generate share link:', err);
            showToast('Failed to generate share link', 'error');
        } finally {
            setSharing(false);
        }
    };

    const copyToClipboard = async () => {
        if (!shareUrl) return;
        try {
            await navigator.clipboard.writeText(shareUrl);
            showToast('Link copied to clipboard!', 'success');
        } catch (err) {
            console.error('Failed to copy:', err);
            showToast('Failed to copy link', 'error');
        }
    };

    const handleVisionSubmit = async (payload: { screenshots: any[]; annotations: any[]; prompt: string }) => {
        if (!currentVersion || !editingScreen) return;

        try {
            showToast('Submitting edits...', 'info');
            const result = await api.annotateWireframeVision(
                conversationId,
                currentVersion,
                editingScreen.id,
                payload
            );

            // Handle Async Job (202 Accepted pattern)
            if (result.job_id) {
                const jobId = result.job_id;
                setEditingScreen(null); // Close editor to show progress
                showToast('Vision edit processing... (this may take 5-10 minutes)', 'info');
                setGenerating(true);

                // Poll for completion
                const pollInterval = 5000;
                const maxAttempts = 200; // ~16 mins max
                let attempts = 0;

                const pollStatus = async () => {
                    attempts++;
                    try {
                        const status = await api.getGenerationStatus(conversationId, jobId);

                        if (status.status === 'completed') {
                            showToast(`Edits applied! Created version ${status.version}`, 'success');
                            await loadWireframes();
                            if (status.version) {
                                setCurrentVersion(status.version);
                                onSelectWireframe?.(status.version);
                            }
                            setGenerating(false);
                            return;
                        }

                        if (status.status === 'failed') {
                            throw new Error(status.error || 'Edit generation failed');
                        }

                        if (attempts >= maxAttempts) {
                            throw new Error('Edit processing timed out');
                        }

                        setTimeout(pollStatus, pollInterval);
                    } catch (pollError: any) {
                        console.error('Polling error:', pollError);
                        if (attempts < maxAttempts) {
                            setTimeout(pollStatus, pollInterval);
                        } else {
                            showToast(pollError.message || 'Edit processing failed', 'error');
                            setGenerating(false);
                        }
                    }
                };

                pollStatus();
                return;
            }

            // Handle Synchronous Success (Fallback)
            if (result.success && result.new_version) {
                const newVersion = result.new_version;
                showToast(`Edits applied! Created version ${newVersion}`, 'success');
                setEditingScreen(null);

                await loadWireframes();
                setCurrentVersion(newVersion);
                onSelectWireframe?.(newVersion);
            }
        } catch (err: any) {
            console.error('Failed to submit vision edits:', err);
            showToast(err.response?.data?.error || 'Failed to submit edits', 'error');
            setGenerating(false);
        }
    };

    useEffect(() => {
        loadWireframes();
    }, [conversationId]);

    useEffect(() => {
        if (currentVersion) {
            loadWireframePreview(currentVersion);
            // Note: Don't call onSelectWireframe here as it causes infinite loops.
            // The callback is called explicitly in handleGenerate, handleVisionSubmit, 
            // and the dropdown onChange handler where user explicitly changes version.
        }
    }, [currentVersion]);

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
        );
    }

    // Render Editor Mode
    if (editingScreen) {
        return (
            <WireframeEditor
                screenUrl={editingScreen.url}
                screenId={editingScreen.id}
                screenName={editingScreen.name}
                onCancel={() => setEditingScreen(null)}
                onSubmitStart={() => { }}
                onSubmitVision={handleVisionSubmit}
            />
        );
    }

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden" style={{ minHeight: '600px' }}>
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-gray-800">Wireframes</h3>
                    {wireframes.length > 0 && (
                        <select
                            value={currentVersion || ''}
                            onChange={(e) => setCurrentVersion(Number(e.target.value))}
                            className="text-sm border border-gray-300 rounded px-2 py-1"
                        >
                            {wireframes.map((w) => (
                                <option key={w.version} value={w.version}>
                                    v{w.version} - {w.screen_count} screens - {format(new Date(w.created_at), 'MMM d, h:mm a')}
                                </option>
                            ))}
                        </select>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    {currentVersion && (
                        <div className="relative">
                            <button
                                onClick={() => document.getElementById('export-menu')?.classList.toggle('hidden')}
                                disabled={exporting}
                                className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50"
                            >
                                {exporting ? 'Exporting...' : 'Export ▾'}
                            </button>
                            <div id="export-menu" className="hidden absolute right-0 mt-1 w-40 bg-white border border-gray-200 rounded shadow-lg z-10">
                                <button
                                    onClick={() => handleExport('react')}
                                    className="block w-full text-left px-4 py-2 text-sm hover:bg-gray-50"
                                >
                                    Export as React
                                </button>
                                <button
                                    onClick={() => handleExport('html')}
                                    className="block w-full text-left px-4 py-2 text-sm hover:bg-gray-50"
                                >
                                    Export as HTML
                                </button>
                            </div>
                        </div>
                    )}
                    {currentVersion && (
                        <button
                            onClick={handleShare}
                            disabled={sharing}
                            className="px-3 py-1.5 text-sm bg-purple-500 text-white rounded hover:bg-purple-600 disabled:opacity-50"
                        >
                            {sharing ? 'Sharing...' : '🔗 Share'}
                        </button>
                    )}
                    <button
                        onClick={handleGenerate}
                        disabled={generating}
                        className="px-3 py-1.5 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
                    >
                        {generating ? 'Generating...' : wireframes.length > 0 ? 'Regenerate' : 'Generate Wireframes'}
                    </button>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div className="p-4 bg-red-50 border-b border-red-200 text-red-700 text-sm">
                    {error}
                </div>
            )}

            {/* Content */}
            {wireframes.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                    <div className="text-4xl mb-3">🎨</div>
                    <p className="mb-4">No wireframes generated yet</p>
                    <button
                        onClick={handleGenerate}
                        disabled={generating}
                        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
                    >
                        {generating ? 'Generating...' : 'Generate Wireframes'}
                    </button>
                </div>
            ) : (
                <div className="flex h-full" style={{ minHeight: '600px' }}>
                    {/* Sidebar - Screen List */}
                    <div className="w-48 border-r border-gray-200 bg-gray-50 overflow-y-auto">
                        <div className="p-2 text-xs font-medium text-gray-500 uppercase">Screens</div>
                        {screens.map((screen) => (
                            <button
                                key={screen.id}
                                onClick={() => {
                                    setSelectedScreen(screen.id);
                                    if (screen.url) {
                                        setPreviewUrl(screen.url);
                                    }
                                }}
                                className={`w-full text-left px-3 py-2 text-sm truncate ${selectedScreen === screen.id
                                    ? 'bg-blue-50 text-blue-700 border-l-2 border-blue-500'
                                    : 'text-gray-700 hover:bg-gray-100'
                                    }`}
                            >
                                {screen.name}
                            </button>
                        ))}
                    </div>

                    {/* Preview */}
                    <div className="flex-1 bg-gray-100 flex flex-col relative">
                        {/* Preview Header - for Edit Button */}
                        {selectedScreen && previewUrl && (
                            <div className="absolute top-4 right-4 z-10">
                                <button
                                    onClick={() => {
                                        // Find screen obj
                                        const s = screens.find(sc => sc.id === selectedScreen);
                                        if (s && s.url) {
                                            setEditingScreen({ id: s.id, name: s.name, url: s.url });
                                        }
                                    }}
                                    className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-md shadow hover:bg-indigo-700 flex items-center gap-2"
                                >
                                    <span>✏️ Edit Vision</span>
                                </button>
                            </div>
                        )}

                        {previewUrl ? (
                            <iframe
                                src={previewUrl}
                                className="w-full h-full border-0"
                                title="Wireframe Preview"
                                style={{ minHeight: '600px' }}
                            />
                        ) : (
                            <div className="flex items-center justify-center h-full text-gray-400">
                                Select a screen to preview
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Toast */}
            {toastMessage && (
                <div
                    className={`fixed bottom-4 right-4 px-4 py-2 rounded shadow-lg ${toastMessage.tone === 'success'
                        ? 'bg-green-500 text-white'
                        : toastMessage.tone === 'error'
                            ? 'bg-red-500 text-white'
                            : 'bg-gray-800 text-white'
                        }`}
                >
                    {toastMessage.message}
                </div>
            )}

            {/* Share Modal */}
            {shareModalOpen && shareUrl && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold text-gray-900">Share Wireframes</h3>
                            <button
                                onClick={() => setShareModalOpen(false)}
                                className="text-gray-400 hover:text-gray-600"
                            >
                                ✕
                            </button>
                        </div>

                        <p className="text-sm text-gray-600 mb-4">
                            Share this link with your client. They can view the wireframes without logging in.
                        </p>

                        <div className="flex items-center gap-2 mb-4">
                            <input
                                type="text"
                                readOnly
                                value={shareUrl}
                                className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm bg-gray-50 text-gray-700"
                            />
                            <button
                                onClick={copyToClipboard}
                                className="px-4 py-2 bg-purple-500 text-white text-sm rounded hover:bg-purple-600"
                            >
                                📋 Copy
                            </button>
                        </div>

                        <div className="text-xs text-gray-500 flex items-center gap-2">
                            <span>⏰</span>
                            <span>This link expires in 7 days</span>
                        </div>

                        <div className="mt-6 flex justify-end gap-3">
                            <button
                                onClick={() => window.open(shareUrl, '_blank')}
                                className="px-4 py-2 text-sm text-purple-600 hover:text-purple-800"
                            >
                                Open Preview →
                            </button>
                            <button
                                onClick={() => setShareModalOpen(false)}
                                className="px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded hover:bg-gray-200"
                            >
                                Done
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
