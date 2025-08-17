import { useEffect, useState, useCallback } from 'react';
import { format } from 'date-fns';
import { Conversation, PendingReply, ReviewResult } from '../types';
import api from '../api/client';
import ReplyEditor from './ReplyEditor';
import ProposalViewer from './ProposalViewer';

interface ConversationDetailProps {
  conversationId: string;
  onBack: () => void;
}

const ConversationDetail: React.FC<ConversationDetailProps> = ({ conversationId, onBack }) => {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [pendingReplies, setPendingReplies] = useState<PendingReply[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPrompt, setShowPrompt] = useState<string | null>(null);
  const [editingReply, setEditingReply] = useState<PendingReply | null>(null);
  const [replyReviews, setReplyReviews] = useState<Record<string, ReviewResult>>({});
  const [loadingReviews, setLoadingReviews] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadConversationDetails();
  }, [conversationId]);

  const loadConversationDetails = async () => {
    try {
      setLoading(true);
      const [convData, repliesData] = await Promise.all([
        api.getConversation(conversationId),
        api.getPendingReplies(conversationId),
      ]);
      console.log('Conversation data received:', convData); // DEBUG
      console.log('Has latest_metadata?', !!convData.latest_metadata); // DEBUG
      console.log('Metadata fields:', {
        client_name: convData.client_name,
        project_name: convData.project_name,
        latest_metadata: convData.latest_metadata
      }); // DEBUG
      setConversation(convData);
      setPendingReplies(repliesData.pending_replies);
    } catch (err) {
      setError('Failed to load conversation details');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (reply: PendingReply) => {
    try {
      await api.approveReply(reply.reply_id, conversationId);
      setPendingReplies(prev => prev.filter(r => r.reply_id !== reply.reply_id));
      // Reload to get updated conversation
      loadConversationDetails();
    } catch (err: any) {
      console.error('Failed to approve reply:', err);

      // Extract error message from response
      const errorMessage = err.response?.data?.error || 'Failed to send proposal';
      const errorDetails = err.response?.data?.details;

      // Show detailed error to user
      if (errorDetails?.error_type === 'PdfGenerationError' || errorDetails?.error_type === 'ConfigurationError') {
        alert(`PDF Generation Error:\n\n${errorMessage}\n\nThe reply remains pending. Please check the system configuration and try again.`);
      } else {
        alert(`Error: ${errorMessage}\n\nThe reply remains pending. Please try again or contact support if the issue persists.`);
      }

      // Keep the reply in pending state - do NOT remove it
      // User can retry after fixing the underlying issue
    }
  };

  const handleReject = async (reply: PendingReply, reason: string) => {
    try {
      await api.rejectReply(reply.reply_id, conversationId, reason);
      setPendingReplies(prev => prev.filter(r => r.reply_id !== reply.reply_id));
    } catch (err) {
      console.error('Failed to reject reply:', err);
    }
  };

  const handleAmend = async (reply: PendingReply, newContent: string) => {
    try {
      await api.amendReply(reply.reply_id, conversationId, newContent);
      await handleApprove(reply);
      setEditingReply(null);
    } catch (err) {
      console.error('Failed to amend reply:', err);
    }
  };

  const showLLMPrompt = async (replyId: string) => {
    try {
      const data = await api.getReplyPrompt(replyId);
      setShowPrompt(data.prompt);
    } catch (err) {
      console.error('Failed to get prompt:', err);
    }
  };

  const loadReplyReview = useCallback(async (replyId: string) => {
    // Check if already loading this specific review
    setLoadingReviews(prev => {
      if (prev.has(replyId)) {
        return prev; // Already loading
      }
      return new Set(prev).add(replyId);
    });

    try {
      console.log('Loading review for reply:', replyId);
      const data = await api.getReplyReview(replyId);
      console.log('Review loaded:', data);
      setReplyReviews(prev => ({
        ...prev,
        [replyId]: data.review
      }));
    } catch (err) {
      console.error('Failed to get review for reply', replyId, ':', err);
      // Set a default error review so we don't keep retrying
      setReplyReviews(prev => ({
        ...prev,
        [replyId]: {
          relevance_score: 0,
          completeness_score: 0,
          accuracy_score: 0,
          next_steps_score: 0,
          overall_score: 0,
          red_flags: ['Review failed to load'],
          summary: 'Unable to load AI review. Please review manually.',
          reviewed_at: new Date().toISOString()
        }
      }));
    } finally {
      setLoadingReviews(prev => {
        const newSet = new Set(prev);
        newSet.delete(replyId);
        return newSet;
      });
    }
  }, []);

  // Load reviews when pending replies change
  useEffect(() => {
    pendingReplies.forEach(reply => {
      if (reply.status !== 'pending') {
        return; // Only review pending replies
      }
      
      if (reply.review) {
        // Use cached review from reply data
        setReplyReviews(prev => ({
          ...prev,
          [reply.reply_id]: reply.review!
        }));
      } else if (!replyReviews[reply.reply_id] && !loadingReviews.has(reply.reply_id)) {
        // Load review from API only if not already loaded or loading
        loadReplyReview(reply.reply_id);
      }
    });
  }, [pendingReplies, loadReplyReview, replyReviews, loadingReviews]);

  const getScoreColor = (score: number) => {
    if (score >= 4) return 'text-green-600 bg-green-100';
    if (score >= 3) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const ReviewDisplay = ({ review }: { review: ReviewResult }) => (
    <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium text-blue-900">AI Review</h4>
        <span className={`px-2 py-1 text-xs font-medium rounded-full ${getScoreColor(review.overall_score)}`}>
          Overall: {review.overall_score}/5
        </span>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2">
        <div className={`px-2 py-1 text-xs rounded ${getScoreColor(review.relevance_score)}`}>
          Relevance: {review.relevance_score}/5
        </div>
        <div className={`px-2 py-1 text-xs rounded ${getScoreColor(review.completeness_score)}`}>
          Complete: {review.completeness_score}/5
        </div>
        <div className={`px-2 py-1 text-xs rounded ${getScoreColor(review.accuracy_score)}`}>
          Accuracy: {review.accuracy_score}/5
        </div>
        <div className={`px-2 py-1 text-xs rounded ${getScoreColor(review.next_steps_score)}`}>
          Next Steps: {review.next_steps_score}/5
        </div>
      </div>

      {review.red_flags.length > 0 && (
        <div className="mb-2">
          <div className="text-xs font-medium text-red-700 mb-1">⚠️ Red Flags:</div>
          <ul className="text-xs text-red-600">
            {review.red_flags.map((flag, index) => (
              <li key={index} className="ml-2">• {flag}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-xs text-blue-800">{review.summary}</p>
    </div>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading conversation...</div>
      </div>
    );
  }

  if (error || !conversation) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500">{error || 'Conversation not found'}</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={onBack}
          className="mb-4 inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          ← Back to list
        </button>
        <h2 className="text-2xl font-bold text-gray-900">{conversation.subject || 'No subject'}</h2>
        <div className="mt-2 flex items-center space-x-4 text-sm text-gray-500">
          <span>Client: {conversation.client_name || conversation.client_email}</span>
          <span>•</span>
          <span>Phase: {conversation.phase.replace('_', ' ')}</span>
          <span>•</span>
          <span>Mode: {conversation.reply_mode}</span>
          {conversation.project_name && (
            <>
              <span>•</span>
              <span>Project: {conversation.project_name}</span>
            </>
          )}
        </div>
      </div>

      {/* Extracted Metadata */}
      {conversation.latest_metadata && (
        <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-lg font-medium text-blue-900 mb-4">Extracted Information</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium text-gray-700">Client Name:</span>{' '}
              <span className="text-gray-900">{conversation.latest_metadata.client_name || 'Not detected'}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Project Name:</span>{' '}
              <span className="text-gray-900">{conversation.latest_metadata.project_name || 'Not specified'}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Project Type:</span>{' '}
              <span className="text-gray-900">{conversation.latest_metadata.project_type || 'Unknown'}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">PDF Should Be Sent:</span>{' '}
              <span className={`font-semibold ${conversation.latest_metadata.should_send_pdf ? 'text-green-600' : 'text-gray-500'}`}>
                {conversation.latest_metadata.should_send_pdf ? 'Yes ✓' : 'No'}
              </span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Proposal Explicitly Requested:</span>{' '}
              <span className="text-gray-900">{conversation.latest_metadata.proposal_explicitly_requested ? 'Yes' : 'No'}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Revision Requested:</span>{' '}
              <span className="text-gray-900">{conversation.latest_metadata.revision_requested ? 'Yes' : 'No'}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Meeting Requested:</span>{' '}
              <span className="text-gray-900">{conversation.latest_metadata.meeting_requested ? 'Yes' : 'No'}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Action Required:</span>{' '}
              <span className="text-gray-900">{conversation.latest_metadata.action_required || 'N/A'}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Feedback Sentiment:</span>{' '}
              <span className="text-gray-900">{conversation.latest_metadata.feedback_sentiment || 'N/A'}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Confidence Score:</span>{' '}
              <span className="text-gray-900">
                {conversation.latest_metadata.confidence_score 
                  ? `${(conversation.latest_metadata.confidence_score * 100).toFixed(0)}%`
                  : 'N/A'}
              </span>
            </div>
            {conversation.latest_metadata.key_topics && conversation.latest_metadata.key_topics.length > 0 && (
              <div className="md:col-span-2">
                <span className="font-medium text-gray-700">Key Topics:</span>{' '}
                <span className="text-gray-900">{conversation.latest_metadata.key_topics.join(', ')}</span>
              </div>
            )}
            {conversation.latest_metadata.extraction_notes && (
              <div className="md:col-span-2">
                <span className="font-medium text-gray-700">Extraction Notes:</span>{' '}
                <span className="text-gray-900 italic">{conversation.latest_metadata.extraction_notes}</span>
              </div>
            )}
          </div>
          {conversation.metadata_updated_at && (
            <div className="mt-2 text-xs text-gray-500">
              Last extracted: {format(new Date(conversation.metadata_updated_at), 'MMM d, h:mm a')}
            </div>
          )}
        </div>
      )}

      {/* Pending Replies */}
      {pendingReplies.length > 0 && (
        <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <h3 className="text-lg font-medium text-yellow-900 mb-4">Pending Replies</h3>
          {pendingReplies.map((reply) => (
            <div key={reply.reply_id} className="mb-4 bg-white rounded-lg p-4 shadow">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-500">
                    Generated at {format(new Date(reply.generated_at), 'MMM d, h:mm a')}
                  </span>
                  {reply.metadata?.should_send_pdf !== undefined && (
                    <span className={`text-sm font-medium ${reply.metadata.should_send_pdf ? 'text-green-600' : 'text-gray-500'}`}>
                      PDF: {reply.metadata.should_send_pdf ? 'Yes' : 'No'}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => showLLMPrompt(reply.reply_id)}
                  className="text-sm text-indigo-600 hover:text-indigo-500"
                >
                  View Prompt
                </button>
              </div>

              {editingReply?.reply_id === reply.reply_id ? (
                <ReplyEditor
                  initialContent={reply.llm_response}
                  onSave={(content) => handleAmend(reply, content)}
                  onCancel={() => setEditingReply(null)}
                />
              ) : (
                <>
                  <div className="mb-4 p-3 bg-gray-50 rounded whitespace-pre-wrap">
                    {reply.llm_response}
                  </div>

                  {/* AI Review */}
                  {replyReviews[reply.reply_id] ? (
                    <ReviewDisplay review={replyReviews[reply.reply_id]} />
                  ) : loadingReviews.has(reply.reply_id) ? (
                    <div className="mb-3 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                      <div className="text-sm text-gray-500">Loading AI review...</div>
                    </div>
                  ) : (
                    <div className="mb-3 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                      <div className="text-sm text-gray-500">AI review unavailable</div>
                    </div>
                  )}

                  <div className="flex space-x-2">
                    <button
                      onClick={() => handleApprove(reply)}
                      className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                    >
                      Approve & Send
                    </button>
                    <button
                      onClick={() => setEditingReply(reply)}
                      className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => {
                        const reason = prompt('Rejection reason:');
                        if (reason) handleReject(reply, reason);
                      }}
                      className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                    >
                      Reject
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Email History */}
      <div className="bg-white shadow overflow-hidden sm:rounded-lg mb-6">
        <div className="px-4 py-5 sm:px-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900">Email History</h3>
        </div>
        <div className="border-t border-gray-200">
          <ul className="divide-y divide-gray-200">
            {conversation.email_history?.map((email) => (
              <li key={email.email_id} className="px-4 py-4">
                <div className="flex space-x-3">
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium">
                        {email.direction === 'inbound' ? email.from : 'You'}
                      </h3>
                      <p className="text-sm text-gray-500">
                        {format(new Date(email.timestamp), 'MMM d, h:mm a')}
                      </p>
                    </div>
                    <p className="text-sm text-gray-500">To: {email.to.join(', ')}</p>
                    <div className="text-sm text-gray-900 whitespace-pre-wrap mt-2">
                      {email.body}
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Proposals Section */}
      {['proposal_draft', 'proposal_sent', 'proposal_feedback', 'closed'].includes(conversation.phase) && (
        <div className="bg-white shadow overflow-hidden sm:rounded-lg mb-6">
          <div className="px-4 py-5 sm:px-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">Proposals</h3>
          </div>
          <div className="border-t border-gray-200">
            <ProposalViewer conversationId={conversationId} />
          </div>
        </div>
      )}

      {/* LLM Prompt Modal */}
      {showPrompt && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[80vh] overflow-hidden">
            <div className="px-4 py-3 border-b">
              <h3 className="text-lg font-medium">LLM Prompt</h3>
            </div>
            <div className="p-4 overflow-y-auto max-h-[calc(80vh-8rem)]">
              <pre className="whitespace-pre-wrap text-sm">{showPrompt}</pre>
            </div>
            <div className="px-4 py-3 border-t text-right">
              <button
                onClick={() => setShowPrompt(null)}
                className="inline-flex justify-center py-2 px-4 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ConversationDetail;
