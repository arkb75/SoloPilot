"""
Email Response Reviewer

This module uses Claude 4.5 Haiku to review email responses before they are sent.
It analyzes the response against conversation context and provides a quality assessment.
"""

import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

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


class EmailReviewer:
    """Reviews email responses using Claude 4.5 Haiku for quality assessment."""
    
    def __init__(self):
        """Initialize the email reviewer with Claude 4.5 Haiku model."""
        # Use Haiku for fast, cost-effective review
        self.model = "anthropic.claude-haiku-4-5-20251001-v1:0"  # Bedrock model ID
        self.anthropic_model = "claude-4-5-haiku-20241022"  # For AI provider
        
        if USE_AI_PROVIDER:
            self.provider = get_provider(os.environ.get("AI_PROVIDER", "bedrock"))
        
    def review_response(self, conversation: Dict[str, Any], response_text: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Review an email response for quality and appropriateness.
        
        Args:
            conversation: Full conversation data including email history
            response_text: The proposed email response to review
            metadata: Optional metadata about the response
            
        Returns:
            Dict containing review scores and analysis
        """
        try:
            # Build the review prompt
            prompt = self._build_review_prompt(conversation, response_text, metadata)
            
            # Call Haiku for review
            response = self._call_haiku(prompt)
            
            # Parse and validate the response
            review = json.loads(response)
            validated_review = self._validate_review(review)
            
            # Log successful review
            logger.info(f"Successfully reviewed response with overall score: {validated_review.get('overall_score', 0)}")
            
            return validated_review
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse review JSON: {str(e)}")
            logger.error(f"Raw response: {response[:500]}...")
            return self._get_default_review()
            
        except Exception as e:
            logger.error(f"Error reviewing response: {str(e)}")
            return self._get_default_review()

    
    def generate_feedback_prompt(self, review: Dict[str, Any], original_response: str, conversation_context: Dict[str, Any] = None) -> str:
        """
        Generate precise, actionable feedback for response improvement.
        
        Args:
            review: Review results from review_response()
            original_response: The original email response text
            conversation_context: Optional conversation context for better feedback
            
        Returns:
            Precise feedback prompt focusing on specific changes needed
        """
        try:
            # Identify low-scoring dimensions (< 4)
            low_scores = []
            feedback_points = []
            
            if review.get("relevance_score", 5) < 4:
                low_scores.append(("RELEVANCE", review.get("relevance_score", 0)))
                feedback_points.append(self._generate_relevance_feedback(original_response, conversation_context))
            
            if review.get("completeness_score", 5) < 4:
                low_scores.append(("COMPLETENESS", review.get("completeness_score", 0)))
                feedback_points.append(self._generate_completeness_feedback(original_response, conversation_context))
            
            if review.get("accuracy_score", 5) < 4:
                low_scores.append(("ACCURACY", review.get("accuracy_score", 0)))
                feedback_points.append(self._generate_accuracy_feedback(original_response))
            
            if review.get("next_steps_score", 5) < 4:
                low_scores.append(("NEXT STEPS", review.get("next_steps_score", 0)))
                feedback_points.append(self._generate_next_steps_feedback(original_response))
            
            # Handle red flags
            red_flags = review.get("red_flags", [])
            if red_flags:
                feedback_points.append(self._generate_red_flag_feedback(original_response, red_flags))
            
            # If no specific issues found but overall score is low, generate general feedback
            if not feedback_points and review.get("overall_score", 5) < 4:
                feedback_points.append("GENERAL: The response needs improvement. Review for clarity, completeness, and professionalism.")
            
            # Build the feedback prompt
            if not feedback_points:
                return "No specific improvements needed. The response meets quality standards."
            
            feedback_text = "\n\n".join([point for point in feedback_points if point])
            
            return f"""REQUIRED CHANGES (make only these specific edits):

{feedback_text}

IMPORTANT INSTRUCTIONS:
- Make ONLY the changes listed above
- Keep everything else exactly as written
- Maintain the same tone and style
- Do not add greeting or signature (already handled)
- Do not rewrite entire sections unless specifically requested"""

        except Exception as e:
            logger.error(f"Error generating feedback prompt: {str(e)}")
            return "Unable to generate specific feedback. Please review manually for improvements."
    
    def _generate_relevance_feedback(self, response: str, context: Dict[str, Any] = None) -> str:
        """Generate feedback for improving relevance to client's questions."""
        if not context:
            return "1. RELEVANCE: Response doesn't fully address the client's specific questions or concerns. Add direct responses to their main points."
        
        # Try to identify what the client asked about
        latest_email = context.get("email_history", [])
        if latest_email:
            client_email = latest_email[-1].get("body", "") if latest_email[-1].get("direction") == "inbound" else ""
            
            # Look for question words or request indicators
            questions = []
            if "budget" in client_email.lower() and "budget" not in response.lower():
                questions.append("budget requirements")
            if "timeline" in client_email.lower() and "timeline" not in response.lower():
                questions.append("timeline expectations")
            if "?" in client_email:
                questions.append("their specific questions")
            
            if questions:
                return f"1. RELEVANCE (Score: {context.get('relevance_score', 0)}/5): Missing response to {', '.join(questions)}. Add direct answers to what they asked about."
        
        return "1. RELEVANCE: Ensure response directly addresses the client's main questions and concerns mentioned in their email."
    
    def _generate_completeness_feedback(self, response: str, context: Dict[str, Any] = None) -> str:
        """Generate feedback for improving completeness."""
        missing_elements = []
        
        # Check for common missing elements
        if context:
            latest_email_body = ""
            email_history = context.get("email_history", [])
            if email_history:
                latest_email_body = email_history[-1].get("body", "").lower()
            
            if "cost" in latest_email_body or "price" in latest_email_body:
                if "cost" not in response.lower() and "price" not in response.lower() and "$" not in response:
                    missing_elements.append("pricing information")
            
            if "when" in latest_email_body or "timeline" in latest_email_body:
                if "week" not in response.lower() and "day" not in response.lower() and "month" not in response.lower():
                    missing_elements.append("timeline details")
            
            if "how" in latest_email_body and "work" in latest_email_body:
                if "process" not in response.lower() and "approach" not in response.lower():
                    missing_elements.append("process explanation")
        
        if missing_elements:
            return f"2. COMPLETENESS: Missing {', '.join(missing_elements)}. Add brief mentions of these topics."
        
        return "2. COMPLETENESS: Response needs more detail. Add specific information about process, timeline, or other relevant details."
    
    def _generate_accuracy_feedback(self, response: str) -> str:
        """Generate feedback for improving accuracy."""
        # Look for potential over-promises or vague claims
        issues = []
        
        response_lower = response.lower()
        if "definitely" in response_lower or "guaranteed" in response_lower:
            issues.append("Remove absolute guarantees - use 'plan to' or 'aim for' instead")
        
        if "very quick" in response_lower or "super fast" in response_lower:
            issues.append("Replace vague speed claims with specific timeframes")
        
        if "cheap" in response_lower or "low cost" in response_lower:
            issues.append("Replace subjective cost terms with specific pricing")
        
        if issues:
            return f"3. ACCURACY: {'; '.join(issues)}."
        
        return "3. ACCURACY: Review for any overpromises or inaccurate technical claims. Be more specific and realistic."
    
    def _generate_next_steps_feedback(self, response: str) -> str:
        """Generate feedback for improving next steps clarity."""
        response_lower = response.lower()
        
        # Check if response has clear next steps
        has_action = any(phrase in response_lower for phrase in [
            "next step", "will send", "i'll prepare", "let me know", "would you like",
            "i can", "shall i", "ready by", "by tomorrow", "this week"
        ])
        
        if has_action:
            return "4. NEXT STEPS: Make the action item more specific with timeline. Example: 'I will send you a detailed proposal by end of day tomorrow.'"
        else:
            return "4. NEXT STEPS: Add a clear next action. Example: 'Would you like me to prepare a detailed proposal? I can have it ready within 24 hours.'"
    
    def _generate_red_flag_feedback(self, response: str, red_flags: List[str]) -> str:
        """Generate feedback for addressing red flags."""
        flag_fixes = []
        
        for flag in red_flags[:3]:  # Limit to top 3 red flags
            if "over-promising" in flag.lower():
                flag_fixes.append("Remove overpromises - be more realistic about timelines and outcomes")
            elif "pricing" in flag.lower() or "cost" in flag.lower():
                flag_fixes.append("Clarify pricing - provide ranges or ask about budget first")
            elif "technical" in flag.lower():
                flag_fixes.append("Verify technical accuracy - ensure claims are realistic")
            elif "scope" in flag.lower():
                flag_fixes.append("Clarify project scope - be specific about what's included")
            else:
                flag_fixes.append(f"Address: {flag}")
        
        if flag_fixes:
            return f"RED FLAGS: {'; '.join(flag_fixes)}."
        
        return ""
    
    def _build_review_prompt(self, conversation: Dict[str, Any], response_text: str, metadata: Dict[str, Any] = None) -> str:
        """Build the review prompt with conversation context and response."""
        # Convert Decimals in conversation data
        conversation = decimal_to_json_serializable(conversation)
        if metadata:
            metadata = decimal_to_json_serializable(metadata)
        
        # Get conversation history
        email_history = conversation.get("email_history", [])
        client_email = conversation.get("client_email", "unknown")
        phase = conversation.get("phase", "unknown")
        
        # Build context from recent emails (last 5 for context)
        context_emails = []
        for email in email_history[-5:]:
            direction = email.get("direction", "unknown")
            body = email.get("body", "")
            timestamp = email.get("timestamp", "")
            
            context_emails.append(f"{direction.upper()} [{timestamp}]: {body[:300]}...")
        
        context_text = "\n\n".join(context_emails) if context_emails else "No previous emails"
        
        # Include metadata if available
        metadata_text = ""
        if metadata:
            metadata_text = f"\n\nRESPONSE METADATA:\n{json.dumps(metadata, indent=2)}"
        
        prompt = f"""
You are reviewing an email response before it gets sent to a client. Analyze the response quality and appropriateness.

CLIENT: {client_email}
CONVERSATION PHASE: {phase}

CONVERSATION CONTEXT (recent emails):
{context_text}

PROPOSED RESPONSE TO REVIEW:
{response_text}
{metadata_text}

Please review this response on the following criteria:

1. RELEVANCE (1-5): Does the response directly address what the client asked or needs?
2. COMPLETENESS (1-5): Are all the client's questions and concerns addressed?
3. ACCURACY (1-5): Is the technical information correct? No over-promising or false claims?
4. NEXT STEPS (1-5): Are clear next actions or path forward provided?

Also identify any RED FLAGS:
- Over-promising capabilities or timelines
- Incorrect pricing or technical information
- Commitments beyond reasonable scope
- Inconsistencies with previous responses
- Unprofessional tone or language

Provide a 2-3 sentence summary of the response quality and any concerns.

Output a JSON object with your analysis:
{{
  "relevance_score": 1-5,
  "completeness_score": 1-5,
  "accuracy_score": 1-5,
  "next_steps_score": 1-5,
  "overall_score": 1-5,
  "red_flags": ["list", "of", "concerns"],
  "summary": "Brief 2-3 sentence assessment of response quality and recommendations",
  "reviewed_at": "{datetime.now().isoformat()}"
}}

Provide ONLY the JSON object:
"""
        
        return prompt
    
    def _call_haiku(self, prompt: str) -> str:
        """Call Claude 4.5 Haiku model for review."""
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
                    "temperature": 0.2,  # Low temperature for consistent review
                }
                
                response = bedrock_client.invoke_model(
                    modelId=self.model,
                    body=json.dumps(request_body)
                )
                
                response_body = json.loads(response['body'].read())
                return response_body['content'][0]['text']
                
        except Exception as e:
            logger.error(f"Error calling Haiku model: {str(e)}")
            raise
    
    def _validate_review(self, review: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize the review response."""
        validated = {
            "relevance_score": max(1, min(5, review.get("relevance_score", 3))),
            "completeness_score": max(1, min(5, review.get("completeness_score", 3))),
            "accuracy_score": max(1, min(5, review.get("accuracy_score", 3))),
            "next_steps_score": max(1, min(5, review.get("next_steps_score", 3))),
            "overall_score": max(1, min(5, review.get("overall_score", 3))),
            "red_flags": review.get("red_flags", [])[:5],  # Limit to 5 flags
            "summary": review.get("summary", "Review completed")[:500],  # Limit summary length
            "reviewed_at": review.get("reviewed_at", datetime.now().isoformat())
        }
        
        # Calculate overall score if not provided
        if "overall_score" not in review:
            scores = [
                validated["relevance_score"],
                validated["completeness_score"],
                validated["accuracy_score"],
                validated["next_steps_score"]
            ]
            validated["overall_score"] = round(sum(scores) / len(scores))
        
        return validated
    
    def _get_default_review(self) -> Dict[str, Any]:
        """Return a default review when analysis fails."""
        return {
            "relevance_score": 3,
            "completeness_score": 3,
            "accuracy_score": 3,
            "next_steps_score": 3,
            "overall_score": 3,
            "red_flags": ["Review system unavailable"],
            "summary": "Unable to complete automated review. Please manually review before sending.",
            "reviewed_at": datetime.now().isoformat()
        }
