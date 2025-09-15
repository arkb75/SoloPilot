"""Vision analyzer that converts annotated crops into JSON patches.

Uses Bedrock multimodal (Anthropic Claude) to analyze image crops alongside
the annotator's note and nearby text, and returns strict JSON Patch ops.

Output schema:
[
  { "op": "replace", "path": "/title", "value": "External Dashboard" }
]

We validate patches on the caller side; this module focuses on model IO.
"""

import json
import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import boto3
    bedrock_client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-2"))
except Exception:  # pragma: no cover
    bedrock_client = None


SYSTEM_INSTRUCTIONS = (
    "You are an editing assistant. You receive one or more image crops from a PDF page "
    "with the user's handwritten or typed notes. Your job is to produce a SMALL set of JSON Patch operations (RFC6902 subset) "
    "to update a structured requirements JSON. Only return patches for fields you can clearly infer, leave others untouched.\n\n"
    "Rules:\n"
    "- Allowed paths: /title, /summary, /business_description, /project_type, /budget_amount\n"
    "- Prefer minimal edits (e.g., replace only a word in the title rather than rewriting whole text)\n"
    "- If the note says change 'Internal' to 'External' in the main title, return a single replace for /title with the new title.\n"
    "- If budget is specified as a number, set /budget_amount to that number (no currency symbols).\n"
    "- Output ONLY a JSON array of patches. No commentary."
)


class VisionAnalyzer:
    def __init__(self, model_id: Optional[str] = None):
        self.model_id = model_id or os.environ.get("VISION_MODEL_ID") or os.environ.get("BEDROCK_MODEL_ID")

    def build_messages(self, annotations: List[Dict[str, Any]], requirements: Dict[str, Any], user_prompt: Optional[str]) -> List[Dict[str, Any]]:
        content: List[Dict[str, Any]] = [
            {"type": "text", "text": SYSTEM_INSTRUCTIONS},
            {"type": "text", "text": "Current requirements (JSON):\n" + json.dumps(requirements, indent=2)},
        ]

        for idx, a in enumerate(annotations):
            desc = [f"Annotation {idx+1}:", f"zone={a.get('zone','')}"]
            if a.get("comment"):
                desc.append(f"note={a['comment']}")
            if a.get("selectedText"):
                desc.append(f"selected={a['selectedText']}")
            if a.get("surroundingText"):
                desc.append(f"context={a['surroundingText'][:200]}")
            content.append({"type": "text", "text": "\n".join(desc)})
            if a.get("imageData"):
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": a["imageData"],
                    },
                })

        if user_prompt:
            content.append({"type": "text", "text": f"User overall instruction: {user_prompt}"})

        return [{"role": "user", "content": content}]

    def analyze(self, annotations: List[Dict[str, Any]], requirements: Dict[str, Any], user_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
        if bedrock_client is None or not self.model_id:
            logger.warning("VisionAnalyzer unavailable (no bedrock client or model id)")
            return []
        try:
            messages = self.build_messages(annotations, requirements, user_prompt)
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "temperature": 0.0,
                "messages": messages,
            }

            response = bedrock_client.invoke_model(modelId=self.model_id, body=json.dumps(request_body))
            body = json.loads(response["body"].read())
            text = body["content"][0]["text"] if body.get("content") else "[]"
            # The model should return just a JSON array
            patches = json.loads(text)
            if isinstance(patches, list):
                return patches
            return []
        except Exception as e:
            logger.warning(f"Vision analysis failed: {e}")
            return []
