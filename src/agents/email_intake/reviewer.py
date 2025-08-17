"""
Email Response Reviewer

This module uses Claude 3.5 Haiku to review email responses before they are sent.
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
    """Reviews email responses using Claude 3.5 Haiku for quality assessment."""
    
    def __init__(self):
        """Initialize the email reviewer with Claude 3.5 Haiku model."""
        # Use Haiku for fast, cost-effective review
        self.model = "us.anthropic.claude-3-5-haiku-20241022-v1:0"  # Bedrock model ID
        self.anthropic_model = "claude-3-5-haiku-20241022"  # For AI provider
        
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
        """Call Claude 3.5 Haiku model for review."""
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