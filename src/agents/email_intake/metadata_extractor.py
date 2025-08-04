"""
Metadata Extractor

This module uses Claude Haiku to extract structured metadata from conversations.
The metadata is used by the conversational responder to generate natural emails.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

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
        self.model = "us.anthropic.claude-3-5-haiku-20241022-v1:0"  # Bedrock model ID
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
            metadata = json.loads(response)
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
        """Build the prompt for metadata extraction."""
        # Get only the latest 2 emails (latest inbound and latest outbound if available)
        email_history = conversation.get("email_history", [])
        recent_emails = email_history[-2:] if len(email_history) > 1 else email_history
        
        # Format only recent emails
        conversation_text = self._format_recent_emails(recent_emails)
        
        # Get the latest email for detailed analysis
        latest_email = email_history[-1] if email_history else {}
        
        # Format existing metadata for context
        existing_client_name = existing_metadata.get("client_name")
        existing_project_name = existing_metadata.get("project_name")
        
        prompt = f"""Analyze this email and extract metadata.

Current conversation phase: {current_phase}

Existing metadata (for persistent fields only):
- Client Name: {existing_client_name or 'Not yet identified'}
- Project Name: {existing_project_name or 'Not yet defined'}

Recent conversation context (last 2 emails only):
{conversation_text}

Latest email to analyze:
From: {latest_email.get('from', 'Unknown')}
Subject: {latest_email.get('subject', 'No subject')}
Body: {latest_email.get('body', 'No body')}

Extract the following information into a JSON object:

{{
  "client_name": "Full name from signature (use existing if not found with high confidence)",
  "client_first_name": "First name only (null if not found)",
  "project_name": "Descriptive name for project (use existing unless client provides new one)",
  "project_type": "One of: website, web_app, dashboard, api, mobile_app, other",
  "current_phase": "{current_phase}",
  "should_send_pdf": boolean (true when proposal should be sent),
  "proposal_explicitly_requested": boolean (true if client explicitly asked for proposal),
  "meeting_requested": boolean (true if client asked for a call/meeting IN THIS EMAIL),
  "meeting_confidence": 0.0 to 1.0 (confidence that this is a real meeting request),
  "revision_requested": boolean (true if client is asking for changes to proposal),
  "feedback_sentiment": "One of: positive, negative, neutral, needs_revision",
  "key_topics": ["array", "of", "main", "topics", "from", "this", "email"],
  "action_required": "One of: send_proposal, answer_question, revise_proposal, schedule_meeting, close_conversation",
  "confidence_score": 0.0 to 1.0 (your confidence in the extraction accuracy),
  "extraction_notes": "Any relevant notes about the extraction"
}}

IMPORTANT RULES:
1. For client_name: Only update if you find a name with >0.8 confidence, otherwise use existing
2. For project_name: Only update if client explicitly mentions a new project name
3. For should_send_pdf: Set to true when:
   - Client explicitly asks for proposal/quote ("send proposal", "give me a quote", "send pricing")
   - Client says "answer these yourself and give me a proposal"
   - Current phase is proposal_draft AND this is first proposal
   - revision_requested is true AND current phase is proposal_feedback
4. For proposal_explicitly_requested: ONLY true when client uses words like:
   - "send me a proposal"
   - "give me a quote"
   - "send the proposal"
   - "answer these yourself and give me a proposal"
   - "just send something"
5. For meeting_requested: ONLY analyze THIS EMAIL, not conversation history
   Set to true ONLY if BOTH conditions are met:
   a) Contains verbs like "schedule", "arrange", "meet", "call", "book"
   b) Contains explicit request like "book a call", "set up a meeting", "can we schedule"
   
   These are NOT meeting requests:
   - "Let me know next steps"
   - "What's the timeline?"
   - "How should we proceed?"
   - "Looking forward to hearing from you"
   
6. Reset per-email fields (don't carry forward from history):
   - meeting_requested
   - revision_requested
   - key_topics (only from this email)
   - action_required (based on this email)

Return ONLY the JSON object, no other text."""
        
        return prompt
    
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
                
                response = bedrock_client.invoke_model(
                    modelId=self.model,
                    body=json.dumps(request_body)
                )
                
                response_body = json.loads(response["body"].read())
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
        
        # Override should_send_pdf based on explicit request or phase logic
        if validated["proposal_explicitly_requested"]:
            validated["should_send_pdf"] = True
            logger.info("Proposal explicitly requested - setting should_send_pdf to True")
        elif current_phase == "proposal_draft" and not existing_metadata.get("proposal_sent"):
            # First proposal in proposal_draft phase
            validated["should_send_pdf"] = True
        elif current_phase == "proposal_feedback" and validated["revision_requested"]:
            validated["should_send_pdf"] = True
            
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
            "should_send_pdf": current_phase == "proposal_draft",
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