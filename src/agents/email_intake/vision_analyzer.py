"""Vision analyzer that converts annotated crops into JSON patches.

Uses Bedrock multimodal (Anthropic Claude) to analyze image crops alongside
the annotator's note and nearby text, and returns strict JSON Patch ops.

Output schema:
[
  { "op": "replace", "path": "/title", "value": "External Dashboard" }
]

We validate patches on the caller side; this module focuses on model IO.
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


class VisionModelError(Exception):
    """Raised when the vision model cannot be invoked successfully."""


class VisionAnalyzer:
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
            raise VisionModelError(
                "Bedrock runtime client unavailable. Verify AWS credentials and region configuration."
            )

        if not (self.inference_profile_arn or self.model_id):
            raise VisionModelError(
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
            raise VisionModelError(
                f"Vision model invocation failed: {e}."
            ) from e

    def _decode_base64(self, payload: str) -> Optional[bytes]:
        if not payload:
            return None
        data = payload
        if data.startswith("data:") and "," in data:
            data = data.split(",", 1)[1]
        try:
            return base64.b64decode(data)
        except Exception:
            return None

    def _sanitize_annotations(self, annotations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sanitized: List[Dict[str, Any]] = []
        for a in annotations:
            if not isinstance(a, dict):
                continue
            slim = dict(a)
            if "imageData" in slim:
                img_len = len(str(slim.get("imageData") or ""))
                slim["imageData"] = f"[omitted:{img_len} chars]"
            sanitized.append(slim)
        return sanitized

    def _upload_debug_dir(
        self,
        tag_dir: str,
        *,
        bucket: str,
        prefix: str,
        trace_id: Optional[str],
        debug_tag: str,
        include_output_only: bool = False,
    ) -> None:
        if not s3_client:
            logger.warning("[VISION_DEBUG][S3] S3 client unavailable")
            return
        if not os.path.isdir(tag_dir):
            logger.warning("[VISION_DEBUG][S3] Debug dir missing: %s", tag_dir)
            return

        try:
            entries = [
                f for f in os.listdir(tag_dir) if os.path.isfile(os.path.join(tag_dir, f))
            ]
        except Exception as err:
            logger.warning("[VISION_DEBUG][S3] Failed to list %s: %s", tag_dir, err)
            return

        if include_output_only:
            entries = [f for f in entries if f == "output.txt"]

        for filename in entries:
            local_path = os.path.join(tag_dir, filename)
            key = f"{prefix.rstrip('/')}/{debug_tag}/{filename}"
            try:
                s3_client.upload_file(local_path, bucket, key)
            except Exception as err:
                logger.warning(
                    "[VISION_DEBUG][S3] Upload failed trace_id=%s tag=%s file=%s: %s",
                    trace_id,
                    debug_tag,
                    filename,
                    err,
                )

        logger.info(
            "[VISION_DEBUG][S3] trace_id=%s tag=%s bucket=%s prefix=%s",
            trace_id,
            debug_tag,
            bucket,
            prefix,
        )

    def _emit_debug_input(
        self,
        *,
        debug_dir: Optional[str],
        debug_tag: str,
        trace_id: Optional[str],
        prompt_text: str,
        pages: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        user_prompt: Optional[str],
        debug_s3_bucket: Optional[str],
        debug_s3_prefix: Optional[str],
    ) -> None:
        if prompt_text:
            logger.info(
                "[VISION_DEBUG][PROMPT] trace_id=%s tag=%s\n%s",
                trace_id,
                debug_tag,
                prompt_text,
            )
        if not debug_dir:
            logger.info(
                "[VISION_DEBUG][INPUT] trace_id=%s tag=%s dir=None pages=%d annotations=%d",
                trace_id,
                debug_tag,
                len(pages),
                len(annotations),
            )
            return
        tag_dir = os.path.join(debug_dir, debug_tag)
        try:
            os.makedirs(tag_dir, exist_ok=True)
        except Exception as err:
            logger.warning("[VISION_DEBUG][INPUT] Failed to create debug dir: %s", err)
            return

        prompt_path = os.path.join(tag_dir, "prompt.txt")
        try:
            with open(prompt_path, "w", encoding="utf-8") as handle:
                handle.write(prompt_text or "")
        except Exception as err:
            logger.warning("[VISION_DEBUG][INPUT] Failed to write prompt: %s", err)

        pages_meta: List[Dict[str, Any]] = []
        for p in pages:
            if not isinstance(p, dict):
                continue
            page_index = p.get("pageIndex", 0)
            img_b64 = p.get("imageBase64") or ""
            img_path = os.path.join(tag_dir, f"page_{page_index}_composite.png")
            decoded = self._decode_base64(img_b64)
            if decoded:
                try:
                    with open(img_path, "wb") as handle:
                        handle.write(decoded)
                    pages_meta.append(
                        {
                            "pageIndex": page_index,
                            "image_path": img_path,
                            "bytes": len(decoded),
                        }
                    )
                except Exception as err:
                    pages_meta.append(
                        {"pageIndex": page_index, "image_path": None, "error": str(err)}
                    )
            else:
                pages_meta.append(
                    {"pageIndex": page_index, "image_path": None, "error": "decode_failed"}
                )

        pages_manifest_path = os.path.join(tag_dir, "pages.json")
        try:
            with open(pages_manifest_path, "w", encoding="utf-8") as handle:
                json.dump(pages_meta, handle, indent=2)
        except Exception as err:
            logger.warning("[VISION_DEBUG][INPUT] Failed to write pages manifest: %s", err)

        annotations_path = os.path.join(tag_dir, "annotations.json")
        try:
            with open(annotations_path, "w", encoding="utf-8") as handle:
                json.dump(
                    self._sanitize_annotations(annotations),
                    handle,
                    indent=2,
                    default=str,
                )
        except Exception as err:
            logger.warning("[VISION_DEBUG][INPUT] Failed to write annotations: %s", err)

        if user_prompt:
            try:
                with open(
                    os.path.join(tag_dir, "user_prompt.txt"),
                    "w",
                    encoding="utf-8",
                ) as handle:
                    handle.write(user_prompt)
            except Exception as err:
                logger.warning("[VISION_DEBUG][INPUT] Failed to write user prompt: %s", err)

        logger.info(
            "[VISION_DEBUG][INPUT] trace_id=%s tag=%s dir=%s prompt_path=%s "
            "pages_manifest=%s annotations_path=%s pages=%d annotations=%d",
            trace_id,
            debug_tag,
            tag_dir,
            prompt_path,
            pages_manifest_path,
            annotations_path,
            len(pages),
            len(annotations),
        )

        if debug_s3_bucket and debug_s3_prefix:
            self._upload_debug_dir(
                tag_dir,
                bucket=debug_s3_bucket,
                prefix=f"{debug_s3_prefix.rstrip('/')}/{trace_id or 'unknown'}",
                trace_id=trace_id,
                debug_tag=debug_tag,
                include_output_only=False,
            )

    def _emit_debug_output(
        self,
        *,
        debug_dir: Optional[str],
        debug_tag: str,
        trace_id: Optional[str],
        output_text: str,
        debug_s3_bucket: Optional[str],
        debug_s3_prefix: Optional[str],
    ) -> None:
        logger.info(
            "[VISION_DEBUG][OUTPUT] trace_id=%s tag=%s %s",
            trace_id,
            debug_tag,
            output_text,
        )
        if not debug_dir:
            return
        tag_dir = os.path.join(debug_dir, debug_tag)
        try:
            os.makedirs(tag_dir, exist_ok=True)
        except Exception as err:
            logger.warning("[VISION_DEBUG][OUTPUT] Failed to create debug dir: %s", err)
            return
        try:
            with open(
                os.path.join(tag_dir, "output.txt"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write(output_text or "")
        except Exception as err:
            logger.warning("[VISION_DEBUG][OUTPUT] Failed to write output: %s", err)

        if debug_s3_bucket and debug_s3_prefix:
            self._upload_debug_dir(
                tag_dir,
                bucket=debug_s3_bucket,
                prefix=f"{debug_s3_prefix.rstrip('/')}/{trace_id or 'unknown'}",
                trace_id=trace_id,
                debug_tag=debug_tag,
                include_output_only=True,
            )

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

    def analyze(
        self, annotations: List[Dict[str, Any]], requirements: Dict[str, Any], user_prompt: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        try:
            messages = self.build_messages(annotations, requirements, user_prompt)
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "temperature": 0.0,
                "messages": messages,
            }

            body = self._invoke_bedrock(request_body)
            text = body["content"][0]["text"] if body.get("content") else "[]"
            patches = json.loads(text)
            if isinstance(patches, list):
                return patches
            raise VisionModelError(
                "Vision model returned an unexpected payload (expected JSON array)."
            )
        except VisionModelError as err:
            logger.error(str(err))
            raise
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}", exc_info=True)
            raise VisionModelError(str(e)) from e

    def generate_intent(
        self,
        pages: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        base_instructions: str,
        user_prompt: Optional[str] = None,
        *,
        debug_dir: Optional[str] = None,
        debug_tag: str = "intent",
        debug_trace_id: Optional[str] = None,
        debug_s3_bucket: Optional[str] = None,
        debug_s3_prefix: Optional[str] = None,
    ) -> str:
        """Generate a concise, human-readable edit intent from annotated page composites.

        Inputs:
          - pages: list of { pageIndex, imageBase64 }
          - annotations: list of { pageIndex, comment?, ... }
          - base_instructions: instructions about how to write the intent for a code model
          - user_prompt: optional additional instruction from user

        Returns plain text (no JSON) with short bullet points of code-edit instructions.
        """
        try:
            # Build content: base instructions, short ledger, page images
            content: List[Dict[str, Any]] = [
                {"type": "text", "text": base_instructions.strip()},
            ]

            # Add page composites
            for p in pages:
                img = (p or {}).get("imageBase64")
                if img:
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": img},
                    })

            if user_prompt:
                content.append({"type": "text", "text": f"User prompt: {user_prompt}"})

            messages = [{"role": "user", "content": content}]
            prompt_text = "\n\n".join(
                item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"
            )
            self._emit_debug_input(
                debug_dir=debug_dir,
                debug_tag=debug_tag,
                trace_id=debug_trace_id,
                prompt_text=prompt_text,
                pages=pages,
                annotations=annotations,
                user_prompt=user_prompt,
                debug_s3_bucket=debug_s3_bucket,
                debug_s3_prefix=debug_s3_prefix,
            )
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 800,
                "temperature": 0.0,
                "messages": messages,
            }
            body = self._invoke_bedrock(request_body)
            text = body["content"][0]["text"] if body.get("content") else ""
            self._emit_debug_output(
                debug_dir=debug_dir,
                debug_tag=debug_tag,
                trace_id=debug_trace_id,
                output_text=text or "",
                debug_s3_bucket=debug_s3_bucket,
                debug_s3_prefix=debug_s3_prefix,
            )
            cleaned = (text or "").strip()
            if not cleaned:
                raise VisionModelError(
                    "Vision model returned an empty intent. Check annotations or model configuration."
                )
            return cleaned
        except VisionModelError as err:
            logger.error(str(err))
            raise
        except Exception as e:
            logger.error(f"Vision intent generation failed: {e}", exc_info=True)
            raise VisionModelError(str(e)) from e

    def generate_ops(
        self,
        pages: List[Dict[str, Any]],
        annotations: List[Dict[str, Any]],
        current_requirements: Dict[str, Any],
        user_prompt: Optional[str] = None,
        *,
        debug_dir: Optional[str] = None,
        debug_tag: str = "ops",
        debug_trace_id: Optional[str] = None,
        debug_s3_bucket: Optional[str] = None,
        debug_s3_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Emit a constrained set of edit operations suitable for deterministic application.

        Returns a dict with shape: { "ops": [...], "warnings": [...] }
        """
        try:
            schema_text = (
                "{"  # begin
                "\"ops\": [{ \"type\": \"set|add|remove\", \"path\": \"JSON Pointer\", \"value\": any }],"
                "\"warnings\": [\"string\"]"
                "}"  # end
            )

            guardrails = (
                "You produce ONLY JSON matching the schema. No prose, no markdown.\n"
                "Rules:\n"
                "- Modify only whitelisted fields: /title, /summary, /pricing_breakdown/*/amount, /timeline_phases/*/duration.\n"
                "- Prefer minimal edits.\n"
                "- Do not introduce new proper nouns or entities not present in the note.\n"
                "- If unsure, return an empty ops list and a warning."
            )

            content: List[Dict[str, Any]] = [
                {"type": "text", "text": guardrails},
                {"type": "text", "text": f"Schema:\n{schema_text}"},
                {"type": "text", "text": "Current requirements (JSON):\n" + json.dumps(current_requirements, indent=2)},
            ]

            # Include concise annotation notes
            if annotations:
                notes_lines = []
                for i, a in enumerate(annotations):
                    note = (a.get("comment") or "").strip()
                    if note:
                        notes_lines.append(f"[{i+1}] page {a.get('pageIndex', 0)+1}: {note}")
                if notes_lines:
                    content.append({"type": "text", "text": "Annotation notes:\n" + "\n".join(notes_lines)})

            # Add images for context
            for p in pages:
                img = (p or {}).get("imageBase64")
                if img:
                    content.append(
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": img},
                        }
                    )

            if user_prompt:
                content.append({"type": "text", "text": f"User prompt: {user_prompt}"})

            messages = [{"role": "user", "content": content}]
            prompt_text = "\n\n".join(
                item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"
            )
            self._emit_debug_input(
                debug_dir=debug_dir,
                debug_tag=debug_tag,
                trace_id=debug_trace_id,
                prompt_text=prompt_text,
                pages=pages,
                annotations=annotations,
                user_prompt=user_prompt,
                debug_s3_bucket=debug_s3_bucket,
                debug_s3_prefix=debug_s3_prefix,
            )
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 400,
                "temperature": 0.0,
                "messages": messages,
            }

            body = self._invoke_bedrock(request_body)
            text = body["content"][0]["text"] if body.get("content") else "{\"ops\": [], \"warnings\": [\"empty\"]}"
            self._emit_debug_output(
                debug_dir=debug_dir,
                debug_tag=debug_tag,
                trace_id=debug_trace_id,
                output_text=text or "",
                debug_s3_bucket=debug_s3_bucket,
                debug_s3_prefix=debug_s3_prefix,
            )
            parsed = json.loads((text or "").strip() or "{}")

            # Basic shape validation
            if not isinstance(parsed, dict):
                raise VisionModelError("Ops response is not an object")
            if "ops" not in parsed or not isinstance(parsed.get("ops"), list):
                raise VisionModelError("Ops response missing 'ops' array")
            if "warnings" in parsed and not isinstance(parsed["warnings"], list):
                parsed["warnings"] = [str(parsed["warnings"])]

            # Normalize ops entries minimally
            norm_ops: List[Dict[str, Any]] = []
            for raw in parsed.get("ops", []):
                if not isinstance(raw, dict):
                    continue
                op_type = str(raw.get("type") or raw.get("op") or "").lower()
                path = raw.get("path")
                if op_type not in {"set", "add", "remove"}:
                    continue
                if not isinstance(path, str) or not path.startswith("/"):
                    continue
                norm_ops.append({"type": op_type, "path": path, "value": raw.get("value")})
            parsed["ops"] = norm_ops

            return parsed
        except VisionModelError:
            raise
        except Exception as e:
            logger.error(f"Vision ops generation failed: {e}", exc_info=True)
            raise VisionModelError(str(e)) from e
