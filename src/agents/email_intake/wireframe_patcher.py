"""Wireframe patcher that uses vision AI to apply edits to HTML wireframes.

Uses Bedrock Claude to analyze annotated screenshots and generate HTML/CSS modifications.

Flow:
1. Vision model reads annotated screenshots and generates edit intent
2. Code model applies the edit intent to the original HTML
3. Returns the modified HTML
"""

import base64
import json
import os
import logging
from typing import Any, Dict, List, Optional

from botocore.exceptions import BotoCoreError, ClientError, ParamValidationError

logger = logging.getLogger(__name__)

try:
    import boto3

    bedrock_client = boto3.client(
        "bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-2")
    )
    s3_client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-2"))
except Exception:  # pragma: no cover
    bedrock_client = None
    s3_client = None


class WireframePatchError(Exception):
    """Raised when wireframe patching fails."""


class WireframePatcher:
    """Applies vision-guided edits to wireframe HTML."""

    def __init__(self, model_id: Optional[str] = None):
        env_inference_profile = os.environ.get("VISION_INFERENCE_PROFILE_ARN") or os.environ.get(
            "BEDROCK_IP_ARN"
        )
        self.inference_profile_arn: Optional[str] = env_inference_profile

        inferred_model_id = None
        if env_inference_profile:
            inferred_model_id = env_inference_profile.split("/")[-1]

        self.model_id = (
            inferred_model_id
            or model_id
            or os.environ.get("VISION_MODEL_ID")
            or os.environ.get("BEDROCK_MODEL_ID")
        )

    def _invoke_bedrock(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        if bedrock_client is None:
            raise WireframePatchError(
                "Bedrock runtime client unavailable. Verify AWS credentials and region configuration."
            )

        if not (self.inference_profile_arn or self.model_id):
            raise WireframePatchError(
                "Vision model not configured. Set VISION_INFERENCE_PROFILE_ARN or VISION_MODEL_ID."
            )

        payload = json.dumps(request_body)

        def _call(model_id: str, *, inference_arn: Optional[str] = None):
            kwargs = {
                "modelId": model_id,
                "body": payload,
                "contentType": "application/json",
            }
            if inference_arn:
                kwargs["inferenceProfileArn"] = inference_arn
            return bedrock_client.invoke_model(**kwargs)

        try:
            if self.inference_profile_arn:
                profile_model_id = self.inference_profile_arn.split("/")[-1]
                try:
                    response = _call(self.inference_profile_arn)
                except ParamValidationError:
                    response = _call(profile_model_id, inference_arn=self.inference_profile_arn)
            else:
                response = _call(self.model_id)

            return json.loads(response["body"].read())

        except (ClientError, BotoCoreError, ParamValidationError) as e:
            raise WireframePatchError(
                f"Vision model invocation failed: {e}."
            ) from e

    def _upload_debug_dir(
        self,
        tag_dir: str,
        *,
        bucket: str,
        prefix: str,
        trace_id: Optional[str],
        debug_tag: str,
    ) -> None:
        if not s3_client:
            return
        if not os.path.isdir(tag_dir):
            return

        try:
            entries = [f for f in os.listdir(tag_dir) if os.path.isfile(os.path.join(tag_dir, f))]
        except Exception:
            return

        for filename in entries:
            local_path = os.path.join(tag_dir, filename)
            key = f"{prefix.rstrip('/')}/{trace_id or 'unknown'}/{debug_tag}/{filename}"
            try:
                s3_client.upload_file(local_path, bucket, key)
            except Exception as err:
                logger.warning(f"Upload failed: {err}")

    def _emit_debug_data(
        self,
        *,
        debug_dir: Optional[str],
        debug_tag: str,
        trace_id: Optional[str],
        data: Dict[str, Any],
        bucket: Optional[str],
        prefix: Optional[str],
    ) -> None:
        if not debug_dir:
            return
            
        tag_dir = os.path.join(debug_dir, debug_tag)
        try:
            os.makedirs(tag_dir, exist_ok=True)
            
            # Write each key in data to a file
            for filename, content in data.items():
                mode = "w" if isinstance(content, str) else "wb"
                encoding = "utf-8" if mode == "w" else None
                
                path = os.path.join(tag_dir, filename)
                with open(path, mode, encoding=encoding) as f:
                    if filename.endswith(".json") and isinstance(content, (dict, list)):
                        json.dump(content, f, indent=2, default=str)
                    else:
                        f.write(content)
                        
            if bucket and prefix:
                self._upload_debug_dir(
                    tag_dir,
                    bucket=bucket,
                    prefix=prefix,
                    trace_id=trace_id,
                    debug_tag=debug_tag
                )
        except Exception as e:
            logger.warning(f"Failed to emit debug data: {e}")

    def generate_edit_intent(
        self,
        screenshots: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        user_prompt: Optional[str] = None,
        *,
        debug_dir: Optional[str] = None,
        trace_id: Optional[str] = None,
        bucket: Optional[str] = None,
        prefix: Optional[str] = None,
    ) -> str:
        """Generate edit intent from annotated wireframe screenshots.

        Args:
            screenshots: List of { screenId, imageBase64 }
            annotations: List of { screenId, x, y, width, height, comment?, ... }
            user_prompt: Optional additional instruction from user

        Returns:
            Plain text describing the requested HTML/CSS modifications
        """
        base_instructions = """You are analyzing annotated wireframe screenshots. The user has drawn rectangular highlights on areas they want to modify.

For each highlighted area, describe the requested change in clear, actionable terms. Focus on:
- Visual changes (colors, sizes, spacing, fonts)
- Content changes (text updates, labels)
- Layout changes (positioning, alignment)
- Component changes (add/remove elements)

Output your response as a bulleted list of specific, actionable edits. Each edit should reference the visual location or element being modified.

Example output:
- Change the main header text from "Welcome" to "Hello World"
- Make the primary CTA button background color blue (#3B82F6)
- Increase the padding around the hero section to 4rem
- Add a subtitle below the main heading with text "Your tagline here"
"""

        content: List[Dict[str, Any]] = [
            {"type": "text", "text": base_instructions.strip()},
        ]

        # Add screenshots with their annotations
        for screenshot in screenshots:
            img = screenshot.get("imageBase64")
            screen_id = screenshot.get("screenId", "unknown")
            if img:
                content.append({
                    "type": "text",
                    "text": f"Screen: {screen_id}",
                })
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": img},
                })

        # Add annotation comments
        screen_annotations = {}
        for a in annotations:
            sid = a.get("screenId", "default")
            if sid not in screen_annotations:
                screen_annotations[sid] = []
            screen_annotations[sid].append(a)

        for screen_id, anns in screen_annotations.items():
            if anns:
                ann_text = f"\nAnnotations for {screen_id}:\n"
                for i, a in enumerate(anns, 1):
                    comment = a.get("comment", "").strip()
                    if comment:
                        ann_text += f"  {i}. {comment}\n"
                    else:
                        ann_text += f"  {i}. (highlight without comment)\n"
                content.append({"type": "text", "text": ann_text})

        if user_prompt:
            content.append({"type": "text", "text": f"\nUser instruction: {user_prompt}"})

        messages = [{"role": "user", "content": content}]

        request_body = {
            "messages": messages,
            "max_tokens": 2000,
            "anthropic_version": "bedrock-2023-05-31",
        }

        # Debug Input
        self._emit_debug_data(
            debug_dir=debug_dir,
            debug_tag="intent_input",
            trace_id=trace_id,
            bucket=bucket,
            prefix=prefix,
            data={
                "prompt.txt": base_instructions,
                "request_payload.json": request_body,
                "user_prompt.txt": user_prompt or "",
            }
        )

        try:
            body = self._invoke_bedrock(request_body)
            text = body["content"][0]["text"] if body.get("content") else ""
            cleaned = (text or "").strip()
            if not cleaned:
                raise WireframePatchError(
                    "Vision model returned empty edit intent."
                )
                
            # Debug Output
            self._emit_debug_data(
                debug_dir=debug_dir,
                debug_tag="intent_output",
                trace_id=trace_id,
                bucket=bucket,
                prefix=prefix,
                data={
                    "intent.txt": cleaned,
                    "response_full.json": body
                }
            )

            logger.info(f"Generated edit intent: {cleaned[:200]}...")
            return cleaned
        except WireframePatchError:
            raise
        except Exception as e:
            logger.error(f"Edit intent generation failed: {e}", exc_info=True)
            raise WireframePatchError(str(e)) from e

    def apply_edits(
        self,
        original_html: str,
        edit_intent: str,
        screen_name: str = "screen",
        *,
        debug_dir: Optional[str] = None,
        trace_id: Optional[str] = None,
        bucket: Optional[str] = None,
        prefix: Optional[str] = None,
    ) -> str:
        """Apply edit intent to HTML and return modified HTML.

        Args:
            original_html: The current screen HTML
            edit_intent: Plain text describing the edits to make
            screen_name: Name of the screen for context

        Returns:
            Modified HTML string
        """
        apply_instructions = f"""You are a web developer assistant. Given the original HTML of a wireframe screen and a list of requested edits, produce the modified HTML.

Rules:
1. Apply ALL the requested edits accurately
2. Preserve the overall structure and styling approach
3. Use Tailwind CSS classes when possible (the original uses Tailwind)
4. Do not remove existing functionality unless explicitly requested
5. Output ONLY the complete modified HTML document, no explanation
6. Ensure the output is valid HTML

Screen name: {screen_name}

Original HTML:
```html
{original_html}
```

Requested edits:
{edit_intent}

Output the complete modified HTML document:"""

        messages = [{"role": "user", "content": apply_instructions}]

        request_body = {
            "messages": messages,
            "max_tokens": 8000,
            "anthropic_version": "bedrock-2023-05-31",
        }

        # Debug Input
        self._emit_debug_data(
            debug_dir=debug_dir,
            debug_tag="apply_input",
            trace_id=trace_id,
            bucket=bucket,
            prefix=prefix,
            data={
                "original.html": original_html,
                "intent.txt": edit_intent,
                "request_payload.json": request_body,
            }
        )

        try:
            body = self._invoke_bedrock(request_body)
            text = body["content"][0]["text"] if body.get("content") else ""
            
            # Extract HTML from potential markdown code blocks
            modified_html = self._extract_html(text)
            
            if not modified_html:
                raise WireframePatchError(
                    "Model did not return valid HTML."
                )
            
            # Debug Output
            self._emit_debug_data(
                debug_dir=debug_dir,
                debug_tag="apply_output",
                trace_id=trace_id,
                bucket=bucket,
                prefix=prefix,
                data={
                    "modified.html": modified_html,
                    "response_full.json": body
                }
            )

            logger.info(f"Applied edits successfully, HTML length: {len(modified_html)}")
            return modified_html
            
        except WireframePatchError:
            raise
        except Exception as e:
            logger.error(f"Apply edits failed: {e}", exc_info=True)
            raise WireframePatchError(str(e)) from e

    def _extract_html(self, text: str) -> str:
        """Extract HTML from model response, handling potential markdown code blocks."""
        text = text.strip()
        
        # Check for markdown code blocks
        if "```html" in text:
            # Extract content between ```html and ```
            start = text.find("```html") + 7
            end = text.rfind("```")
            if end > start:
                return text[start:end].strip()
        elif "```" in text:
            # Generic code block
            start = text.find("```") + 3
            end = text.rfind("```")
            if end > start:
                return text[start:end].strip()
        
        # If starts with <!DOCTYPE or <html, treat as raw HTML
        if text.startswith("<!DOCTYPE") or text.startswith("<html") or text.startswith("<"):
            return text
        
        return text

    def patch_screen(
        self,
        original_html: str,
        screenshots: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        user_prompt: Optional[str] = None,
        screen_name: str = "screen",
        *,
        debug_dir: Optional[str] = None,
        job_id: Optional[str] = None,  # Used as trace_id
        debug_bucket: Optional[str] = None,
        debug_prefix: Optional[str] = None,
    ) -> str:
        """Full pipeline: analyze screenshots, generate edits, apply to HTML.

        Args:
            original_html: Current screen HTML
            screenshots: Annotated screenshot images
            annotations: Highlight annotations with comments
            user_prompt: Optional overall edit instruction
            screen_name: Name of the screen

        Returns:
            Modified HTML
        """
        # Step 1: Generate edit intent from vision
        edit_intent = self.generate_edit_intent(
            screenshots, 
            annotations, 
            user_prompt,
            debug_dir=debug_dir,
            trace_id=job_id,
            bucket=debug_bucket,
            prefix=debug_prefix
        )
        
        # Step 2: Apply edits to HTML
        modified_html = self.apply_edits(
            original_html, 
            edit_intent, 
            screen_name,
            debug_dir=debug_dir,
            trace_id=job_id,
            bucket=debug_bucket,
            prefix=debug_prefix
        )
        
        return modified_html
