"""Enhanced conversational response generator with prompt tracking."""

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
    """Generates phase-appropriate conversational responses with prompt tracking."""

    def __init__(self, sender_name="Abdul", calendly_link="[CALENDLY_LINK]"):
        """Initialize with AI provider or Bedrock client.

        Args:
            sender_name: Name to use in email signatures
            calendly_link: Calendly link for scheduling meetings
        """
        self.sender_name = sender_name
        self.calendly_link = calendly_link

        if USE_AI_PROVIDER:
            self.provider = get_provider(AI_PROVIDER)
        else:
            # Lambda environment - use Bedrock directly
            self.bedrock_client = boto3.client(
                "bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-2")
            )
            self.model_id = os.environ.get(
                "BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            )

    def generate_response_with_tracking(
        self, conversation: Dict[str, Any], latest_email: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Generate phase-appropriate response with prompt tracking.

        Args:
            conversation: Full conversation state
            latest_email: Latest email received

        Returns:
            Tuple of (response_text, metadata, llm_prompt)
        """
        phase = conversation.get("phase", "understanding")
        email_body = latest_email.get("body", "").lower()

        # Check for user impatience or proposal request
        impatience_indicators = [
            "just give me",
            "no just",
            "you decide",
            "send me the proposal",
            "let's move forward",
            "sounds good",
            "that works",
            "let me know how we can call",
            "book a call",
            "schedule",
            "give me a proposal",
            "send proposal",
            "quote please",
        ]

        is_impatient = any(indicator in email_body for indicator in impatience_indicators)

        if is_impatient and phase == "understanding":
            logger.info("User impatience detected - jumping to proposal phase")
            # Override phase to jump to proposal
            phase = "proposal_draft"

        # Extract metadata using Haiku
        extractor = MetadataExtractor()
        extracted_metadata = extractor.extract_metadata(conversation, phase)
        logger.info(f"Extracted metadata: {json.dumps(extracted_metadata, default=str)}")

        # Build conversation context
        context = self._build_conversation_context(conversation)

        # Generate phase-appropriate response and capture prompt
        if phase == "understanding":
            response, metadata, prompt = self._generate_clarifying_response_tracked(context, latest_email, conversation, extracted_metadata)
        elif phase == "proposal_draft":
            response, metadata, prompt = self._generate_proposal_response_tracked(context, conversation, extracted_metadata)
        elif phase == "proposal_feedback":
            response, metadata, prompt = self._handle_proposal_feedback_tracked(context, latest_email, conversation, extracted_metadata)
        elif phase == "documentation":
            response, metadata, prompt = self._generate_documentation_response_tracked(context, conversation)
        elif phase == "awaiting_approval":
            response, metadata, prompt = self._handle_approval_response_tracked(context, latest_email)
        else:
            # Default conversational response
            response, metadata, prompt = self._generate_general_response_tracked(context, latest_email)
        
        # Add the extracted metadata to the response metadata
        metadata["extracted_metadata"] = extracted_metadata
        
        return response, metadata, prompt

    def generate_response(
        self, conversation: Dict[str, Any], latest_email: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate phase-appropriate response (backward compatibility).

        Args:
            conversation: Full conversation state
            latest_email: Latest email received

        Returns:
            Tuple of (response_text, metadata)
        """
        response_text, metadata, _ = self.generate_response_with_tracking(
            conversation, latest_email
        )
        return response_text, metadata

    def _generate_clarifying_response_tracked(
        self, context: str, latest_email: Dict[str, Any], conversation: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Generate response during understanding phase using extracted metadata."""
        # Use metadata for personalization
        client_first_name = metadata.get("client_first_name", "there")
        project_name = metadata.get("project_name", "your project")
        key_topics = metadata.get("key_topics", [])
        
        # Apply confidence threshold for meeting detection
        meeting_requested = metadata.get("meeting_requested", False)
        meeting_confidence = metadata.get("meeting_confidence", 0.5)
        
        # Only accept meeting request if confidence is high enough
        if meeting_requested and meeting_confidence < 0.8:
            logger.info(f"Meeting request detected but confidence too low ({meeting_confidence}), ignoring")
            meeting_requested = False
        
        # Get latest message
        email_body = latest_email.get('body', '')

        prompt = f"""You are {self.sender_name}, a freelance developer in conversation with {client_first_name}.

Latest message from {client_first_name}:
{email_body}

Project context: {project_name}
Key topics discussed: {', '.join(key_topics) if key_topics else 'Not yet clear'}

Write a natural response to understand their needs better.

Guidelines:
- Be conversational and friendly
- Acknowledge what they've shared
- Ask clarifying questions if needed
- Keep it concise (2-3 paragraphs max)
{f"- They want to schedule a meeting (Calendly link will be added automatically)" if meeting_requested else "- Do NOT suggest meetings or calls - the client hasn't asked for one"}

Write only the email body text.

CRITICAL INSTRUCTIONS:
- Do NOT add any signature (no "Best,", "Regards,", "Sincerely," etc.)
- Do NOT add your name at the end
- Do NOT add any P.S. lines
- End the email with your last sentence about the topic
- The signature and P.S. will be added automatically by the system

ENVIRONMENT AWARENESS:
- Meeting requested: {"YES - mention the call" if meeting_requested else "NO - do NOT suggest calls/meetings"}
- You can gather requirements via email without meetings
- Only suggest meetings if the client explicitly asked for one"""

        response = self._call_llm(prompt)
        
        # Add signature
        response = response.strip() + f"\n\nBest,\n{self.sender_name}"
        
        # Add Calendly if meeting requested
        if meeting_requested and self.calendly_link:
            response += f"\n\nP.S. You can book a time at: {self.calendly_link}"

        # Build metadata
        response_metadata = {
            "phase": "understanding",
            "client_name": metadata.get("client_name"),
            "client_first_name": client_first_name,
            "clarified_points": self._extract_clarified_points(response),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return response, response_metadata, prompt

    def _generate_proposal_response_tracked(
        self, context: str, conversation: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Generate proposal email using extracted metadata - no proposal content."""
        # Use metadata for personalization
        client_first_name = metadata.get("client_first_name", "there")
        project_name = metadata.get("project_name", "your project")
        
        # Apply confidence threshold for meeting detection
        meeting_requested = metadata.get("meeting_requested", False)
        meeting_confidence = metadata.get("meeting_confidence", 0.5)
        
        # Only accept meeting request if confidence is high enough
        if meeting_requested and meeting_confidence < 0.8:
            logger.info(f"Meeting request detected but confidence too low ({meeting_confidence}), ignoring")
            meeting_requested = False
        
        # Get requirements for additional context if needed
        requirements = conversation.get("requirements", {})
        
        prompt = f"""You are {self.sender_name}, a freelance developer writing to {client_first_name}.

Project: {project_name}
Meeting requested: {meeting_requested}

Write a brief, natural email informing them that their proposal is attached.

Guidelines:
- Be conversational and friendly
- 2-3 sentences maximum
- Mention the attached proposal naturally
- Don't include proposal details (they're in the PDF)
{f"- Meeting was requested (P.S. with Calendly will be added automatically)" if meeting_requested else "- Do NOT suggest meetings or calls - focus on the proposal"}

Write only the email body text. Be natural, not robotic.

CRITICAL INSTRUCTIONS:
- Do NOT add any signature (no "Best,", "Regards,", "Sincerely," etc.)
- Do NOT add your name at the end
- Do NOT add any P.S. lines
- End the email with your last sentence about the topic
- The signature and P.S. will be added automatically by the system

ENVIRONMENT AWARENESS:
- Meeting requested: {"YES" if meeting_requested else "NO - do not mention calls/meetings"}"""

        # Generate the email body
        email_body = self._call_llm(prompt)
        
        # Clean up the email body
        email_body = email_body.strip()
        
        # Add signature
        email_body += f"\n\nBest,\n{self.sender_name}"
        
        # Add Calendly link if requested
        if meeting_requested and self.calendly_link:
            email_body += f"\n\nP.S. You can book a time at: {self.calendly_link}"

        # Build metadata
        response_metadata = {
            "phase": "proposal_draft",
            "client_name": metadata.get("client_name"),
            "client_first_name": client_first_name,
            "proposal_version": 1,
            "should_send_pdf": True,  # Always true for proposal_draft
            "meeting_requested": meeting_requested,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Log metadata
        logger.info(f"[PROPOSAL_DRAFT] Generated email for {client_first_name}, project: {project_name}, PDF: True")

        return email_body, response_metadata, prompt

    def _handle_proposal_feedback_tracked(
        self, context: str, latest_email: Dict[str, Any], conversation: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Handle feedback on proposal using extracted metadata."""
        # Use metadata for personalization
        client_first_name = metadata.get("client_first_name", "there")
        project_name = metadata.get("project_name", "your project")
        revision_requested = metadata.get("revision_requested", False)
        feedback_sentiment = metadata.get("feedback_sentiment", "neutral")
        action_required = metadata.get("action_required", "answer_question")
        
        # Get the feedback
        feedback_body = latest_email.get("body", "")
        
        # If revision is requested, generate a revised proposal
        if revision_requested or action_required == "revise_proposal":
            logger.info(f"[PROPOSAL_FEEDBACK] Revision requested for {client_first_name}")
            
            # Simple prompt for revision acknowledgment
            prompt = f"""You are {self.sender_name} responding to {client_first_name}'s request for proposal changes.

Their feedback: {feedback_body}

Write a brief email acknowledging their feedback and mentioning the revised proposal is attached.

Guidelines:
- Be understanding and professional
- 2-3 sentences maximum
- Mention the attached revised proposal
- Don't repeat the changes in detail (they're in the PDF)

Write only the email body text.

CRITICAL INSTRUCTIONS:
- Do NOT add any signature (no "Best,", "Regards,", "Sincerely," etc.)
- Do NOT add your name at the end
- Do NOT add any P.S. lines
- End the email with your last sentence about the topic
- The signature and P.S. will be added automatically by the system"""

            email_body = self._call_llm(prompt)
            email_body = email_body.strip() + f"\n\nBest,\n{self.sender_name}"
            
            # Get current proposal version and increment
            current_version = conversation.get("proposal_version", 1)
            
            response_metadata = {
                "phase": "proposal_feedback",
                "client_name": metadata.get("client_name"),
                "client_first_name": client_first_name,
                "proposal_version": current_version + 1,
                "should_send_pdf": True,  # Generate revised PDF
                "feedback_sentiment": "revision_requested",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            logger.info(f"[PROPOSAL_FEEDBACK] Revision response - PDF: True, version: {current_version + 1}")
            
            return email_body, response_metadata, prompt
        
        # Regular feedback (no revision needed)
        prompt = f"""You are {self.sender_name} responding to {client_first_name}'s feedback.

Their feedback: {feedback_body}
Project: {project_name}
Sentiment: {feedback_sentiment}

Write a natural response based on their feedback.

Guidelines:
- Be conversational and helpful
- If they're ready to proceed, confirm next steps
- If they have questions, answer clearly
- If they want to meet: mention a call (Calendly link will be added automatically)
- Keep it concise

Write only the email body text.

CRITICAL INSTRUCTIONS:
- Do NOT add any signature (no "Best,", "Regards,", "Sincerely," etc.)
- Do NOT add your name at the end
- Do NOT add any P.S. lines
- End the email with your last sentence about the topic
- The signature and P.S. will be added automatically by the system"""

        email_body = self._call_llm(prompt)
        email_body = email_body.strip() + f"\n\nBest,\n{self.sender_name}"

        response_metadata = {
            "phase": "proposal_feedback",
            "client_name": metadata.get("client_name"),
            "client_first_name": client_first_name,
            "feedback_sentiment": feedback_sentiment,
            "should_send_pdf": False,  # No PDF for regular feedback
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        logger.info(f"[PROPOSAL_FEEDBACK] Regular feedback - PDF: False, sentiment: {feedback_sentiment}")

        return email_body, response_metadata, prompt

    def _generate_documentation_response_tracked(
        self, context: str, conversation: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Generate detailed project documentation with prompt tracking."""
        requirements = conversation.get("requirements", {})
        proposal = conversation.get("proposal", {})

        prompt = f"""You are {self.sender_name}, a professional freelancer creating detailed project documentation.
The client has approved the proposal. Now create comprehensive project documentation.

Conversation history:
{context}

Approved proposal:
{json.dumps(decimal_to_json_serializable(proposal), indent=2)}

Requirements:
{json.dumps(decimal_to_json_serializable(requirements), indent=2)}

RULES:
1. NO meeting speculation
2. Be concise but thorough
3. Do NOT add a signature - it will be added automatically

Create detailed documentation including:
1. Project Specification
   - Detailed requirements
   - Technical specifications
   - User stories/use cases
2. Development Plan
   - Phase breakdown
   - Milestones and deliverables
   - Timeline with dates
3. Technical Architecture
   - Technology stack
   - System design overview
   - Integration points
4. Success Criteria
   - Acceptance criteria
   - Testing approach
   - Launch checklist

End by asking for final approval to begin development.

Do NOT add a signature - it will be added automatically.

CRITICAL: Output ONLY the email text to send. Do NOT include any preamble, thinking, or explanation. Start directly with the greeting."""

        response = self._call_llm(prompt)

        metadata = {
            "phase": "documentation",
            "documentation_complete": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return response, metadata, prompt

    def _handle_approval_response_tracked(
        self, context: str, latest_email: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Handle final approval response with prompt tracking."""
        calendly_link = self.calendly_link
        prompt = f"""You are {self.sender_name}, a professional freelancer responding to client's decision on the project documentation.

Conversation history:
{context}

Client's response:
{latest_email.get('body', '')}

If approved:
- Thank them for their trust
- Confirm project kickoff
- Outline immediate next steps
- Provide contact/communication expectations

If not approved or needs changes:
- Acknowledge their feedback
- Offer to revise if needed
- Keep door open for future

Keep it professional and positive.

Do NOT add a signature - it will be added automatically.

CRITICAL: Output ONLY the email text to send. Do NOT include any preamble, thinking, or explanation. Start directly with the greeting."""

        response = self._call_llm(prompt)

        # Check for approval
        approval_indicators = ["approved", "yes", "let's start", "begin", "go ahead"]
        response_lower = latest_email.get("body", "").lower()

        is_approved = any(indicator in response_lower for indicator in approval_indicators)

        metadata = {
            "phase": "awaiting_approval",
            "approved": is_approved,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return response, metadata, prompt

    def _generate_general_response_tracked(
        self, context: str, latest_email: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Generate general conversational response with prompt tracking."""
        calendly_link = self.calendly_link
        prompt = f"""You are {self.sender_name}, a professional freelancer in ongoing conversation with a client.

Conversation history:
{context}

Latest message:
{latest_email.get('body', '')}

RULES:
1. Do NOT add a signature - it will be added automatically
2. NO meeting availability speculation
3. If scheduling needed: mention it (Calendly link will be added automatically)

Provide a helpful, professional response that moves the conversation forward.
Be natural and conversational.

CRITICAL: Output ONLY the email text to send. Do NOT include any preamble, thinking, or explanation. Start directly with the greeting."""

        response = self._call_llm(prompt)

        metadata = {"phase": "general", "timestamp": datetime.now(timezone.utc).isoformat()}

        return response, metadata, prompt

    def _check_if_call_requested(self, email_history: List[Dict]) -> bool:
        """Check if client explicitly requested a call or meeting."""
        call_indicators = [
            "book a call",
            "schedule a call",
            "let's meet",
            "can we meet",
            "meeting",
            "discuss over a call",
            "phone call",
            "video call",
            "zoom",
            "teams",
            "google meet",
            "calendly",
            "let me know when",
            "when can we talk",
            "available to talk",
            "time to chat",
        ]

        for email in email_history:
            if email.get("direction") == "inbound":
                body = email.get("body", "").lower()
                for indicator in call_indicators:
                    if indicator in body:
                        return True

        return False

    def _extract_client_name_from_signature(self, email_history: List[Dict]) -> str:
        """Extract client name from email signature using improved logic."""
        if not email_history:
            return "Client"

        # Get first inbound email
        first_email = None
        for email in email_history:
            if email.get("direction") == "inbound":
                first_email = email
                break

        if not first_email:
            return "Client"

        # Extract from signature using same logic as pdf_generator.py
        body_lines = first_email.get("body", "").split("\n")
        signature_candidates = []
        client_name = "Client"

        # Collect potential name lines from signature area
        for line in reversed(body_lines):
            line = line.strip()
            if not line or line.startswith("--") or "@" in line:
                continue

            # Skip common non-name patterns
            if any(
                word in line.lower()
                for word in ["thanks", "regards", "best", "sincerely", "cheers"]
            ):
                continue

            # Skip lines that end with colon (likely headers like "Nice-to-haves:")
            if line.endswith(":"):
                continue

            # Skip common section headers
            if any(
                header in line.lower()
                for header in ["nice-to-have", "requirements", "features", "notes", "additional"]
            ):
                continue

            # Look for name-like patterns (1-3 words, starts with capital)
            words = line.split()
            if 1 <= len(words) <= 3 and words[0][0].isupper():
                # Prefer lines that look like names over titles
                if not any(
                    title in line.lower()
                    for title in ["ceo", "cto", "manager", "director", "president", "founder"]
                ):
                    client_name = line.split("(")[0].strip()
                    break
                else:
                    signature_candidates.append(line)

        # If still no name found, check for standalone names in email body
        if client_name == "Client":
            for email in email_history:
                body = email.get("body", "")
                # Look for standalone names at the end of short emails
                lines = body.strip().split("\n")
                for line in reversed(lines):
                    line = line.strip()
                    if len(line.split()) == 1 and len(line) > 2 and line[0].isupper():
                        # Single word that could be a name
                        if line.lower() not in ["thanks", "regards", "best", "sincerely", "cheers"]:
                            client_name = line
                            break
                if client_name != "Client":
                    break

        # Fallback to title lines if no pure name found
        if client_name == "Client" and signature_candidates:
            client_name = signature_candidates[-1].split("(")[0].strip()

        return client_name

    def _extract_budget_constraints(self, email_history: List[Dict]) -> Dict[str, Any]:
        """Extract budget constraints from conversation history."""
        budget_info = {"initial_budget": None, "requested_budget": None, "budget_type": "unknown"}

        for email in email_history:
            body = email.get("body", "").lower()

            # Check for initial budget mentions
            if "$3-4k" in body or "$3-4" in body:
                budget_info["initial_budget"] = 3500
                budget_info["budget_type"] = "range"
            elif "budget:" in body and "$" in body:
                # Try to extract budget amount
                import re

                budget_match = re.search(r"\$(\d+(?:,\d+)?(?:k|000)?)", body)
                if budget_match:
                    amount_str = budget_match.group(1)
                    if "k" in amount_str:
                        amount = int(amount_str.replace("k", "").replace(",", "")) * 1000
                    else:
                        amount = int(amount_str.replace(",", ""))
                    budget_info["initial_budget"] = amount

            # Check for budget reduction requests
            if "cost down to $500" in body or "down to $500" in body:
                budget_info["requested_budget"] = 500
                budget_info["budget_type"] = "reduced"
            elif "$500" in body and ("get" in body or "cost" in body or "price" in body):
                budget_info["requested_budget"] = 500
                budget_info["budget_type"] = "target"

        return budget_info

    def _build_conversation_context(self, conversation: Dict[str, Any]) -> str:
        """Build formatted conversation history."""
        email_history = conversation.get("email_history", [])
        context_parts = []

        # Add conversation metadata at the top
        context_parts.append(
            f"CONVERSATION THREAD ID: {conversation.get('conversation_id', 'unknown')}"
        )

        # Extract client name from signature (improved logic)
        client_name = self._extract_client_name_from_signature(email_history)

        # Identify the client email
        participants = conversation.get("participants", [])
        client_email = None
        for p in participants:
            if "solopilot" not in p.lower() and "abdul" not in p.lower():
                client_email = p
                context_parts.append(f"CLIENT: {client_name} ({p})")
                break

        context_parts.append(f"CURRENT PHASE: {conversation.get('phase', 'understanding')}")
        context_parts.append("---")

        # Include ALL emails to maintain context
        for email in email_history:
            sender = email.get("from", "Unknown")
            timestamp = email.get("timestamp", "")
            body = email.get("body", "").strip()
            direction = email.get("direction", "inbound")

            if not body:
                continue

            # Clear attribution
            if direction == "outbound" or "solopilot" in sender.lower():
                role = f"You ({self.sender_name})"
            else:
                # Extract sender name properly
                sender_name = sender
                if "@" in sender:
                    local = sender.split("@")[0]
                    sender_name = local.replace(".", " ").replace("_", " ").title()
                role = sender_name

            context_parts.append(f"{role} wrote ({timestamp}):")
            context_parts.append(body)
            context_parts.append("---")

        return "\n".join(context_parts)

    def _call_llm(self, prompt: str) -> str:
        """Call LLM with prompt."""
        try:
            if USE_AI_PROVIDER:
                # Use provider
                response = self.provider.generate_code(prompt, [])
                cleaned = self._clean_llm_response(response)
                return cleaned
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
                raw_response = response_body["content"][0]["text"].strip()
                cleaned = self._clean_llm_response(raw_response)
                return cleaned

        except Exception as e:
            logger.error(f"Error calling LLM: {str(e)}")
            # Return a safe fallback response
            return "Thank you for your message. I'm having trouble processing it right now. Could you please try again?"

    def _clean_llm_response(self, response: str) -> str:
        """Remove LLM preambles and thinking from response."""
        # Common preamble patterns to remove
        preamble_patterns = [
            r"Based on.*?:\s*\n+",
            r"I'll.*?:\s*\n+",
            r"Let me.*?:\s*\n+",
            r"Here's.*?:\s*\n+",
            r"I will.*?:\s*\n+",
            r"I'm going to.*?:\s*\n+",
            r"Looking at.*?:\s*\n+",
            r"After analyzing.*?:\s*\n+",
            r"Given.*?:\s*\n+",
        ]

        cleaned = response.strip()

        # Remove preambles
        import re

        for pattern in preamble_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL, count=1)

        # If the response starts with quotes, remove them
        if cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1]
        if cleaned.startswith("'") and cleaned.endswith("'"):
            cleaned = cleaned[1:-1]

        # Remove any leading/trailing whitespace
        cleaned = cleaned.strip()

        # If we accidentally removed everything, return original
        if not cleaned:
            return response.strip()

        return cleaned

    def _extract_clarified_points(self, response: str) -> List[str]:
        """Extract clarified points from understanding phase response."""
        # Simple extraction - could be enhanced with LLM
        points = []

        # Look for numbered lists or bullet points
        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if line and (
                line[0].isdigit()
                or line.startswith("-")
                or line.startswith("•")
                or line.startswith("*")
            ):
                # Clean up the line
                clean_line = line.lstrip("0123456789.-•* ")
                if clean_line:
                    points.append(clean_line)

        return points[:5]  # Max 5 points

    def determine_phase_transition(
        self,
        current_phase: str,
        response_metadata: Dict[str, Any],
        conversation: Dict[str, Any],
        latest_email: Dict[str, Any],
    ) -> Optional[str]:
        """Determine if phase should transition based on response.

        Args:
            current_phase: Current conversation phase
            response_metadata: Metadata from response generation
            conversation: Full conversation state
            latest_email: Latest email from client

        Returns:
            New phase if transition needed, None otherwise
        """
        email_body = latest_email.get("body", "").lower()

        # Check for urgent transition signals
        proposal_triggers = [
            "show me a plan",
            "show me the plan",
            "what are the costs",
            "what's the cost",
            "time estimates",
            "how much",
            "send me a proposal",
            "send proposal",
            "let's move forward",
            "ready to proceed",
            "what's the timeline",
            "project timeline",
        ]

        frustration_signals = [
            "figure the rest out",
            "that's enough questions",
            "just give me",
            "stop asking",
        ]

        # Understanding -> Proposal Draft
        if current_phase == "understanding":
            # Check for direct proposal requests
            for trigger in proposal_triggers + frustration_signals:
                if trigger in email_body:
                    return "proposal_draft"

            # Check email count - if this is 5th+ exchange, move to proposal
            email_count = len(conversation.get("email_history", []))
            if email_count >= 6:  # 3 from client, 3 from us - substantial conversation
                return "proposal_draft"

            # TODO: Fix understanding_context not being updated with actual data
            # For now, disable this check as it's not working properly
            # understanding = conversation.get("understanding_context", {})
            # confidence = understanding.get("confidence_level", 0)
            # clarified_points = understanding.get("clarified_points", [])
            # 
            # # Move to proposal if we have enough understanding
            # if confidence >= 0.7 or len(clarified_points) >= 3:
            #     return "proposal_draft"

        # Proposal Draft -> Proposal Feedback
        elif current_phase == "proposal_draft":
            # Always move to feedback after presenting proposal
            return "proposal_feedback"

        # Proposal Feedback -> Documentation or back to Proposal
        elif current_phase == "proposal_feedback":
            sentiment = response_metadata.get("feedback_sentiment")
            if sentiment == "positive":
                return "documentation"
            else:
                return "proposal_draft"  # Revise proposal

        # Documentation -> Awaiting Approval
        elif current_phase == "documentation":
            if response_metadata.get("documentation_complete"):
                return "awaiting_approval"

        # Awaiting Approval -> Approved or back to Documentation
        elif current_phase == "awaiting_approval":
            if response_metadata.get("approved"):
                return "approved"

        return None
