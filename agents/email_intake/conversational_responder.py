"""Enhanced conversational response generator with prompt tracking."""

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

try:
    from agents.ai_providers import get_provider
    from agents.ai_providers.base import log_call
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
                "bedrock-runtime",
                region_name=os.environ.get("AWS_REGION", "us-east-2")
            )
            self.model_id = os.environ.get(
                "BEDROCK_MODEL_ID",
                "us.anthropic.claude-3-5-haiku-20241022-v1:0"
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
            "just give me", "no just", "you decide", "send me the proposal",
            "let's move forward", "sounds good", "that works",
            "let me know how we can call", "book a call", "schedule",
            "give me a proposal", "send proposal", "quote please"
        ]
        
        is_impatient = any(indicator in email_body for indicator in impatience_indicators)
        
        if is_impatient and phase == "understanding":
            logger.info("User impatience detected - jumping to proposal phase")
            # Override phase to jump to proposal
            phase = "proposal_draft"
        
        # Build conversation context
        context = self._build_conversation_context(conversation)
        
        # Generate phase-appropriate response and capture prompt
        if phase == "understanding":
            return self._generate_clarifying_response_tracked(context, latest_email, conversation)
        elif phase == "proposal_draft":
            return self._generate_proposal_response_tracked(context, conversation)
        elif phase == "proposal_feedback":
            return self._handle_proposal_feedback_tracked(context, latest_email, conversation)
        elif phase == "documentation":
            return self._generate_documentation_response_tracked(context, conversation)
        elif phase == "awaiting_approval":
            return self._handle_approval_response_tracked(context, latest_email)
        else:
            # Default conversational response
            return self._generate_general_response_tracked(context, latest_email)
    
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
        response_text, metadata, _ = self.generate_response_with_tracking(conversation, latest_email)
        return response_text, metadata

    def _generate_clarifying_response_tracked(
        self, context: str, latest_email: Dict[str, Any], conversation: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Generate response during understanding phase with prompt tracking."""
        
        # Extract client name for personalized response
        client_name = self._extract_client_name_from_signature(conversation.get("email_history", []))
        
        prompt = f"""You are {self.sender_name}, a professional freelancer responding to {client_name}.

CRITICAL: Address the client as "{client_name}" throughout your response.

Conversation history:
{context}

Latest client message:
{latest_email.get('body', '')}

IMPORTANT RULES:
1. Address the client as "{client_name}" (NOT as any other name)
2. If the client says "show me a plan", "what are costs", or shows impatience - SKIP to proposal phase
3. If client gives short/curt responses, match their brevity
4. If client ignores a question twice, never ask it again
5. If client suggests specific meeting times (e.g., "Tuesday or Thursday between 10am-1pm"), respond:
   "Perfect! I'd love to discuss your project. Please book a time that works best at: {self.calendly_link}"
6. Sign emails as "{self.sender_name}"
6. Keep responses concise - 2-3 paragraphs max
7. ALWAYS acknowledge the client's key points:
   - Their company/role
   - Project type (e.g., "onboarding automation")
   - Specific requirements they listed
   - Budget/timeline if mentioned
8. Focus on understanding ONLY the missing critical info

READ THE CLIENT'S EMAIL CAREFULLY and respond to what they actually said.
If they provided detailed requirements, acknowledge them before asking questions.

Generate a response that respects their communication style and urgency.

CRITICAL: Output ONLY the email text to send. Do NOT include any preamble, thinking, or explanation. Start directly with the greeting (e.g., "Hi Morgan,")."""

        response = self._call_llm(prompt)
        
        # Extract any clarified points from the response
        metadata = {
            "phase": "understanding",
            "clarified_points": self._extract_clarified_points(response),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return response, metadata, prompt

    def _generate_proposal_response_tracked(
        self, context: str, conversation: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Generate proposal presentation with prompt tracking."""
        requirements = conversation.get("requirements", {})
        understanding = conversation.get("understanding_context", {})
        
        # Extract client name for personalized proposal
        client_name = self._extract_client_name_from_signature(conversation.get("email_history", []))
        
        # Extract budget constraints from conversation history
        budget_info = self._extract_budget_constraints(conversation.get("email_history", []))
        
        # Determine target budget
        target_budget = None
        budget_guidance = "Keep costs reasonable: $500 for simple dashboards, $1-3k for standard projects"
        
        if budget_info["requested_budget"]:
            target_budget = budget_info["requested_budget"]
            budget_guidance = f"CRITICAL: Target budget is ${target_budget}. Do NOT exceed this amount."
        elif budget_info["initial_budget"]:
            target_budget = budget_info["initial_budget"]
            budget_guidance = f"Client's budget is around ${target_budget}. Stay within this range."
        
        prompt = f"""You are {self.sender_name}, a professional freelancer presenting a project proposal to {client_name}.

CRITICAL: Address the client as "{client_name}" throughout your response.

Conversation history:
{context}

Current understanding:
{json.dumps(decimal_to_json_serializable(understanding), indent=2)}

Requirements gathered:
{json.dumps(decimal_to_json_serializable(requirements), indent=2)}

BUDGET CONSTRAINTS:
{json.dumps(budget_info, indent=2)}

IMPORTANT RULES:
1. Address the client as "{client_name}" (NOT as any other name)
2. Be direct and action-oriented
3. {budget_guidance}
4. Sign as "{self.sender_name}"
5. If they mention "call" or "meeting", end with: "Book a time at: {self.calendly_link}"
6. NO questions like "Are you available?" or "When works for you?"

Generate a VERY concise proposal:
1. Project Overview: Briefly reference their specific project (e.g., "Shopify dashboard", "e-commerce platform", etc.)
2. Scope: 3-4 bullet points based on THEIR actual requirements from the conversation
3. Investment: Single total amount{"" if not target_budget else f" (target: ${target_budget})"}
4. Timeline: Simple duration (e.g., "1 week" or "3 weeks")
5. If they asked about calling: "Book a time at: {self.calendly_link}"

CRITICAL: Use their SPECIFIC project details, not generic "web development solution" language.
Base the scope on what they actually described in their emails.

Keep it under 100 words. Be decisive and specific.

CRITICAL: Output ONLY the email text to send. Do NOT include any preamble, thinking, or explanation. Start directly with the greeting."""

        response = self._call_llm(prompt)
        
        metadata = {
            "phase": "proposal_draft",
            "proposal_version": 1,
            "should_send_proposal": True,  # Always generate PDF for proposals
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return response, metadata, prompt

    def _handle_proposal_feedback_tracked(
        self, context: str, latest_email: Dict[str, Any], conversation: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Handle feedback on proposal with prompt tracking."""
        
        # Extract client name for personalized response
        client_name = self._extract_client_name_from_signature(conversation.get("email_history", []))
        
        prompt = f"""You are {self.sender_name}, a professional freelancer responding to {client_name}'s feedback on your proposal.

CRITICAL: Address the client as "{client_name}" throughout your response.

Conversation history:
{context}

Client's feedback:
{latest_email.get('body', '')}

RULES:
1. Address the client as "{client_name}" (NOT as any other name)
2. Sign as "{self.sender_name}"
3. Be concise and action-oriented
4. NO meeting time speculation
5. If they want to discuss: "You can book a time at {self.calendly_link}"

Analyze the feedback and respond appropriately:
- If they want changes, acknowledge and ask for specifics
- If they have questions, answer clearly
- If they're ready to proceed, confirm and outline next steps
- If they're not interested, thank them professionally

Keep the tone professional and solution-focused.

CRITICAL: Output ONLY the email text to send. Do NOT include any preamble, thinking, or explanation. Start directly with the greeting."""

        response = self._call_llm(prompt)
        
        # Determine if we should move to documentation phase
        approval_indicators = ["yes", "proceed", "sounds good", "let's do it", "approved"]
        feedback_lower = latest_email.get('body', '').lower()
        
        is_approved = any(indicator in feedback_lower for indicator in approval_indicators)
        
        metadata = {
            "phase": "proposal_feedback",
            "feedback_sentiment": "positive" if is_approved else "needs_revision",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return response, metadata, prompt

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
1. Sign as "{self.sender_name}"
2. NO meeting speculation
3. Be concise but thorough

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

Sign as "{self.sender_name}".

CRITICAL: Output ONLY the email text to send. Do NOT include any preamble, thinking, or explanation. Start directly with the greeting."""

        response = self._call_llm(prompt)
        
        metadata = {
            "phase": "documentation",
            "documentation_complete": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return response, metadata, prompt

    def _handle_approval_response_tracked(
        self, context: str, latest_email: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Handle final approval response with prompt tracking."""
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

Sign as "{self.sender_name}".

CRITICAL: Output ONLY the email text to send. Do NOT include any preamble, thinking, or explanation. Start directly with the greeting."""

        response = self._call_llm(prompt)
        
        # Check for approval
        approval_indicators = ["approved", "yes", "let's start", "begin", "go ahead"]
        response_lower = latest_email.get('body', '').lower()
        
        is_approved = any(indicator in response_lower for indicator in approval_indicators)
        
        metadata = {
            "phase": "awaiting_approval",
            "approved": is_approved,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return response, metadata, prompt

    def _generate_general_response_tracked(
        self, context: str, latest_email: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str]:
        """Generate general conversational response with prompt tracking."""
        prompt = f"""You are {self.sender_name}, a professional freelancer in ongoing conversation with a client.

Conversation history:
{context}

Latest message:
{latest_email.get('body', '')}

RULES:
1. Sign as "{self.sender_name}"
2. NO meeting availability speculation
3. If scheduling needed: "You can book a time at {self.calendly_link}"

Provide a helpful, professional response that moves the conversation forward.
Be natural and conversational.

CRITICAL: Output ONLY the email text to send. Do NOT include any preamble, thinking, or explanation. Start directly with the greeting."""

        response = self._call_llm(prompt)
        
        metadata = {
            "phase": "general",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return response, metadata, prompt

    def _extract_client_name_from_signature(self, email_history: List[Dict]) -> str:
        """Extract client name from email signature using improved logic."""
        if not email_history:
            return "Client"
            
        # Get first inbound email
        first_email = None
        for email in email_history:
            if email.get('direction') == 'inbound':
                first_email = email
                break
                
        if not first_email:
            return "Client"
            
        # Extract from signature using same logic as pdf_generator.py
        body_lines = first_email.get('body', '').split('\n')
        signature_candidates = []
        client_name = 'Client'
        
        # Collect potential name lines from signature area
        for line in reversed(body_lines):
            line = line.strip()
            if not line or line.startswith('--') or '@' in line:
                continue
            
            # Skip common non-name patterns
            if any(word in line.lower() for word in ['thanks', 'regards', 'best', 'sincerely', 'cheers']):
                continue
            
            # Look for name-like patterns (1-3 words, starts with capital)
            words = line.split()
            if 1 <= len(words) <= 3 and words[0][0].isupper():
                # Prefer lines that look like names over titles
                if not any(title in line.lower() for title in ['ceo', 'cto', 'manager', 'director', 'president']):
                    client_name = line.split('(')[0].strip()
                    break
                else:
                    signature_candidates.append(line)
        
        # If still no name found, check for standalone names in email body
        if client_name == 'Client':
            for email in email_history:
                body = email.get('body', '')
                # Look for standalone names at the end of short emails
                lines = body.strip().split('\n')
                for line in reversed(lines):
                    line = line.strip()
                    if len(line.split()) == 1 and len(line) > 2 and line[0].isupper():
                        # Single word that could be a name
                        if not line.lower() in ['thanks', 'regards', 'best', 'sincerely', 'cheers']:
                            client_name = line
                            break
                if client_name != 'Client':
                    break
        
        # Fallback to title lines if no pure name found
        if client_name == 'Client' and signature_candidates:
            client_name = signature_candidates[-1].split('(')[0].strip()
        
        return client_name

    def _extract_budget_constraints(self, email_history: List[Dict]) -> Dict[str, Any]:
        """Extract budget constraints from conversation history."""
        budget_info = {
            "initial_budget": None,
            "requested_budget": None,
            "budget_type": "unknown"
        }
        
        for email in email_history:
            body = email.get('body', '').lower()
            
            # Check for initial budget mentions
            if '$3-4k' in body or '$3-4' in body:
                budget_info["initial_budget"] = 3500
                budget_info["budget_type"] = "range"
            elif 'budget:' in body and '$' in body:
                # Try to extract budget amount
                import re
                budget_match = re.search(r'\$(\d+(?:,\d+)?(?:k|000)?)', body)
                if budget_match:
                    amount_str = budget_match.group(1)
                    if 'k' in amount_str:
                        amount = int(amount_str.replace('k', '').replace(',', '')) * 1000
                    else:
                        amount = int(amount_str.replace(',', ''))
                    budget_info["initial_budget"] = amount
            
            # Check for budget reduction requests
            if 'cost down to $500' in body or 'down to $500' in body:
                budget_info["requested_budget"] = 500
                budget_info["budget_type"] = "reduced"
            elif '$500' in body and ('get' in body or 'cost' in body or 'price' in body):
                budget_info["requested_budget"] = 500
                budget_info["budget_type"] = "target"
        
        return budget_info

    def _build_conversation_context(self, conversation: Dict[str, Any]) -> str:
        """Build formatted conversation history."""
        email_history = conversation.get("email_history", [])
        context_parts = []
        
        # Add conversation metadata at the top
        context_parts.append(f"CONVERSATION THREAD ID: {conversation.get('conversation_id', 'unknown')}")
        
        # Extract client name from signature (improved logic)
        client_name = self._extract_client_name_from_signature(email_history)
        
        # Identify the client email
        participants = conversation.get("participants", [])
        client_email = None
        for p in participants:
            if 'solopilot' not in p.lower() and 'abdul' not in p.lower():
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
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.7
                }
                
                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body)
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
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line and (
                line[0].isdigit() or 
                line.startswith('-') or 
                line.startswith('•') or
                line.startswith('*')
            ):
                # Clean up the line
                clean_line = line.lstrip('0123456789.-•* ')
                if clean_line:
                    points.append(clean_line)
        
        return points[:5]  # Max 5 points

    def determine_phase_transition(
        self, current_phase: str, response_metadata: Dict[str, Any], conversation: Dict[str, Any], latest_email: Dict[str, Any]
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
        email_body = latest_email.get('body', '').lower()
        
        # Check for urgent transition signals
        proposal_triggers = [
            "show me a plan",
            "show me the plan", 
            "what are the costs",
            "what's the cost",
            "time estimates",
            "how much",
            "send me a proposal",
            "next steps",
            "let's move forward"
        ]
        
        frustration_signals = [
            "figure the rest out",
            "that's enough questions",
            "just give me",
            "stop asking"
        ]
        
        # Understanding -> Proposal Draft
        if current_phase == "understanding":
            # Check for direct proposal requests
            for trigger in proposal_triggers + frustration_signals:
                if trigger in email_body:
                    return "proposal_draft"
            
            # Check email count - if this is 3rd+ exchange, move to proposal
            email_count = len(conversation.get("email_history", []))
            if email_count >= 4:  # 2 from client, 2 from us
                return "proposal_draft"
            
            understanding = conversation.get("understanding_context", {})
            confidence = understanding.get("confidence_level", 0)
            clarified_points = understanding.get("clarified_points", [])
            
            # Move to proposal if we have enough understanding
            if confidence >= 0.7 or len(clarified_points) >= 3:
                return "proposal_draft"
        
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