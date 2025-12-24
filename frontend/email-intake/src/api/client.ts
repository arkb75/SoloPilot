import axios from 'axios';
import { Conversation, PendingReply } from '../types';

const API_BASE_URL = (import.meta as any).env.VITE_API_URL || '/api';
const API_KEY = (import.meta as any).env.VITE_API_KEY || '';

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-Api-Key': API_KEY,
  },
});

// Add response interceptor for error handling
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle authentication error
      console.error('Authentication error');
    }
    return Promise.reject(error);
  }
);

export const api = {
  // Conversation endpoints
  listConversations: async (limit = 20, nextToken?: string) => {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (nextToken) params.append('nextToken', nextToken);

    const response = await client.get<{
      conversations: Conversation[];
      count: number;
      nextToken?: string;
    }>(`/conversations?${params}`);
    return response.data;
  },

  getConversation: async (id: string) => {
    const response = await client.get<Conversation>(`/conversations/${id}`);
    return response.data;
  },

  updateConversationMode: async (id: string, mode: 'manual' | 'auto') => {
    const response = await client.patch(`/conversations/${id}/mode`, { mode });
    return response.data;
  },

  deleteConversation: async (id: string) => {
    const response = await client.delete(`/conversations/${id}`);
    return response.data;
  },

  getPendingReplies: async (conversationId: string) => {
    const response = await client.get<{
      conversation_id: string;
      pending_replies: PendingReply[];
      count: number;
    }>(`/conversations/${conversationId}/pending-replies`);
    return response.data;
  },

  // Reply endpoints
  approveReply: async (replyId: string, conversationId: string, reviewedBy = 'admin') => {
    const response = await client.post(`/replies/${replyId}/approve`, {
      conversation_id: conversationId,
      reviewed_by: reviewedBy,
    });
    return response.data;
  },

  rejectReply: async (replyId: string, conversationId: string, reason: string, reviewedBy = 'admin') => {
    const response = await client.post(`/replies/${replyId}/reject`, {
      conversation_id: conversationId,
      reason,
      reviewed_by: reviewedBy,
    });
    return response.data;
  },

  amendReply: async (replyId: string, conversationId: string, content: string, amendedBy = 'admin') => {
    const response = await client.patch(`/replies/${replyId}`, {
      conversation_id: conversationId,
      content,
      amended_by: amendedBy,
    });
    return response.data;
  },

  getReplyPrompt: async (replyId: string) => {
    const response = await client.get<{
      reply_id: string;
      prompt: string;
    }>(`/replies/${replyId}/prompt`);
    return response.data;
  },

  getReplyReview: async (replyId: string) => {
    const response = await client.get<{
      reply_id: string;
      review: {
        relevance_score: number;
        completeness_score: number;
        accuracy_score: number;
        next_steps_score: number;
        overall_score: number;
        red_flags: string[];
        summary: string;
        reviewed_at: string;
      };
      cached: boolean;
    }>(`/replies/${replyId}/review`);
    return response.data;
  },

  requestRevision: async (replyId: string) => {
    const response = await client.post<{
      reply_id: string;
      revision: {
        revised_response: string;
        feedback_prompt: string;
        revision_prompt: string;
        revised_at: string;
        revision_successful: boolean;
        revised_review?: {
          relevance_score: number;
          completeness_score: number;
          accuracy_score: number;
          next_steps_score: number;
          overall_score: number;
          red_flags: string[];
          summary: string;
          reviewed_at: string;
        };
        revision_error?: string;
        revision_attempts?: number;
      };
      original_review: {
        relevance_score: number;
        completeness_score: number;
        accuracy_score: number;
        next_steps_score: number;
        overall_score: number;
        red_flags: string[];
        summary: string;
        reviewed_at: string;
      };
      cached: boolean;
    }>(`/replies/${replyId}/request-revision`);
    return response.data;
  },

  // Attachment endpoints
  getAttachmentUrl: async (attachmentId: string) => {
    const response = await client.get<{
      attachment_id: string;
      url: string;
      expires_in: number;
    }>(`/attachments/${attachmentId}`);
    return response.data;
  },

  // Proposal endpoints
  listProposals: async (conversationId: string) => {
    const response = await client.get<{
      conversation_id: string;
      proposals: Array<{
        version: number;
        created_at: string;
        file_size: number;
        budget?: string;
        has_revisions: boolean;
      }>;
      count: number;
    }>(`/conversations/${conversationId}/proposals`);
    return response.data;
  },

  getProposalUrl: async (conversationId: string, version: number) => {
    const response = await client.get<{
      conversation_id: string;
      version: number;
      url: string;
      expires_in: number;
      metadata?: any;
    }>(`/conversations/${conversationId}/proposals/${version}`);
    return response.data;
  },

  // Vision annotate endpoint (page screenshot based)
  annotateProposalVision: async (
    conversationId: string,
    baseVersion: number,
    payload: {
      pages: Array<{ pageIndex: number; imageBase64: string }>;
      annotations?: Array<{
        pageIndex: number;
        x: number; y: number; width: number; height: number;
        type: 'highlight' | 'note';
        color?: string; opacity?: number;
        comment?: string;
      }>;
      prompt?: string;
    }
  ) => {
    const response = await client.post<{
      success: boolean;
      conversation_id: string;
      base_version: number;
      new_version: number;
      applied_fields?: string[];
      vision_used: boolean;
      fallback_llm_used: boolean;
    }>(`/conversations/${conversationId}/proposals/${baseVersion}/annotate-vision`, payload);
    return response.data;
  },
};

export default api;
