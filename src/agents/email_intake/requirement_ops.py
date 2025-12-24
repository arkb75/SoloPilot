"""Deterministic application of small, typed requirement edit operations.

This module enforces a whitelist of editable paths and applies a restricted
subset of JSON-Patch-like operations in a safe, auditable way. It is intended
to replace free-form LLM-based editing for simple requirement updates.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


class RequirementOpsError(Exception):
    """Raised when an operation set is invalid or cannot be applied safely."""


@dataclass
class EditOp:
    type: str  # set|add|remove
    path: str  # JSON Pointer
    value: Any | None = None


def _normalize_allowed_paths(paths: Optional[Iterable[str]]) -> List[str]:
    if not paths:
        return [
            "/title",
            "/summary",
            "/pricing_breakdown",
            "/timeline_phases",
        ]
    return [p.strip() for p in paths if p and p.strip().startswith("/")]


def _path_is_allowed(pointer: str, allowed_prefixes: List[str]) -> bool:
    # Allow exact match or child paths of allowed prefixes
    for prefix in allowed_prefixes:
        if pointer == prefix:
            return True
        if pointer.startswith(prefix + "/"):
            return True
    return False


def _resolve_pointer(root: Any, pointer: str) -> Tuple[Any, str]:
    """Return (parent_container, last_token) for a JSON Pointer.

    Supports dicts and lists. Does not create intermediary nodes.
    """
    if not pointer or pointer[0] != "/":
        raise RequirementOpsError(f"Invalid JSON Pointer: {pointer}")

    # RFC 6901 token unescaping
    def _unescape(token: str) -> str:
        return token.replace("~1", "/").replace("~0", "~")

    tokens = [_unescape(t) for t in pointer.split("/")[1:]]

    parent = root
    for token in tokens[:-1]:
        if isinstance(parent, dict):
            if token not in parent:
                raise RequirementOpsError(f"Path does not exist: {pointer}")
            parent = parent[token]
        elif isinstance(parent, list):
            try:
                idx = int(token)
            except ValueError as exc:
                raise RequirementOpsError(f"Non-integer index in path: {pointer}") from exc
            if idx < 0 or idx >= len(parent):
                raise RequirementOpsError(f"Index out of range in path: {pointer}")
            parent = parent[idx]
        else:
            raise RequirementOpsError(f"Cannot traverse into non-container at: {pointer}")

    return parent, tokens[-1]


def _apply_set(parent: Any, key: str, value: Any) -> None:
    if isinstance(parent, dict):
        parent[key] = value
        return
    if isinstance(parent, list):
        idx = int(key)
        if idx < 0 or idx >= len(parent):
            raise RequirementOpsError("Index out of range for set operation")
        parent[idx] = value
        return
    raise RequirementOpsError("Target for set is not a container")


def _apply_add(parent: Any, key: str, value: Any) -> None:
    if isinstance(parent, dict):
        if key in parent:
            raise RequirementOpsError("Key already exists for add operation")
        parent[key] = value
        return
    if isinstance(parent, list):
        if key == "-":  # append
            parent.append(value)
            return
        idx = int(key)
        if idx < 0 or idx > len(parent):
            raise RequirementOpsError("Index out of range for add operation")
        parent.insert(idx, value)
        return
    raise RequirementOpsError("Target for add is not a container")


def _apply_remove(parent: Any, key: str) -> None:
    if isinstance(parent, dict):
        if key not in parent:
            raise RequirementOpsError("Key does not exist for remove operation")
        del parent[key]
        return
    if isinstance(parent, list):
        idx = int(key)
        if idx < 0 or idx >= len(parent):
            raise RequirementOpsError("Index out of range for remove operation")
        parent.pop(idx)
        return
    raise RequirementOpsError("Target for remove is not a container")


def _enforce_title_minimal_change(old_title: str, new_title: str) -> None:
    """Guardrail for title edits to prevent embellishment.

    Policy:
    - allow exact swap Internal->External when present
    - additionally allow "External Dashboard" as a minimal absolute title
    - otherwise reject
    """
    if not isinstance(old_title, str) or not isinstance(new_title, str):
        raise RequirementOpsError("Title must be a string")

    if old_title.replace("Internal", "External") == new_title:
        return
    if new_title.strip() == "External Dashboard":
        return
    raise RequirementOpsError(
        "Title edit rejected by strict policy (non-minimal change detected)"
    )


def _coerce_amount(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        digits = value.replace("$", "").replace(",", "").strip()
        return int(float(digits or 0))
    raise RequirementOpsError("Invalid amount value type")


def _postprocess(requirements: Dict[str, Any]) -> Dict[str, Any]:
    # Normalize numeric shapes but keep machine-friendly types (do NOT format to strings here)
    pricing = requirements.get("pricing_breakdown")
    if isinstance(pricing, list):
        normalized: List[Dict[str, Any]] = []
        for item in pricing:
            if not isinstance(item, dict):
                continue
            amt = item.get("amount")
            try:
                n = _coerce_amount(amt)
                item["amount"] = n
            except RequirementOpsError:
                # leave as is if it cannot be coerced
                pass
            normalized.append(item)
        requirements["pricing_breakdown"] = normalized
    return requirements


def apply_ops(
    requirements: Dict[str, Any],
    ops: List[Dict[str, Any]],
    *,
    allowed_paths: Optional[Iterable[str]] = None,
    strict_title: bool = True,
) -> Dict[str, Any]:
    """Apply a list of small, typed operations to requirements.

    Raises RequirementOpsError on any invalid or unsafe operation.
    Returns a new requirements dict.
    """
    if not isinstance(requirements, dict):
        raise RequirementOpsError("Requirements must be an object")
    allowed_prefixes = _normalize_allowed_paths(allowed_paths)

    # Create a deep copy without importing heavy libs
    working = json.loads(json.dumps(requirements))

    for i, raw in enumerate(ops or []):
        if not isinstance(raw, dict):
            raise RequirementOpsError(f"Invalid op at index {i}")
        op_type = str(raw.get("type") or raw.get("op") or "").lower()
        pointer = raw.get("path")
        value = raw.get("value")

        if op_type not in {"set", "add", "remove"}:
            raise RequirementOpsError(f"Unsupported op type: {op_type}")
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            raise RequirementOpsError(f"Invalid op path: {pointer}")
        if not _path_is_allowed(pointer, allowed_prefixes):
            raise RequirementOpsError(f"Path not allowed: {pointer}")

        # Title guard
        if strict_title and pointer == "/title" and op_type in {"set", "add"}:
            old_title = str(working.get("title", ""))
            _enforce_title_minimal_change(old_title, str(value))

        parent, key = _resolve_pointer(working, pointer)
        if op_type == "set":
            _apply_set(parent, key, value)
        elif op_type == "add":
            _apply_add(parent, key, value)
        elif op_type == "remove":
            _apply_remove(parent, key)

    return _postprocess(working)


