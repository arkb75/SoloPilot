"""
Metadata Extractor

This module uses Claude Haiku to extract structured metadata from conversations.
The metadata is used by the conversational responder to generate natural emails.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def _clean_json_response(text: Optional[str]) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()

# Try to use the AI provider framework, fallback to Bedrock if not available
try:
    from src.providers import get_provider
    USE_AI_PROVIDER = True
except ImportError:
    USE_AI_PROVIDER = False
    logger.warning("AI provider framework not available, using Bedrock directly")
    
# Use Bedrock in Lambda environment
if not USE_AI_PROVIDER:
    import boto3
    bedrock_client = boto3.client(
        "bedrock-runtime", 
        region_name=os.environ.get("AWS_REGION", "us-east-2")
    )


class MetadataExtractor:
    """Extracts structured metadata from conversations using Claude Haiku."""
    
    def __init__(self):
        """Initialize the metadata extractor with Claude Haiku model."""
        # Use Haiku for fast extraction
        self.model = os.environ.get(
            "BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0"
        )  # Bedrock model ID
        self.inference_profile_arn = (
            os.environ.get("BEDROCK_IP_ARN")
            or os.environ.get("VISION_INFERENCE_PROFILE_ARN")
        )
        self.anthropic_model = "claude-3-haiku-20240307"  # For AI provider
        
        if USE_AI_PROVIDER:
            self.provider = get_provider(os.environ.get("AI_PROVIDER", "bedrock"))
        
    def extract_metadata(self, conversation: Dict[str, Any], current_phase: str) -> Dict[str, Any]:
        """
        Extract structured metadata from a conversation.
        
        Args:
            conversation: Full conversation data including email history
            current_phase: Current conversation phase (understanding, proposal_draft, etc.)
            
        Returns:
            Dict containing extracted metadata with confidence scores
        """
        try:
            # Get existing metadata to preserve persistent fields
            existing_metadata = conversation.get("latest_metadata", {})
            
            # Build the extraction prompt
            prompt = self._build_extraction_prompt(conversation, current_phase, existing_metadata)
            
            # Call Haiku for extraction
            response = self._call_haiku(prompt)
            
            # Parse and validate the response
            metadata = json.loads(_clean_json_response(response))
            validated_metadata = self._validate_metadata(metadata, current_phase, existing_metadata)
            
            # Log successful extraction
            logger.info(f"Successfully extracted metadata with confidence: {validated_metadata.get('confidence_score', 0)}")
            
            return validated_metadata
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse metadata JSON: {str(e)}")
            logger.error(f"Raw response: {response[:500]}...")
            return self._get_default_metadata(current_phase)
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {str(e)}")
            return self._get_default_metadata(current_phase)
    
    def _build_extraction_prompt(self, conversation: Dict[str, Any], current_phase: str, existing_metadata: Dict[str, Any]) -> str:
        """Build reasoning-based prompt for metadata extraction."""
        # Get only the latest 2 emails (latest inbound and latest outbound if available)
        email_history = conversation.get("email_history", [])
        recent_emails = email_history[-2:] if len(email_history) > 1 else email_history
        
        # Format only recent emails
        conversation_text = self._format_recent_emails(recent_emails)
        
        # Get the latest email for detailed analysis
        latest_email = email_history[-1] if email_history else {}
        
        # Check if PDF was already sent in conversation
        pdf_already_sent = self._check_if_pdf_was_sent(conversation)
        
        # Format existing metadata for context
        existing_client_name = existing_metadata.get("client_name")
        existing_project_name = existing_metadata.get("project_name")
        
        prompt = f"""You are analyzing an email conversation to extract metadata for automated response handling.

<context>
Current conversation phase: {current_phase}
Previous client name (if known): {existing_client_name or 'Not identified'}
Previous project name (if known): {existing_project_name or 'Not defined'}
PDF proposal already sent: {pdf_already_sent}
</context>

<latest_email>
From: {latest_email.get('from', 'Unknown')}
Subject: {latest_email.get('subject', 'No subject')}
Body: {latest_email.get('body', 'No body')}
</latest_email>

<recent_conversation>
{conversation_text}
</recent_conversation>

<task>
Analyze this email using logical reasoning to determine appropriate metadata values.

REASONING APPROACH:
1. First understand the client's intent - what are they trying to achieve?
2. Consider the conversation context - where are we in the sales process?
3. Determine what action a human freelancer would take next
4. Map those insights to the metadata fields

FIELD DEFINITIONS:
- client_name: The person's actual name (not email address). Only update if found with high confidence, otherwise keep existing.
- project_name: Descriptive name for what's being built. Keep existing unless client explicitly provides a new one.
- should_send_pdf: Should we attach a PDF proposal document to our response?
  * First check: Has a PDF already been sent? (see context above: "PDF proposal already sent")
  * If PDF was already sent: ONLY set to true if client is explicitly requesting it again or asking for changes
  * If PDF was NOT sent yet: Consider if client is ready for a formal proposal
  * Consider phrases like: "send proposal", "what's the cost", "I meant the pdf", "just send me something", "give me a quote", "pricing details", etc.
  * Also true if: We're in proposal_draft phase and haven't sent one yet, OR client is asking for revisions to existing proposal
  * IMPORTANT: Set to FALSE if we've already sent a PDF proposal and client is just asking questions or discussing without requesting changes
- proposal_explicitly_requested: Did client directly ask for a proposal/quote using clear language?
- meeting_requested: Is client asking to schedule a call/meeting IN THIS SPECIFIC EMAIL (not in conversation history)?
  * Look for actual scheduling intent, not just mentions of future communication
- revision_requested: Is client asking for changes to an existing proposal they've seen?
- feedback_sentiment: What's the emotional tone - positive, negative, neutral, or needs_revision?
- action_required: What's the most logical next step based on client's message?
  * Options: send_proposal, answer_question, revise_proposal, schedule_meeting, close_conversation

CRITICAL REASONING POINTS:
- If client references "the pdf" or "the proposal" they likely want the PDF document (should_send_pdf = true)
- If client seems confused about next steps and we're in proposal phase, they probably need the proposal
- IMPORTANT: If we're in proposal_feedback phase and client is just asking questions or discussing WITHOUT requesting changes, DO NOT resend the PDF
- Don't be overly rigid - understand intent, not just exact words
- Consider what would be most helpful to the client at this moment
- Avoid sending duplicate PDFs unless explicitly requested or changes are needed

Output a JSON object with your reasoning-based analysis:
{{
  "client_name": string or null,
  "client_first_name": string or null,
  "project_name": string,
  "project_type": "website|web_app|dashboard|api|mobile_app|other",
  "current_phase": "{current_phase}",
  "should_send_pdf": boolean,
  "proposal_explicitly_requested": boolean,
  "meeting_requested": boolean,
  "meeting_confidence": 0.0-1.0,
  "revision_requested": boolean,
  "feedback_sentiment": "positive|negative|neutral|needs_revision",
  "key_topics": ["main", "topics", "from", "email"],
  "action_required": "send_proposal|answer_question|revise_proposal|schedule_meeting|close_conversation",
  "confidence_score": 0.0-1.0,
  "extraction_notes": "Brief explanation of reasoning for key decisions, especially should_send_pdf"
}}

Think through the client's needs step by step, then provide ONLY the JSON object:
"""
        
        return prompt
    
    def _check_if_pdf_was_sent(self, conversation: Dict[str, Any]) -> bool:
        """Check if a PDF proposal has already been sent in this conversation."""
        # Check email history for PDF attachments or PDF sending indicators
        email_history = conversation.get("email_history", [])
        for email in email_history:
            if email.get("direction") == "outbound":
                # Check metadata for PDF indicators
                metadata = email.get("metadata", {})
                if metadata.get("has_pdf_attachment") or metadata.get("should_send_pdf"):
                    return True
                # Check if email body mentions attached proposal
                body = email.get("body", "").lower()
                if "attached" in body and ("proposal" in body or "pdf" in body):
                    return True
        
        # Check pending replies that were approved
        pending_replies = conversation.get("pending_replies", [])
        for reply in pending_replies:
            if reply.get("status") == "approved" and reply.get("metadata", {}).get("should_send_pdf"):
                return True
        
        return False
    
    def _format_recent_emails(self, recent_emails: List[Dict[str, Any]]) -> str:
        """Format only recent emails into readable text."""
        formatted = []
        
        for email in recent_emails:
            direction = "Client" if email.get("direction") == "inbound" else "Assistant"
            body_preview = email.get('body', '')[:300]  # Shorter preview for recent context
            formatted.append(f"{direction}: {body_preview}...")
            
        return "\n---\n".join(formatted) if formatted else "No recent emails"
    
    def _format_conversation_history(self, conversation: Dict[str, Any]) -> str:
        """Format email history into readable text."""
        email_history = conversation.get("email_history", [])
        formatted = []
        
        for email in email_history:
            direction = "Client" if email.get("direction") == "inbound" else "Assistant"
            formatted.append(f"{direction}: {email.get('body', '')[:500]}...")
            
        return "\n---\n".join(formatted) if formatted else "No conversation history"
    
    def _invoke_bedrock(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.dumps(request_body)
        if self.inference_profile_arn:
            response = bedrock_client.invoke_model(
                modelId=self.inference_profile_arn, body=payload, contentType="application/json"
            )
            return json.loads(response["body"].read())
        response = bedrock_client.invoke_model(
            modelId=self.model, body=payload, contentType="application/json"
        )
        return json.loads(response["body"].read())

    def _call_haiku(self, prompt: str) -> str:
        """Call Claude Haiku model for extraction."""
        try:
            if USE_AI_PROVIDER:
                # Use the AI provider framework
                response = self.provider.generate_code(prompt, [])
                return response
            else:
                # Use Bedrock directly in Lambda
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,  # Low temperature for consistent extraction
                }
                response_body = self._invoke_bedrock(request_body)
                return response_body["content"][0]["text"].strip()
                
        except Exception as e:
            logger.error(f"Error calling Haiku model: {str(e)}")
            raise
    
    def _validate_metadata(self, metadata: Dict[str, Any], current_phase: str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean extracted metadata, preserving persistent fields."""
        # Start with extracted metadata
        validated = {
            "client_name": metadata.get("client_name"),
            "client_first_name": metadata.get("client_first_name"),
            "project_name": metadata.get("project_name", "Your Project"),
            "project_type": metadata.get("project_type", "web_app"),
            "current_phase": current_phase,  # Use provided phase, not extracted
            "should_send_pdf": metadata.get("should_send_pdf", False),
            "proposal_explicitly_requested": metadata.get("proposal_explicitly_requested", False),
            "meeting_requested": metadata.get("meeting_requested", False),
            "meeting_confidence": metadata.get("meeting_confidence", 0.5),
            "revision_requested": metadata.get("revision_requested", False),
            "feedback_sentiment": metadata.get("feedback_sentiment", "neutral"),
            "key_topics": metadata.get("key_topics", []),
            "action_required": metadata.get("action_required", "send_proposal"),
            "confidence_score": metadata.get("confidence_score", 0.5),
            "extraction_notes": metadata.get("extraction_notes", ""),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Preserve persistent fields if not confidently updated
        if existing_metadata:
            # Client name: only update if new extraction has high confidence
            existing_client = existing_metadata.get("client_name")
            if existing_client and (not validated["client_name"] or 
                                  validated["confidence_score"] < 0.8):
                validated["client_name"] = existing_client
                validated["client_first_name"] = existing_metadata.get("client_first_name")
                
            # Project name: preserve unless explicitly changed
            existing_project = existing_metadata.get("project_name")
            if existing_project and existing_project != "Your Project":
                if not validated["project_name"] or validated["project_name"] == "Your Project":
                    validated["project_name"] = existing_project
        
        # Apply consistency checks and business logic
        # 1. If proposal is explicitly requested, PDF should be sent
        if validated["proposal_explicitly_requested"] and not validated["should_send_pdf"]:
            logger.info("Consistency fix: proposal_explicitly_requested=True, setting should_send_pdf=True")
            validated["should_send_pdf"] = True
            validated["extraction_notes"] += " [Auto-corrected: explicit proposal request requires PDF]"
        
        # 2. If revision requested in proposal_feedback phase, send updated PDF
        if current_phase == "proposal_feedback" and validated["revision_requested"]:
            if not validated["should_send_pdf"]:
                logger.info("Consistency fix: revision requested in proposal_feedback, setting should_send_pdf=True")
                validated["should_send_pdf"] = True
                validated["extraction_notes"] += " [Auto-corrected: revision request requires updated PDF]"
        
        # 3. Validate action_required aligns with other fields
        if validated["should_send_pdf"] and validated["action_required"] not in ["send_proposal", "revise_proposal"]:
            logger.info(f"Consistency fix: should_send_pdf=True but action was {validated['action_required']}, setting to send_proposal")
            validated["action_required"] = "send_proposal"
            validated["extraction_notes"] += " [Auto-corrected: action aligned with PDF sending]"
        
        # 4. If meeting requested with high confidence, action should reflect it
        if validated["meeting_requested"] and validated["meeting_confidence"] >= 0.7:
            if validated["action_required"] != "schedule_meeting":
                logger.info("Consistency fix: high-confidence meeting request, setting action to schedule_meeting")
                validated["action_required"] = "schedule_meeting"
        
        # 5. Log reasoning-based decisions for monitoring
        if validated["should_send_pdf"]:
            logger.info(f"PDF will be sent - Reasoning: {validated.get('extraction_notes', 'No notes')}")
            
        # Clean client names
        if validated["client_name"]:
            # Remove common false positives
            false_positives = ["must-haves", "requirements", "nice-to-haves", "notes", "additional"]
            if validated["client_name"].lower() in false_positives:
                validated["client_name"] = None
                validated["client_first_name"] = None
                validated["confidence_score"] *= 0.7  # Reduce confidence
                
        # Default first name if we have full name but no first name
        if validated["client_name"] and not validated["client_first_name"]:
            validated["client_first_name"] = validated["client_name"].split()[0]
            
        return validated
    
    def _get_default_metadata(self, current_phase: str) -> Dict[str, Any]:
        """Return default metadata when extraction fails."""
        logger.warning("Using default metadata due to extraction failure")
        
        return {
            "client_name": None,
            "client_first_name": "there",  # Generic greeting
            "project_name": "your project",
            "project_type": "web_app",
            "current_phase": current_phase,
            "should_send_pdf": False,  # Default to False - only True when explicitly requested
            "proposal_explicitly_requested": False,
            "meeting_requested": False,
            "meeting_confidence": 0.0,
            "revision_requested": False,
            "feedback_sentiment": "neutral",
            "key_topics": [],
            "action_required": "send_proposal" if current_phase == "proposal_draft" else "answer_question",
            "confidence_score": 0.0,
            "extraction_notes": "Failed to extract metadata, using defaults",
            "timestamp": datetime.utcnow().isoformat()
        }
