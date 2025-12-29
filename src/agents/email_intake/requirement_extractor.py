"""Requirement extractor using Bedrock LLM."""

import json
import logging
import os
import re
import uuid
from datetime import datetime
from decimal import Decimal  # Added for Decimal handling
from typing import Any, Dict, List, Optional

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


def _clean_json_response(text: Optional[str]) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _parse_json_response(text: Optional[str]) -> Any:
    cleaned = _clean_json_response(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


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
            self.inference_profile_arn = self._resolve_inference_profile()
            self.model_id = os.environ.get(
                "BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0"
            )

    def _resolve_inference_profile(self) -> Optional[str]:
        return (
            os.environ.get("BEDROCK_IP_ARN")
            or os.environ.get("VISION_INFERENCE_PROFILE_ARN")
        )

    def _invoke_bedrock(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.dumps(request_body)
        if self.inference_profile_arn:
            response = self.bedrock_client.invoke_model(
                modelId=self.inference_profile_arn, body=payload, contentType="application/json"
            )
            return json.loads(response["body"].read())
        response = self.bedrock_client.invoke_model(
            modelId=self.model_id, body=payload, contentType="application/json"
        )
        return json.loads(response["body"].read())

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
- pricing_breakdown: Array of {{"item": "Line Item", "amount": numeric_amount, "optional": boolean}} that adds up to budget_amount
  - Mark nice-to-have items as optional=true
- executive_summary: 1-3 short paragraphs (string with newlines) summarizing the proposal
- executive_summary_paragraphs: Optional array of paragraphs if you can separate them
- tech_stack_overview: Short paragraph explaining the technology stack choices
- next_steps: Array of immediate action steps (3-6 items)
- success_metrics: Array of measurable outcomes (3-6 items)
- freelancer_name: Name of the provider if explicitly mentioned
- validity_note: Short proposal validity note if provided

For scope_items, timeline_phases, and pricing_breakdown:
- If project mentions "dashboard", include appropriate dashboard-specific items
- If "Shopify" is mentioned with dashboard, include Shopify integration
- Timeline should typically have Discovery, Design/Development, Testing, Launch phases
- Pricing should be realistic and add up to the budget_amount

If the conversation does not mention a field (e.g., freelancer_name, validity_note), omit it or return an empty list.

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
                llm_response = response
                # Parse JSON response
                requirements = _parse_json_response(response)
            else:
                # Call Bedrock directly to extract requirements
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                }

                response_body = self._invoke_bedrock(request_body)
                llm_response = response_body["content"][0]["text"]

                # Parse JSON response
                requirements = _parse_json_response(llm_response)

            # Log extracted requirements
            logger.info("=" * 80)
            logger.info("REQUIREMENT EXTRACTOR: Extracted requirements")
            logger.info(json.dumps(requirements, indent=2))
            logger.info("=" * 80)

            logger.info("Successfully extracted requirements")
            requirements = self._ensure_pricing_optional_flags(requirements)
            requirements = self._sync_budget_to_pricing(requirements)
            return requirements

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            logger.error(f"LLM Response was: {llm_response if 'llm_response' in locals() else 'Not available'}")
            # Return existing requirements on error
            return existing_requirements
        except Exception as e:
            logger.error(f"Error extracting requirements: {str(e)}")
            return existing_requirements

    def apply_edit_instructions(
        self, requirements: Dict[str, Any], instructions: str, max_attempts: int = 2
    ) -> Dict[str, Any]:
        """Apply natural language instructions to existing requirements JSON."""

        if not instructions or not instructions.strip():
            raise RequirementEditError("Empty instruction set provided")

        def _decimal_safe(obj: Any):
            if isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            raise TypeError

        requirements_json = json.dumps(requirements, indent=2, default=_decimal_safe)

        base_prompt = f"""You are a senior proposal analyst. Update the JSON requirements to reflect the requested changes exactly.

CURRENT REQUIREMENTS:
{requirements_json}

CHANGE INSTRUCTIONS:
{instructions.strip()}

Return ONLY the updated requirements JSON. Do not include explanations, markdown, code fences, or extra text. Preserve all fields from the current payload, updating only where the instructions require changes."""

        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            prompt = base_prompt
            if attempt > 1 and last_error:
                prompt = (
                    f"{base_prompt}\n\n"
                    f"The previous output was invalid JSON ({last_error}). "
                    "Return valid JSON only with double quotes, no trailing commas."
                )
            try:
                if USE_AI_PROVIDER:
                    response = self.provider.generate_code(prompt, [])
                    logger.info("Requirement edit model raw response (provider): %s", response)
                    updated = _parse_json_response(response)
                else:
                    request_body = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 4000,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                    }

                    body = self._invoke_bedrock(request_body)
                    model_text = body["content"][0]["text"]
                    logger.info("Requirement edit model raw response (bedrock): %s", model_text)
                    updated = _parse_json_response(model_text)

                if not isinstance(updated, dict):
                    raise RequirementEditError("Model returned non-object requirements payload")
                updated = self._ensure_pricing_optional_flags(updated)
                updated = self._sync_budget_to_pricing(updated)
                return updated
            except json.JSONDecodeError as e:
                last_error = e
                logger.error(f"Failed to parse requirement edit response (attempt {attempt}): {e}")
                if attempt == max_attempts:
                    raise RequirementEditError(
                        "Model returned invalid JSON while applying edits"
                    ) from e
            except Exception as e:
                logger.error(f"Error applying requirement edits: {e}")
                raise RequirementEditError(str(e)) from e

        raise RequirementEditError("Model returned invalid JSON while applying edits")

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
        self,
        existing_requirements: Dict[str, Any],
        feedback_email: Dict[str, Any],
        extraction_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update requirements based on client feedback using LLM.
        
        Args:
            existing_requirements: Current complete requirements
            feedback_email: Latest feedback email from client
            extraction_notes: Metadata extractor notes to consider
            
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

EXTRACTION NOTES:
{(extraction_notes or '').strip() or 'None provided'}

TASK:
Update the existing requirements based on the client's feedback. Return the COMPLETE updated requirements, not just the changes.

Key instructions:
1. If the client mentions a new budget, update BOTH the budget field AND budget_amount
2. If the client asks to remove features, remove them from the features list
3. If the client asks to add features, add them to the features list
4. If the client updates the timeline, update the timeline field
5. If features change significantly, update scope_items to reflect the changes
6. If the client requests scope changes that affect pricing, update pricing_breakdown by adding/removing line items, but DO NOT change the amount of any existing line item
6a. If the client asks to remove optional/nice-to-have items, remove any items marked optional=true and remove related optional scope_items/features
7. Keep all other requirements that aren't explicitly changed
8. Maintain the same JSON structure as the existing requirements
9. Preserve the optional flag on existing pricing_breakdown items; mark newly added optional items with optional=true

For budget changes:
- "$1k" or "$1000" → budget_amount: 1000
- "$500" → budget_amount: 500
- "$3-4k" → budget_amount: 3500 (midpoint)
- If the budget changes due to removing/adding items, adjust budget_amount to equal the sum of pricing_breakdown

Return ONLY the updated requirements as a valid JSON object. Do not include any explanation or commentary."""

        trace_id = f"feedback-{datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"
        debug_root = os.environ.get("FEEDBACK_DEBUG_DIR", "/tmp/feedback_debug")
        debug_dir = os.path.join(debug_root, trace_id)
        prompt_path = os.path.join(debug_dir, "prompt.txt")
        response_path = os.path.join(debug_dir, "response.txt")
        def _log_blob(tag: str, payload: str, chunk_size: int = 4000) -> None:
            if not payload:
                logger.info("[FEEDBACK_DEBUG][%s_TEXT] empty=true", tag)
                return
            total = (len(payload) + chunk_size - 1) // chunk_size
            for idx in range(total):
                chunk = payload[idx * chunk_size : (idx + 1) * chunk_size]
                logger.info(
                    "[FEEDBACK_DEBUG][%s_TEXT] part=%s/%s chunk=%s",
                    tag,
                    idx + 1,
                    total,
                    chunk,
                )

        try:
            os.makedirs(debug_dir, exist_ok=True)
            with open(prompt_path, "w", encoding="utf-8") as handle:
                handle.write(prompt)
            logger.info(
                "[FEEDBACK_DEBUG][INPUT] trace_id=%s dir=%s prompt_path=%s prompt_len=%s",
                trace_id,
                debug_dir,
                prompt_path,
                len(prompt),
            )
            _log_blob("INPUT", prompt)
        except Exception as debug_err:
            logger.warning(
                "[FEEDBACK_DEBUG][INPUT] trace_id=%s failed_to_write_prompt=%s",
                trace_id,
                debug_err,
            )

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
                
                response_body = self._invoke_bedrock(request_body)
                llm_response = response_body["content"][0]["text"]

            try:
                with open(response_path, "w", encoding="utf-8") as handle:
                    handle.write(llm_response or "")
                logger.info(
                    "[FEEDBACK_DEBUG][OUTPUT] trace_id=%s response_path=%s response_len=%s",
                    trace_id,
                    response_path,
                    len(llm_response or ""),
                )
                _log_blob("OUTPUT", llm_response or "")
            except Exception as debug_err:
                logger.warning(
                    "[FEEDBACK_DEBUG][OUTPUT] trace_id=%s failed_to_write_response=%s",
                    trace_id,
                    debug_err,
                )
            
            # Parse JSON response
            updated_requirements = _parse_json_response(llm_response)
            existing_requirements = self._ensure_pricing_optional_flags(existing_requirements)
            updated_requirements = self._ensure_pricing_optional_flags(updated_requirements)
            updated_requirements = self._lock_pricing_breakdown(
                existing_requirements, updated_requirements
            )
            updated_requirements = self._sync_budget_to_pricing(updated_requirements)
            
            # Log the update
            logger.info("=" * 80)
            logger.info("REQUIREMENT EXTRACTOR: Updated requirements from feedback")
            logger.info(json.dumps(updated_requirements, indent=2, default=_decimal_safe))
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

    def _lock_pricing_breakdown(
        self, existing_requirements: Dict[str, Any], updated_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        locked_breakdown = existing_requirements.get("pricing_breakdown")
        if not locked_breakdown or not isinstance(locked_breakdown, list):
            return updated_requirements

        updated_breakdown = updated_requirements.get("pricing_breakdown")
        if not updated_breakdown or not isinstance(updated_breakdown, list):
            merged = updated_requirements.copy()
            merged["pricing_breakdown"] = locked_breakdown
            return merged

        def _normalize(label: Any) -> str:
            if not label:
                return ""
            raw = str(label).strip().lower()
            cleaned = "".join(ch if ch.isalnum() else " " for ch in raw)
            return " ".join(cleaned.split())

        existing_amounts = {}
        existing_optionals = {}
        for item in locked_breakdown:
            if not isinstance(item, dict):
                continue
            name = item.get("item") or item.get("name")
            key = _normalize(name)
            if key:
                existing_amounts[key] = item.get("amount")
                existing_optionals[key] = item.get("optional")

        reconciled = []
        locked_count = 0
        for item in updated_breakdown:
            if not isinstance(item, dict):
                continue
            name = item.get("item") or item.get("name")
            key = _normalize(name)
            if key and key in existing_amounts:
                locked_item = dict(item)
                locked_item["amount"] = existing_amounts[key]
                if existing_optionals.get(key) is not None:
                    locked_item["optional"] = existing_optionals[key]
                reconciled.append(locked_item)
                locked_count += 1
            else:
                reconciled.append(item)

        merged = updated_requirements.copy()
        merged["pricing_breakdown"] = reconciled

        logger.info(
            "Locked pricing_breakdown line-item amounts for %s item(s); removed=%s, added=%s",
            locked_count,
            max(len(locked_breakdown) - locked_count, 0),
            max(len(reconciled) - locked_count, 0),
        )
        return merged

    def _ensure_pricing_optional_flags(
        self, requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        breakdown = requirements.get("pricing_breakdown")
        if not breakdown or not isinstance(breakdown, list):
            return requirements

        def _normalize(label: Any) -> str:
            if not label:
                return ""
            raw = str(label).strip().lower()
            cleaned = "".join(ch if ch.isalnum() else " " for ch in raw)
            tokens = [t for t in cleaned.split() if t not in {"optional", "nice", "to", "have"}]
            return " ".join(tokens)

        optional_keys = set()
        scope_items = requirements.get("scope_items") or []
        for item in scope_items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").lower()
            desc = str(item.get("description") or "").lower()
            if "optional" in title or "optional" in desc or "nice-to-have" in title or "nice to have" in title:
                optional_keys.add(_normalize(title))

        features = requirements.get("features") or []
        for item in features:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").lower()
            desc = str(item.get("desc") or "").lower()
            if "optional" in name or "optional" in desc or "nice-to-have" in name or "nice to have" in name:
                optional_keys.add(_normalize(name))

        updated = []
        for item in breakdown:
            if not isinstance(item, dict):
                continue
            optional = item.get("optional")
            if optional is None:
                name = item.get("item") or item.get("name") or ""
                normalized_name = _normalize(name)
                optional = bool(
                    "optional" in str(name).lower()
                    or "nice-to-have" in str(name).lower()
                    or "nice to have" in str(name).lower()
                    or (normalized_name and normalized_name in optional_keys)
                )
            updated_item = dict(item)
            updated_item["optional"] = bool(optional)
            updated.append(updated_item)

        requirements["pricing_breakdown"] = updated
        return requirements

    def _sync_budget_to_pricing(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.storage.budget_utils import compute_budget_total

            total = compute_budget_total({"pricing_breakdown": requirements.get("pricing_breakdown")})
        except Exception as budget_err:
            logger.warning(f"Failed to compute pricing total: {budget_err}")
            return requirements

        if total:
            requirements["budget_amount"] = total
            requirements["budget"] = f"${total:,}"
        return requirements
