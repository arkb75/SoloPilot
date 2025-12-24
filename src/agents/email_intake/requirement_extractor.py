"""Requirement extractor using Bedrock LLM."""

import json
import logging
import os
from decimal import Decimal  # Added for Decimal handling
from typing import Any, Dict, List

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


class RequirementEditError(Exception):
    """Raised when requirement edits cannot be applied."""


class RequirementExtractor:
    """Extracts project requirements from email conversations using LLM."""

    def __init__(self):
        """Initialize with AI provider or Bedrock client."""
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

    def extract(
        self, email_history: List[Dict[str, Any]], existing_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract requirements from email conversation.

        Args:
            email_history: List of email exchanges
            existing_requirements: Previously extracted requirements

        Returns:
            Updated requirements dict matching analyser format
        """
        # Log extraction start
        logger.info("=" * 80)
        logger.info("REQUIREMENT EXTRACTOR: Starting extraction")
        logger.info(f"  - Email History Count: {len(email_history)}")
        logger.info(f"  - Has Existing Requirements: {bool(existing_requirements)}")
        if email_history:
            latest_email = email_history[-1]
            logger.info(f"  - Latest Email From: {latest_email.get('from', 'unknown')}")
            logger.info(f"  - Latest Email Subject: {latest_email.get('subject', 'unknown')}")
        logger.info("=" * 80)
        
        # Build conversation context
        conversation = self._build_conversation_context(email_history)

        # Safely serialize existing requirements by converting Decimal to native types
        def _decimal_safe(obj: Any):
            """Custom JSON encoder for Decimal objects."""
            if isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            raise TypeError

        safe_existing_json = json.dumps(existing_requirements, indent=2, default=_decimal_safe)

        # Create extraction prompt
        if existing_requirements:
            prompt = f"""You are a project requirement analyst. Update the existing requirements based on the email conversation.

EXISTING REQUIREMENTS (update these based on new information):
{safe_existing_json}

EMAIL CONVERSATION:
{conversation}

IMPORTANT: Return the COMPLETE updated requirements, not just changes. Include all fields from the existing requirements, updating values where the conversation provides new information.

Return a JSON object with these fields:"""
        else:
            prompt = f"""You are a project requirement analyst. Extract project requirements from this email conversation.

EMAIL CONVERSATION:
{conversation}

Extract and return a JSON object with these fields:"""
        
        # Add the common fields description
        prompt += """
- client_name: Client's name (extract from email signature if possible)
- title: Project name/title
- summary: Brief project description
- project_type: "website", "web_app", "mobile_app", or "other"
- business_description: Client's business description
- features: Array of {{"name": "Feature Name", "desc": "Feature description"}} (3-5 key features)
- tech_stack: Array of mentioned technologies (if any)
- constraints: Array of technical/business constraints
- timeline: Delivery timeline or deadline
- budget: Budget range or fixed amount
- budget_amount: Single numeric budget amount (e.g., 1000 for $1k, 3500 for $3-4k range)
- scope_items: Array of {{"title": "Scope Title", "description": "Detailed description"}} for proposal sections
- timeline_phases: Array of {{"phase": "Phase Name", "duration": "X weeks"}} for project phases
- pricing_breakdown: Array of {{"item": "Line Item", "amount": numeric_amount}} that adds up to budget_amount

For scope_items, timeline_phases, and pricing_breakdown:
- If project mentions "dashboard", include appropriate dashboard-specific items
- If "Shopify" is mentioned with dashboard, include Shopify integration
- Timeline should typically have Discovery, Design/Development, Testing, Launch phases
- Pricing should be realistic and add up to the budget_amount

Return ONLY valid JSON, no additional text."""

        # Log the prompt being sent
        logger.info("=" * 80)
        logger.info("REQUIREMENT EXTRACTOR: Sending prompt to LLM")
        logger.info("Prompt preview (first 500 chars):")
        logger.info(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        logger.info("=" * 80)

        try:
            if USE_AI_PROVIDER:
                # Use provider to extract requirements
                response = self.provider.generate_code(prompt, [])
                # Parse JSON response
                requirements = json.loads(response)
            else:
                # Call Bedrock directly to extract requirements
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                }

                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id, body=json.dumps(request_body)
                )

                response_body = json.loads(response["body"].read())
                llm_response = response_body["content"][0]["text"]

                # Parse JSON response
                requirements = json.loads(llm_response)

            # Log extracted requirements
            logger.info("=" * 80)
            logger.info("REQUIREMENT EXTRACTOR: Extracted requirements")
            logger.info(json.dumps(requirements, indent=2))
            logger.info("=" * 80)

            logger.info("Successfully extracted requirements")
            return requirements

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            logger.error(f"LLM Response was: {llm_response if 'llm_response' in locals() else 'Not available'}")
            # Return existing requirements on error
            return existing_requirements
        except Exception as e:
            logger.error(f"Error extracting requirements: {str(e)}")
            return existing_requirements

    def apply_edit_instructions(self, requirements: Dict[str, Any], instructions: str) -> Dict[str, Any]:
        """Apply natural language instructions to existing requirements JSON."""

        if not instructions or not instructions.strip():
            raise RequirementEditError("Empty instruction set provided")

        def _decimal_safe(obj: Any):
            if isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            raise TypeError

        requirements_json = json.dumps(requirements, indent=2, default=_decimal_safe)

        prompt = f"""You are a senior proposal analyst. Update the JSON requirements to reflect the requested changes exactly.

CURRENT REQUIREMENTS:
{requirements_json}

CHANGE INSTRUCTIONS:
{instructions.strip()}

Return ONLY the updated requirements JSON. Do not include explanations, markdown, code fences, or extra text. Preserve all fields from the current payload, updating only where the instructions require changes."""

        try:
            if USE_AI_PROVIDER:
                response = self.provider.generate_code(prompt, [])
                logger.info("Requirement edit model raw response (provider): %s", response)
                updated = json.loads(response)
            else:
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                }

                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id, body=json.dumps(request_body)
                )
                body = json.loads(response["body"].read())
                model_text = body["content"][0]["text"]
                logger.info("Requirement edit model raw response (bedrock): %s", model_text)
                updated = json.loads(model_text)

            if not isinstance(updated, dict):
                raise RequirementEditError("Model returned non-object requirements payload")

            return updated
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse requirement edit response: {e}")
            raise RequirementEditError("Model returned invalid JSON while applying edits") from e
        except Exception as e:
            logger.error(f"Error applying requirement edits: {e}")
            raise RequirementEditError(str(e)) from e

    def is_complete(self, requirements: Dict[str, Any]) -> bool:
        """Check if requirements are complete enough to proceed.

        Args:
            requirements: Current requirements dict

        Returns:
            True if requirements are sufficient
        """
        # Required fields for minimal viable requirements
        required_fields = ["title", "project_type", "business_description", "features"]

        # Check required fields exist and have values
        for field in required_fields:
            if field not in requirements or not requirements[field]:
                return False

        # Check features array has at least 3 items
        if len(requirements.get("features", [])) < 3:
            return False

        # Nice to have: timeline and budget
        # But not required for MVP

        logger.info(f"Requirements completeness check: {True}")
        return True

    def generate_questions(self, requirements: Dict[str, Any]) -> str:
        """Generate follow-up questions for missing information.

        Args:
            requirements: Current requirements dict

        Returns:
            Formatted questions string
        """
        questions = []

        # Check each field and add relevant questions
        if not requirements.get("title"):
            questions.append("What would you like to name your project?")

        if not requirements.get("project_type"):
            questions.append(
                "What type of project are you looking to build? (website, web application, mobile app, etc.)"
            )

        if not requirements.get("business_description"):
            questions.append("Could you describe your business and what it does?")

        features = requirements.get("features", [])
        if len(features) < 3:
            if len(features) == 0:
                questions.append(
                    "What are the main features you'd like in your project? Please list at least 3-5 key features."
                )
            else:
                questions.append(
                    f"You've mentioned {len(features)} feature(s). Could you describe {3 - len(features)} more key features you'd like?"
                )

        if not requirements.get("timeline"):
            questions.append("When would you like this project completed?")

        if not requirements.get("budget"):
            questions.append("What's your budget range for this project?")

        # Format questions
        if questions:
            return "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
        else:
            # No specific questions, ask for confirmation
            return "Is there anything else you'd like to add or clarify about your project?"

    def _build_conversation_context(self, email_history: List[Dict[str, Any]]) -> str:
        """Build formatted conversation from email history."""
        conversation_parts = []

        for email in email_history:
            sender = email.get("from", "Unknown")
            timestamp = email.get("timestamp", "")
            body = email.get("body", "")

            conversation_parts.append(
                f"From: {sender}\n" f"Date: {timestamp}\n" f"Message:\n{body}\n" f"{'-' * 50}"
            )

        return "\n".join(conversation_parts)


    def update_requirements_from_feedback(
        self, existing_requirements: Dict[str, Any], feedback_email: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update requirements based on client feedback using LLM.
        
        Args:
            existing_requirements: Current complete requirements
            feedback_email: Latest feedback email from client
            
        Returns:
            Updated complete requirements (not just changes)
        """
        # Safely serialize existing requirements by converting Decimal to native types
        def _decimal_safe(obj: Any):
            """Custom JSON encoder for Decimal objects."""
            if isinstance(obj, Decimal):
                # Preserve integers without .0
                return int(obj) if obj % 1 == 0 else float(obj)
            raise TypeError

        safe_existing_json = json.dumps(existing_requirements, indent=2, default=_decimal_safe)
        
        prompt = f"""You are a requirements analyst. You have an existing set of project requirements and the client has provided feedback requesting changes.

EXISTING REQUIREMENTS:
{safe_existing_json}

CLIENT FEEDBACK:
From: {feedback_email.get('from', 'Unknown')}
Body: {feedback_email.get('body', '')}

TASK:
Update the existing requirements based on the client's feedback. Return the COMPLETE updated requirements, not just the changes.

Key instructions:
1. If the client mentions a new budget, update BOTH the budget field AND budget_amount
2. If the client asks to remove features, remove them from the features list
3. If the client asks to add features, add them to the features list
4. If the client updates the timeline, update the timeline field
5. If features change significantly, update scope_items to reflect the changes
6. If budget changes, recalculate pricing_breakdown to match the new budget_amount
7. Keep all other requirements that aren't explicitly changed
8. Maintain the same JSON structure as the existing requirements

For budget changes:
- "$1k" or "$1000" → budget_amount: 1000
- "$500" → budget_amount: 500
- "$3-4k" → budget_amount: 3500 (midpoint)
- Update pricing_breakdown items proportionally

Return ONLY the updated requirements as a valid JSON object. Do not include any explanation or commentary."""

        try:
            # Call LLM
            if USE_AI_PROVIDER:
                llm_response = self.provider.generate_code(prompt, [])
            else:
                # Lambda environment
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                }
                
                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id, body=json.dumps(request_body)
                )
                
                response_body = json.loads(response["body"].read())
                llm_response = response_body["content"][0]["text"]
            
            # Clean response
            llm_response = llm_response.strip()
            if llm_response.startswith("```json"):
                llm_response = llm_response[7:]
            if llm_response.endswith("```"):
                llm_response = llm_response[:-3]
            llm_response = llm_response.strip()
            
            # Parse JSON response
            updated_requirements = json.loads(llm_response)
            
            # Log the update
            logger.info("=" * 80)
            logger.info("REQUIREMENT EXTRACTOR: Updated requirements from feedback")
            logger.info(json.dumps(updated_requirements, indent=2))
            logger.info("=" * 80)
            
            return updated_requirements
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            logger.error(f"LLM Response was: {llm_response if 'llm_response' in locals() else 'Not available'}")
            # Return existing requirements on error
            return existing_requirements
        except Exception as e:
            logger.error(f"Error updating requirements from feedback: {str(e)}")
            return existing_requirements

    def extract_requirement_updates(
        self, latest_email: Dict[str, Any], existing_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract requirement updates from proposal feedback email.

        Args:
            latest_email: The latest feedback email
            existing_requirements: Current requirements

        Returns:
            Dictionary of requirement updates to apply
        """
        email_body = latest_email.get("body", "").lower()
        updates = {}

        # Extract budget updates
        import re

        # Patterns for budget updates
        budget_patterns = [
            r"cost down to \$?([\d,]+)k?",
            r"budget (?:is|of) \$?([\d,]+)k?",
            r"reduce (?:the )?(?:cost|budget) to \$?([\d,]+)k?",
            r"(?:can you|could you) (?:do|make) (?:it|this) (?:for )?\$?([\d,]+)k?",
            r"\$?([\d,]+)k? (?:budget|max|maximum)",
        ]

        for pattern in budget_patterns:
            match = re.search(pattern, email_body)
            if match:
                amount_str = match.group(1).replace(",", "")
                amount = int(amount_str)
                # Handle 'k' notation
                if "k" in match.group(0).lower():
                    amount *= 1000
                updates["budget"] = {"max_amount": amount, "type": "fixed"}
                logger.info(f"Extracted budget update: ${amount}")
                break

        # Extract feature removals/changes
        removal_patterns = [
            r"(?:we're )?not (?:on|using|with) ([\w\s]+)",
            r"no ([\w\s]+)",
            r"remove ([\w\s]+)",
            r"don't (?:need|want|use) ([\w\s]+)",
            r"without ([\w\s]+)",
        ]

        removed_features = []
        for pattern in removal_patterns:
            matches = re.findall(pattern, email_body)
            for match in matches:
                feature = match.strip().lower()
                # Check if this is a significant feature
                if feature in ["shopify", "wordpress", "woocommerce", "magento", "squarespace"]:
                    removed_features.append(feature)
                    logger.info(f"Detected feature removal: {feature}")

        if removed_features:
            updates["removed_features"] = removed_features

            # Update features list if exists
            if "features" in existing_requirements:
                current_features = existing_requirements.get("features", [])
                updated_features = []
                for feature in current_features:
                    feature_name = feature.get("name", "").lower()
                    feature_desc = feature.get("desc", "").lower()
                    # Skip features that mention removed items
                    if not any(
                        removed in feature_name or removed in feature_desc
                        for removed in removed_features
                    ):
                        updated_features.append(feature)
                updates["features"] = updated_features

        # Extract timeline updates
        timeline_patterns = [
            r"(?:need|want) (?:it|this) (?:in|within) ([\d\w\s]+)",
            r"timeline (?:is|of) ([\d\w\s]+)",
            r"(?:by|before) (next \w+|end of \w+|\d+ \w+)",
        ]

        for pattern in timeline_patterns:
            match = re.search(pattern, email_body)
            if match:
                timeline = match.group(1).strip()
                updates["timeline"] = timeline
                logger.info(f"Extracted timeline update: {timeline}")
                break

        # Extract any additional requirements
        if "more" in email_body or "also" in email_body or "addition" in email_body:
            # Mark that there might be additional requirements
            updates["has_additional_requirements"] = True

        return updates
