import React, { useEffect, useState } from 'react';
import { format } from 'date-fns';
import { Conversation } from '../types';
import api from '../api/client';

interface ConversationListProps {
  onSelectConversation: (conversation: Conversation) => void;
}

const ConversationList: React.FC<ConversationListProps> = ({ onSelectConversation }) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nextToken, setNextToken] = useState<string | undefined>();

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async (token?: string) => {
    try {
      setLoading(true);
      const data = await api.listConversations(20, token);
      setConversations(prev => token ? [...prev, ...data.conversations] : data.conversations);
      setNextToken(data.nextToken);
    } catch (err) {
      setError('Failed to load conversations');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = async (e: React.MouseEvent, conversation: Conversation) => {
    e.stopPropagation();
    try {
      const newMode = conversation.reply_mode === 'manual' ? 'auto' : 'manual';
      await api.updateConversationMode(conversation.conversation_id, newMode);
      setConversations(prev =>
        prev.map(c =>
          c.conversation_id === conversation.conversation_id
            ? { ...c, reply_mode: newMode }
            : c
        )
      );
    } catch (err) {
      console.error('Failed to update mode:', err);
    }
  };

  const getPhaseColor = (phase: string) => {
    const colors: Record<string, string> = {
      understanding: 'bg-blue-100 text-blue-800',
      proposal_draft: 'bg-purple-100 text-purple-800',
      proposal_feedback: 'bg-yellow-100 text-yellow-800',
      documentation: 'bg-indigo-100 text-indigo-800',
      awaiting_approval: 'bg-orange-100 text-orange-800',
      approved: 'bg-green-100 text-green-800',
      archived: 'bg-gray-100 text-gray-800',
    };
    return colors[phase] || 'bg-gray-100 text-gray-800';
  };

  if (loading && conversations.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading conversations...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500">{error}</div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden bg-white shadow sm:rounded-lg">
      <div className="px-4 py-5 sm:px-6">
        <h3 className="text-lg font-medium leading-6 text-gray-900">Conversations</h3>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">
          Click on a conversation to view details and manage replies
        </p>
      </div>
      <div className="border-t border-gray-200">
        <ul className="divide-y divide-gray-200">
          {conversations.map((conversation) => (
            <li
              key={conversation.conversation_id}
              className="px-4 py-4 hover:bg-gray-50 cursor-pointer"
              onClick={() => onSelectConversation(conversation)}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {conversation.subject || 'No subject'}
                    </p>
                    <div className="ml-2 flex flex-shrink-0">
                      <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${getPhaseColor(conversation.phase)}`}>
                        {conversation.phase.replace('_', ' ')}
                      </span>
                    </div>
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <div className="flex items-center text-sm text-gray-500">
                      <p>{conversation.client_name || conversation.client_email}</p>
                      {conversation.project_name && (
                        <>
                          <span className="mx-2">•</span>
                          <p className="text-gray-700">{conversation.project_name}</p>
                        </>
                      )}
                      <span className="mx-2">•</span>
                      <p>{format(new Date(conversation.updated_at), 'MMM d, h:mm a')}</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      {conversation.pending_replies > 0 && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                          {conversation.pending_replies} pending
                        </span>
                      )}
                      <button
                        onClick={(e) => toggleMode(e, conversation)}
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          conversation.reply_mode === 'manual'
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-green-100 text-green-800'
                        }`}
                      >
                        {conversation.reply_mode}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
        {nextToken && (
          <div className="px-4 py-3 bg-gray-50 text-right sm:px-6">
            <button
              onClick={() => loadConversations(nextToken)}
              disabled={loading}
              className="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              Load More
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ConversationList;
