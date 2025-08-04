"""Enhanced conversational response generator with unified response method."""

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from metadata_extractor import MetadataExtractor

try:
    from src.providers import get_provider
    from src.providers.base import log_call

    USE_AI_PROVIDER = True
except ImportError:
    # Running in Lambda environment
    import boto3

    USE_AI_PROVIDER = False

logger = logging.getLogger(__name__)

# Get AI provider from environment
AI_PROVIDER = os.environ.get("AI_PROVIDER", "bedrock")


def decimal_to_json_serializable(obj):
    """Convert Decimal objects to JSON-serializable types."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_json_serializable(item) for item in obj]
    return obj


class ConversationalResponder:
    """Generates unified conversational responses with Claude 4 Sonnet."""

    def __init__(self, sender_name="Abdul", calendly_link="[CALENDLY_LINK]"):
        """Initialize with AI provider or Bedrock client.

        Args:
            sender_name: Name to use in email signatures
            calendly_link: Calendly link for scheduling meetings
        """
        self.sender_name = sender_name
        self.calendly_link = calendly_link
        self.metadata_extractor = MetadataExtractor()

        if USE_AI_PROVIDER:
            self.provider = get_provider(AI_PROVIDER)
        else:
            # Lambda environment - use Bedrock directly
            self.bedrock_client = boto3.client(
                "bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-2")
            )
            self.model_id = os.environ.get(
                "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
            )

    def generate_response_with_tracking(
        self, conversation: Dict[str, Any], latest_email: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Generate unified response with metadata tracking.

        Args:
            conversation: Full conversation state
            latest_email: Latest email received

        Returns:
            Tuple of (response_text, metadata, llm_prompt)
        """
        # Extract metadata using Haiku
        current_phase = conversation.get("phase", "understanding")
        metadata = self.metadata_extractor.extract_metadata(conversation, current_phase)
        logger.info(f"Extracted metadata: {json.dumps(metadata, default=str)}")
        
        # Generate unified response
        response_body, response_metadata, prompt = self._generate_unified_response(
            conversation, latest_email, metadata
        )
        
        # Build final email with greeting and signature
        final_email = self._build_final_email(response_body, metadata, conversation)
        
        # Add the extracted metadata to response metadata
        response_metadata["extracted_metadata"] = metadata
        
        return final_email, response_metadata, prompt

    def _generate_unified_response(
        self, conversation: Dict[str, Any], latest_email: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Generate response using unified approach with full context."""
        
        # Build comprehensive prompt
        prompt = self._build_unified_prompt(conversation, latest_email, metadata)
        
        # Generate response body only
        response_body = self._call_llm(prompt)
        
        # Determine what action the AI took based on response
        response_metadata = self._analyze_response_action(
            response_body, conversation, metadata
        )
        
        return response_body, response_metadata, prompt

    def _build_unified_prompt(
        self, conversation: Dict[str, Any], latest_email: Dict[str, Any], metadata: Dict[str, Any]
    ) -> str:
        """Build comprehensive prompt with all context."""
        
        # Get conversation details
        email_history = conversation.get("email_history", [])
        requirements = conversation.get("requirements", {})
        current_phase = conversation.get("phase", "understanding")
        
        # Determine client name
        client_name = self._get_client_name(metadata, conversation)
        if client_name and client_name != "Client":
            client_context = f"helping {client_name}"
        else:
            client_context = "helping a potential client"
        
        # Build conversation history
        history_text = self._build_conversation_history(email_history[-5:])  # Last 5 emails
        
        # Determine conversation stage and capabilities
        stage_info = self._determine_stage_info(conversation, metadata)
        
        prompt = f"""You are {self.sender_name}, a freelance developer {client_context}.

CONVERSATION CONTEXT:
- Project: {metadata.get('project_name', 'Not yet defined')}
- Project Type: {metadata.get('project_type', 'Not specified')}
- Current Phase: {current_phase}
- Emails Exchanged: {len(email_history)}
- Client Sentiment: {metadata.get('feedback_sentiment', 'neutral')}

REQUIREMENTS GATHERED:
- Title: {requirements.get('title', 'Not clear yet')}
- Features: {len(requirements.get('features', []))} identified
- Budget: ${requirements.get('budget_amount', 'Not mentioned')}
- Timeline: {requirements.get('timeline', 'Not specified')}

METADATA ANALYSIS:
- Meeting Requested: {metadata.get('meeting_requested', False)}
- Revision Requested: {metadata.get('revision_requested', False)}
- Action Required: {metadata.get('action_required', 'respond')}
- Key Topics: {', '.join(metadata.get('key_topics', []))}

CONVERSATION HISTORY:
{history_text}

LATEST EMAIL FROM CLIENT:
{latest_email.get('body', '')}

{stage_info}

RESPONSE GUIDELINES:
1. Generate ONLY the email body - no greeting, no signature
2. Be concise and natural (2-3 paragraphs max)
3. Focus on the client's specific questions/concerns
4. Don't repeat information already discussed
5. If proposing, mention that details are in the attached PDF
6. If they want a meeting, acknowledge it (system will add Calendly)

What is the most appropriate response to this email?"""
        
        return prompt

    def _determine_stage_info(self, conversation: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """Determine stage-specific instructions based on conversation state."""
        
        current_phase = conversation.get("phase", "understanding")
        requirements = conversation.get("requirements", {})
        has_requirements = bool(requirements.get("features")) and bool(requirements.get("title"))
        
        # Check if proposal was already sent
        proposal_sent = any(
            email.get("metadata", {}).get("should_send_pdf", False)
            for email in conversation.get("email_history", [])
            if email.get("direction") == "outbound"
        )
        
        if current_phase == "understanding" and not proposal_sent:
            return f"""
YOUR CURRENT CAPABILITIES:
- Ask clarifying questions about requirements
- Gather information about budget, timeline, technical needs
- Build rapport and understand their business
- If they explicitly ask for a proposal/pricing AND you have basic requirements: You can send a proposal
- If they seem impatient ("just send something", "figure it out"): You can send a proposal with caveats

CONSTRAINTS:
- Don't send a proposal unless: (a) they ask for it, OR (b) you have enough core requirements
- Don't suggest meetings unless they ask
- Focus on understanding their needs thoroughly"""
        
        elif proposal_sent:
            return f"""
YOUR CURRENT SITUATION:
- You have already sent a proposal (PDF attached in previous email)
- The client is now responding with feedback/questions

YOUR CAPABILITIES:
- Address specific concerns about the proposal
- Negotiate terms (budget, timeline, scope)
- Clarify any misunderstandings
- If they request changes: Acknowledge and mention revised proposal will be attached
- Answer questions about implementation details
- Schedule calls if requested

CONSTRAINTS:
- Don't resend the same proposal information
- Be responsive to their specific feedback
- If they ask about cost reduction, be flexible and suggest options"""
        
        else:
            return f"""
YOUR CAPABILITIES:
- Respond naturally to their message
- Answer any questions
- Provide clarifications
- Move the conversation forward

CONSTRAINTS:
- Be helpful and professional
- Focus on their specific needs"""

    def _build_conversation_history(self, recent_emails: List[Dict[str, Any]]) -> str:
        """Build formatted conversation history from recent emails."""
        history = []
        for email in recent_emails:
            direction = "Client" if email.get("direction") == "inbound" else "You"
            timestamp = email.get("timestamp", "")
            body = email.get("body", "")[:500]  # Truncate long emails
            history.append(f"[{direction} - {timestamp[:10]}]\n{body}\n")
        
        return "\n---\n".join(history) if history else "No previous conversation"

    def _get_client_name(self, metadata: Dict[str, Any], conversation: Dict[str, Any]) -> Optional[str]:
        """Get client name from metadata or conversation."""
        # First check metadata with confidence
        extracted_name = metadata.get("client_name")
        confidence = metadata.get("confidence_score", 0.5)
        
        if extracted_name and extracted_name != "Client" and confidence >= 0.7:
            return extracted_name
            
        # Then check stored name
        stored_name = conversation.get("client_name")
        if stored_name and stored_name != "Client":
            return stored_name
            
        return None

    def _build_final_email(
        self, response_body: str, metadata: Dict[str, Any], conversation: Dict[str, Any]
    ) -> str:
        """Build final email with greeting, body, and signature."""
        
        # Determine greeting
        client_name = self._get_client_name(metadata, conversation)
        if client_name:
            greeting = f"Hi {client_name.split()[0]},"
        else:
            greeting = "Hi there,"
        
        # Build email
        email_parts = [greeting, "", response_body.strip(), "", f"Best,\n{self.sender_name}"]
        
        # Add Calendly if meeting requested
        if metadata.get("meeting_requested", False) and self.calendly_link:
            email_parts.append(f"\nP.S. You can book a time at: {self.calendly_link}")
        
        return "\n".join(email_parts)

    def _analyze_response_action(
        self, response_body: str, conversation: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze what action the AI took in its response."""
        
        response_lower = response_body.lower()
        current_phase = conversation.get("phase", "understanding")
        
        # Detect if proposal was mentioned
        proposal_mentioned = any(word in response_lower for word in [
            "proposal", "attached", "pdf", "document", "quote"
        ])
        
        # Detect if revision was acknowledged
        revision_acknowledged = any(word in response_lower for word in [
            "revised", "updated", "changes", "adjustments"
        ])
        
        # Build metadata
        response_metadata = {
            "phase": current_phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_taken": "response_sent",
            "should_send_pdf": False,
        }
        
        # Determine if we should send a PDF
        if proposal_mentioned and "attached" in response_lower:
            if metadata.get("revision_requested", False) or revision_acknowledged:
                # Sending revised proposal
                response_metadata["should_send_pdf"] = True
                response_metadata["action_taken"] = "revised_proposal_sent"
                response_metadata["proposal_version"] = conversation.get("proposal_version", 1) + 1
            elif current_phase == "understanding":
                # Sending initial proposal
                response_metadata["should_send_pdf"] = True
                response_metadata["action_taken"] = "initial_proposal_sent"
                response_metadata["proposal_version"] = 1
                response_metadata["suggested_phase"] = "proposal_draft"
        
        return response_metadata

    def _call_llm(self, prompt: str) -> str:
        """Call LLM with prompt."""
        try:
            if USE_AI_PROVIDER:
                # Use provider
                response = self.provider.generate_code(prompt, [])
                return response.strip()
            else:
                # Call Bedrock directly
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                }

                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id, body=json.dumps(request_body)
                )

                response_body = json.loads(response["body"].read())
                content = response_body["content"][0]["text"]
                return content.strip()

        except Exception as e:
            logger.error(f"Error calling LLM: {str(e)}", exc_info=True)
            raise

    # Backward compatibility method
    def generate_response(
        self, conversation: Dict[str, Any], latest_email: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate response (backward compatibility)."""
        response_text, metadata, _ = self.generate_response_with_tracking(
            conversation, latest_email
        )
        return response_text, metadata