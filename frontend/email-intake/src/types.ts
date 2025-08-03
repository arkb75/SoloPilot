export interface Conversation {
  conversation_id: string;
  subject: string;
  client_email: string;
  phase: ConversationPhase;
  reply_mode: 'manual' | 'auto';
  created_at: string;
  updated_at: string;
  pending_replies: number;
  email_count?: number;
  participants?: string[];
  email_history?: Email[];
  pending_replies_list?: PendingReply[];
  attachments?: Attachment[];
  // Extracted metadata fields
  client_name?: string;
  project_name?: string;
  project_type?: string;
  latest_metadata?: ExtractedMetadata;
  metadata_updated_at?: string;
}

export interface ExtractedMetadata {
  client_name?: string;
  client_first_name?: string;
  project_name?: string;
  project_type?: string;
  current_phase?: string;
  should_attach_pdf?: boolean;
  meeting_requested?: boolean;
  revision_requested?: boolean;
  feedback_sentiment?: string;
  key_topics?: string[];
  action_required?: string;
  confidence_score?: number;
  extraction_notes?: string;
  timestamp?: string;
}

export type ConversationPhase =
  | 'understanding'
  | 'proposal_draft'
  | 'proposal_feedback'
  | 'documentation'
  | 'awaiting_approval'
  | 'approved'
  | 'archived';

export interface Email {
  email_id: string;
  message_id: string;
  from: string;
  to: string[];
  subject: string;
  body: string;
  timestamp: string;
  direction: 'inbound' | 'outbound';
  attachments?: string[];
}

export interface PendingReply {
  reply_id: string;
  generated_at: string;
  llm_prompt: string;
  llm_response: string;
  status: 'pending' | 'approved' | 'rejected' | 'amended';
  amended_content?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  sent_at?: string;
  message_id?: string;
  phase: ConversationPhase;
  metadata?: Record<string, any>;
}

export interface Attachment {
  attachment_id: string;
  type: string;
  filename: string;
  size: number;
  created_at: string;
  direction: 'inbound' | 'outbound';
  url?: string;
}
