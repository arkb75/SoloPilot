"""
Response Reviser for email intake system.

Handles revising email responses based on AI feedback using Claude Sonnet 4/5.
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# Import AI providers if available
try:
    from src.providers.base import get_provider
    USE_AI_PROVIDER = True
except ImportError:
    USE_AI_PROVIDER = False
    # Fall back to direct Bedrock
    import boto3
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-2")

logger = logging.getLogger(__name__)


class ResponseReviser:
    """Revises email responses using Claude Sonnet 4/5 based on specific feedback."""
    
    def __init__(self):
        """Initialize the response reviser with Claude Sonnet 4/5."""
        # Use Sonnet 4/5 (same model as original response generation)
        self.model_id = os.environ.get(
            "BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-5-20250929-v1:0"
        )
        self.anthropic_model = "claude-3-5-sonnet-20241022"  # For AI provider
        
        if USE_AI_PROVIDER:
            self.provider = get_provider(os.environ.get("AI_PROVIDER", "bedrock"))
    
    def revise_response(
        self, 
        original_response: str, 
        feedback: str, 
        conversation_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Revise an email response based on specific feedback.
        
        Args:
            original_response: The original email response text
            feedback: Specific feedback on what to change
            conversation_context: Optional conversation context for better revision
            
        Returns:
            Dict containing revised response and metadata
        """
        try:
            # Build the revision prompt
            prompt = self._build_revision_prompt(original_response, feedback, conversation_context)
            
            # Call Sonnet 4/5 for revision
            revised_response = self._call_sonnet(prompt)
            
            # Validate the revised response
            if not revised_response or len(revised_response.strip()) < 10:
                logger.warning("Revised response too short, keeping original")
                return {
                    "revised_response": original_response,
                    "feedback_prompt": feedback,
                    "revision_prompt": prompt,
                    "revised_at": datetime.now(timezone.utc).isoformat(),
                    "revision_successful": False,
                    "revision_error": "Revised response too short"
                }
            
            # Log successful revision
            logger.info(f"Successfully revised response. Original length: {len(original_response)}, Revised length: {len(revised_response)}")
            
            return {
                "revised_response": revised_response.strip(),
                "feedback_prompt": feedback,
                "revision_prompt": prompt,
                "revised_at": datetime.now(timezone.utc).isoformat(),
                "revision_successful": True
            }
            
        except Exception as e:
            logger.error(f"Error revising response: {str(e)}")
            return {
                "revised_response": original_response,
                "feedback_prompt": feedback,
                "revision_prompt": "",
                "revised_at": datetime.now(timezone.utc).isoformat(),
                "revision_successful": False,
                "revision_error": str(e)
            }
    
    def _build_revision_prompt(
        self, 
        original_response: str, 
        feedback: str, 
        conversation_context: Dict[str, Any] = None
    ) -> str:
        """Build the revision prompt for Sonnet 4/5."""
        
        # Add conversation context if available
        context_text = ""
        if conversation_context:
            email_history = conversation_context.get("email_history", [])
            if email_history:
                latest_client_email = None
                for email in reversed(email_history):
                    if email.get("direction") == "inbound":
                        latest_client_email = email.get("body", "")
                        break
                
                if latest_client_email:
                    context_text = f"""
LATEST CLIENT EMAIL (for context):
{latest_client_email[:500]}...

"""
        
        prompt = f"""You are revising an email response to a client based on specific feedback.

{context_text}ORIGINAL EMAIL RESPONSE:
{original_response}

REVISION FEEDBACK:
{feedback}

INSTRUCTIONS:
1. Make ONLY the specific changes requested in the feedback
2. Keep everything else exactly as written in the original
3. Maintain the same tone, style, and structure
4. Do NOT add greetings or signatures (those are handled separately)
5. Do NOT rewrite entire sections unless explicitly requested
6. Focus on making precise, targeted improvements

Return the revised email response (body only, no greeting/signature):"""
        
        return prompt
    
    def _call_sonnet(self, prompt: str) -> str:
        """Call Claude Sonnet 4/5 model for revision."""
        try:
            if USE_AI_PROVIDER:
                # Use the AI provider framework
                response = self.provider.generate_code(prompt, [])
                return response
            else:
                # Use Bedrock directly in Lambda
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,  # Lower temperature for more focused revision
                }
                
                response = bedrock_client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body)
                )
                
                response_body = json.loads(response['body'].read())
                return response_body['content'][0]['text']
                
        except Exception as e:
            logger.error(f"Error calling Sonnet model: {str(e)}")
            raise
    
    def revise_with_retry(
        self, 
        original_response: str, 
        feedback: str, 
        conversation_context: Dict[str, Any] = None,
        max_attempts: int = 2
    ) -> Dict[str, Any]:
        """
        Revise response with retry logic for better reliability.
        
        Args:
            original_response: The original email response text
            feedback: Specific feedback on what to change
            conversation_context: Optional conversation context
            max_attempts: Maximum revision attempts
            
        Returns:
            Dict containing revision result and metadata
        """
        for attempt in range(max_attempts):
            try:
                result = self.revise_response(original_response, feedback, conversation_context)
                
                if result.get("revision_successful", False):
                    result["revision_attempts"] = attempt + 1
                    return result
                
                logger.warning(f"Revision attempt {attempt + 1} failed: {result.get('revision_error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Revision attempt {attempt + 1} exception: {str(e)}")
                if attempt == max_attempts - 1:
                    # Last attempt, return failure
                    return {
                        "revised_response": original_response,
                        "feedback_prompt": feedback,
                        "revision_prompt": "",
                        "revised_at": datetime.now(timezone.utc).isoformat(),
                        "revision_successful": False,
                        "revision_error": f"All {max_attempts} attempts failed. Last error: {str(e)}",
                        "revision_attempts": max_attempts
                    }
        
        # Fallback if all attempts failed
        return {
            "revised_response": original_response,
            "feedback_prompt": feedback,
            "revision_prompt": "",
            "revised_at": datetime.now(timezone.utc).isoformat(),
            "revision_successful": False,
            "revision_error": f"All {max_attempts} revision attempts failed",
            "revision_attempts": max_attempts
        }
