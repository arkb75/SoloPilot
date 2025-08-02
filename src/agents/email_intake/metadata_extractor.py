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

# Try to use the AI provider framework, fallback to direct Claude if not available
try:
    USE_AI_PROVIDER = os.environ.get("USE_AI_PROVIDER", "true").lower() == "true"
    if USE_AI_PROVIDER:
        from src.providers import get_ai_provider
        ai_provider = get_ai_provider()
except ImportError:
    USE_AI_PROVIDER = False
    logger.warning("AI provider framework not available, using direct Claude client")

# Direct Claude client as fallback
if not USE_AI_PROVIDER:
    try:
        import anthropic
        claude_client = anthropic.Anthropic(api_key=os.environ.get("CLAUDE_API_KEY"))
    except ImportError:
        logger.error("Neither AI provider framework nor anthropic library available")
        claude_client = None


class MetadataExtractor:
    """Extracts structured metadata from conversations using Claude Haiku."""
    
    def __init__(self):
        """Initialize the metadata extractor with Claude Haiku model."""
        self.model = "claude-3-haiku-20240307"  # Fast, efficient model for structured extraction
        
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
            # Build the extraction prompt
            prompt = self._build_extraction_prompt(conversation, current_phase)
            
            # Call Haiku for extraction
            response = self._call_haiku(prompt)
            
            # Parse and validate the response
            metadata = json.loads(response)
            validated_metadata = self._validate_metadata(metadata, current_phase)
            
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
    
    def _build_extraction_prompt(self, conversation: Dict[str, Any], current_phase: str) -> str:
        """Build the prompt for metadata extraction."""
        # Format conversation history
        conversation_text = self._format_conversation_history(conversation)
        
        # Get the latest email for detailed analysis
        email_history = conversation.get("email_history", [])
        latest_email = email_history[-1] if email_history else {}
        
        prompt = f"""Analyze this email conversation and extract metadata.

Current conversation phase: {current_phase}

Conversation history:
{conversation_text}

Latest email:
From: {latest_email.get('from', 'Unknown')}
Subject: {latest_email.get('subject', 'No subject')}
Body: {latest_email.get('body', 'No body')}

Extract the following information into a JSON object:

{{
  "client_name": "Full name extracted from email signature (null if not found)",
  "client_first_name": "First name only (null if not found)",
  "project_name": "Descriptive name for the project based on discussion",
  "project_type": "One of: website, web_app, dashboard, api, mobile_app, other",
  "current_phase": "{current_phase}",
  "should_attach_pdf": boolean (true for proposal_draft or revision requests),
  "meeting_requested": boolean (true if client asked for a call/meeting),
  "revision_requested": boolean (true if client is asking for changes to proposal),
  "feedback_sentiment": "One of: positive, negative, neutral, needs_revision",
  "key_topics": ["array", "of", "main", "topics"],
  "action_required": "One of: send_proposal, answer_question, revise_proposal, schedule_meeting, close_conversation",
  "confidence_score": 0.0 to 1.0 (your confidence in the extraction accuracy),
  "extraction_notes": "Any relevant notes about the extraction"
}}

IMPORTANT RULES:
1. For client_name: Extract from email signature, NOT from section headers like "Must-haves", "Requirements", "Nice-to-haves"
2. Look for names typically found in signatures (at the end of emails, after greetings)
3. For project_name: Create a descriptive name based on what they're building
4. For should_attach_pdf: Set to true ONLY for proposal_draft phase or when revising a proposal
5. For meeting_requested: Look for phrases like "can we meet", "schedule a call", "book a time"
6. For revision_requested: Look for budget concerns, feature changes, timeline adjustments
7. Set confidence_score based on how clear the information is

Return ONLY the JSON object, no other text."""
        
        return prompt
    
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
                response = ai_provider.generate_code(
                    prompt=prompt,
                    model_override=self.model,
                    temperature=0.1,  # Low temperature for consistent extraction
                    max_tokens=1000
                )
                return response
            else:
                # Fallback to direct Claude client
                if not claude_client:
                    raise Exception("No Claude client available")
                    
                response = claude_client.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
                
        except Exception as e:
            logger.error(f"Error calling Haiku model: {str(e)}")
            raise
    
    def _validate_metadata(self, metadata: Dict[str, Any], current_phase: str) -> Dict[str, Any]:
        """Validate and clean extracted metadata."""
        # Ensure all required fields exist
        validated = {
            "client_name": metadata.get("client_name"),
            "client_first_name": metadata.get("client_first_name"),
            "project_name": metadata.get("project_name", "Your Project"),
            "project_type": metadata.get("project_type", "web_app"),
            "current_phase": current_phase,  # Use provided phase, not extracted
            "should_attach_pdf": metadata.get("should_attach_pdf", False),
            "meeting_requested": metadata.get("meeting_requested", False),
            "revision_requested": metadata.get("revision_requested", False),
            "feedback_sentiment": metadata.get("feedback_sentiment", "neutral"),
            "key_topics": metadata.get("key_topics", []),
            "action_required": metadata.get("action_required", "send_proposal"),
            "confidence_score": metadata.get("confidence_score", 0.5),
            "extraction_notes": metadata.get("extraction_notes", ""),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Phase-specific validation
        if current_phase == "proposal_draft":
            validated["should_attach_pdf"] = True
            validated["action_required"] = "send_proposal"
        elif current_phase == "proposal_feedback" and validated["revision_requested"]:
            validated["should_attach_pdf"] = True
            validated["action_required"] = "revise_proposal"
            
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
            "should_attach_pdf": current_phase == "proposal_draft",
            "meeting_requested": False,
            "revision_requested": False,
            "feedback_sentiment": "neutral",
            "key_topics": [],
            "action_required": "send_proposal" if current_phase == "proposal_draft" else "answer_question",
            "confidence_score": 0.0,
            "extraction_notes": "Failed to extract metadata, using defaults",
            "timestamp": datetime.utcnow().isoformat()
        }