"""Requirement extractor using Bedrock LLM."""

import json
import logging
import os
from decimal import Decimal  # Added for Decimal handling
from typing import Any, Dict, List

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
        # Build conversation context
        conversation = self._build_conversation_context(email_history)

        # Safely serialize existing requirements by converting Decimal to native types
        def _decimal_safe(obj: Any):
            """Custom JSON encoder for Decimal objects."""
            if isinstance(obj, Decimal):
                # Preserve integers without .0
                return int(obj) if obj % 1 == 0 else float(obj)
            raise TypeError

        safe_existing_json = json.dumps(existing_requirements, indent=2, default=_decimal_safe)

        # Create extraction prompt
        prompt = f"""You are a project requirement analyst. Extract project requirements from this email conversation.

Previous requirements (update and enhance these):
{safe_existing_json}

Email conversation:
{conversation}

Extract and return a JSON object with these fields:
- title: Project name/title
- summary: Brief project description
- project_type: "website", "web_app", "mobile_app", or "other"
- business_description: Client's business description
- features: Array of {{"name": "Feature Name", "desc": "Feature description"}} (3-5 key features)
- tech_stack: Array of mentioned technologies (if any)
- constraints: Array of technical/business constraints
- timeline: Delivery timeline or deadline
- budget: Budget range or fixed amount

Return ONLY valid JSON, no additional text."""

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

            # Merge with existing requirements
            merged = self._merge_requirements(existing_requirements, requirements)

            logger.info("Successfully extracted requirements")
            return merged

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            # Return existing requirements on error
            return existing_requirements
        except Exception as e:
            logger.error(f"Error extracting requirements: {str(e)}")
            return existing_requirements

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

    def _merge_requirements(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Merge new requirements with existing ones."""
        merged = existing.copy()

        # Update simple fields
        for field in [
            "title",
            "summary",
            "project_type",
            "business_description",
            "timeline",
            "budget",
        ]:
            if field in new and new[field]:
                merged[field] = new[field]

        # Merge arrays (features, tech_stack, constraints)
        for array_field in ["features", "tech_stack", "constraints"]:
            existing_items = existing.get(array_field, [])
            new_items = new.get(array_field, [])

            if array_field == "features":
                # For features, replace if new has more detail
                if new_items:
                    merged[array_field] = new_items
            else:
                # For others, combine unique items
                combined = existing_items + new_items
                # Remove duplicates while preserving order
                seen = set()
                unique = []
                for item in combined:
                    item_str = str(item)
                    if item_str not in seen:
                        seen.add(item_str)
                        unique.append(item)
                merged[array_field] = unique

        return merged
