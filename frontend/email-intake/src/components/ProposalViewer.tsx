import { useEffect, useRef, useState } from 'react';
import { format } from 'date-fns';
import api from '../api/client';
import PDFAnnotator from './PDFAnnotator';

interface ProposalViewerProps {
  conversationId: string;
  selectedVersion?: number | null;
  onSelectProposal?: (version: number) => void;
}

interface Proposal {
  version: number;
  created_at: string;
  file_size: number;
  budget?: string;
  has_revisions: boolean;
}

const ProposalViewer: React.FC<ProposalViewerProps> = ({ conversationId, selectedVersion, onSelectProposal }) => {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingVersion, setDownloadingVersion] = useState<number | null>(null);
  const [editingVersion, setEditingVersion] = useState<number | null>(null);
  const [editorUrl, setEditorUrl] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; tone: 'info' | 'success' | 'error' } | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const submitInFlightRef = useRef(false);
  const toastTimerRef = useRef<number | null>(null);

  useEffect(() => {
    loadProposals();
  }, [conversationId]);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) {
        window.clearTimeout(toastTimerRef.current);
      }
    };
  }, []);

  const showToast = (message: string, tone: 'info' | 'success' | 'error' = 'info') => {
    setToast({ message, tone });
    if (toastTimerRef.current) {
      window.clearTimeout(toastTimerRef.current);
    }
    toastTimerRef.current = window.setTimeout(() => setToast(null), 4000);
  };

  const loadProposals = async () => {
    try {
      setLoading(true);
      const data = await api.listProposals(conversationId);
      setProposals(data.proposals);
      // Auto-select the most recent proposal (first in list) if nothing selected
      if (data.proposals.length > 0 && selectedVersion == null && onSelectProposal) {
        onSelectProposal(data.proposals[0].version);
      }
    } catch (err) {
      setError('Failed to load proposals');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (version: number) => {
    try {
      setDownloadingVersion(version);
      const data = await api.getProposalUrl(conversationId, version);

      // Open the presigned URL in a new tab
      window.open(data.url, '_blank');
    } catch (err) {
      console.error('Failed to get proposal URL:', err);
      setError('Failed to download proposal');
    } finally {
      setDownloadingVersion(null);
    }
  };

  const openEditor = async (version: number) => {
    try {
      setDownloadingVersion(version);
      const data = await api.getProposalUrl(conversationId, version);
      setEditorUrl(data.url);
      setEditingVersion(version);
    } catch (err) {
      console.error('Failed to open editor:', err);
      setError('Failed to open editor');
    } finally {
      setDownloadingVersion(null);
    }
  };

  const handleVisionSubmit = async (
    baseVersion: number | null,
    payload: { pages: { pageIndex: number; imageBase64: string }[]; annotations: any[]; prompt: string },
  ) => {
    if (!baseVersion) return;
    try {
      await api.annotateProposalVision(conversationId, baseVersion, payload);
      await loadProposals();
      showToast('Edits saved. New version is ready.', 'success');
    } catch (err: any) {
      console.error('Failed to save with vision:', err);
      showToast(err?.response?.data?.error || 'Failed to save vision edits', 'error');
    } finally {
      submitInFlightRef.current = false;
      setEditingVersion(null);
      setEditorUrl(null);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleGenerate = async () => {
    try {
      setIsGenerating(true);
      showToast('Generating proposal...', 'info');
      const result = await api.generateProposal(conversationId);
      showToast(result.message || 'Proposal generated!', 'success');
      await loadProposals();
    } catch (err: any) {
      console.error('Failed to generate proposal:', err);
      showToast(err?.response?.data?.error || 'Failed to generate proposal', 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-center text-gray-500">
        Loading proposals...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center text-red-600">
        {error}
      </div>
    );
  }

  if (proposals.length === 0) {
    return (
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Proposal History</h3>
          <button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="px-4 py-2 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isGenerating ? 'Generating...' : '+ Generate Proposal'}
          </button>
        </div>
        <div className="text-center text-gray-500">No proposals generated yet</div>
        {toast && (
          <div className="fixed bottom-4 right-4 z-50">
            <div className={`px-4 py-3 rounded shadow-lg text-sm text-white ${toast.tone === 'success' ? 'bg-green-600' : toast.tone === 'error' ? 'bg-red-600' : 'bg-blue-600'}`}>
              {toast.message}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Proposal History</h3>
        <button
          onClick={handleGenerate}
          disabled={isGenerating}
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isGenerating ? 'Generating...' : '+ Generate Proposal'}
        </button>
      </div>
      <div className="space-y-3">
        {proposals.map((proposal) => (
          <div
            key={proposal.version}
            className="border rounded-lg p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">Version {proposal.version}</span>
                  {proposal.has_revisions && (
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                      Revised
                    </span>
                  )}
                </div>
                <div className="text-sm text-gray-600 mt-1">
                  Created: {format(new Date(proposal.created_at), 'MMM d, yyyy h:mm a')}
                </div>
                <div className="text-sm text-gray-600">
                  Size: {formatFileSize(proposal.file_size)}
                  {proposal.budget && ` • Budget: $${proposal.budget}`}
                </div>
              </div>
              <div className="flex items-center gap-2 ml-4">
                {onSelectProposal && (
                  <button
                    onClick={() => onSelectProposal(proposal.version)}
                    className={`px-4 py-2 rounded transition-colors ${selectedVersion === proposal.version
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                  >
                    {selectedVersion === proposal.version ? '✓ Selected' : 'Use'}
                  </button>
                )}
                <button
                  onClick={() => handleDownload(proposal.version)}
                  disabled={downloadingVersion === proposal.version}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {downloadingVersion === proposal.version ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                          fill="none"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                      Loading...
                    </span>
                  ) : (
                    'View PDF'
                  )}
                </button>
                <button onClick={() => openEditor(proposal.version)} className="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600">Edit</button>
              </div>
            </div>
          </div>
        ))}
      </div>
      {editingVersion && editorUrl && (
        <PDFAnnotator
          fileUrl={editorUrl}
          onCancel={() => {
            setEditingVersion(null);
            setEditorUrl(null);
            submitInFlightRef.current = false;
          }}
          onSubmitStart={() => {
            if (submitInFlightRef.current) return false;
            submitInFlightRef.current = true;
            showToast('Edits submitted. Generating updated PDF...', 'info');
            return true;
          }}
          onSubmitVision={(payload) => handleVisionSubmit(editingVersion, payload)}
        />
      )}
      {toast && (
        <div className="fixed bottom-4 right-4 z-50">
          <div
            className={`px-4 py-3 rounded shadow-lg text-sm text-white ${toast.tone === 'success'
              ? 'bg-green-600'
              : toast.tone === 'error'
                ? 'bg-red-600'
                : 'bg-blue-600'
              }`}
          >
            {toast.message}
          </div>
        </div>
      )}
    </div>
  );
};

export default ProposalViewer;
