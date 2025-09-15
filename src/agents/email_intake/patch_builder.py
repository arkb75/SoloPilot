"""Tiny JSON Patch (subset) applier for requirements edits.

Supported operations:
- replace on top-level paths: /title, /summary, /business_description, /project_type, /budget_amount

Notes:
- This operates on a shallow dict of requirements. It ignores unknown ops/paths.
- Values are validated/coerced where sensible (e.g., budget_amount -> int).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)

ALLOWED_PATHS = {
    "/title": "title",
    "/summary": "summary",
    "/business_description": "business_description",
    "/project_type": "project_type",
    "/budget_amount": "budget_amount",
}


def _coerce_value(key: str, value: Any) -> Any:
    """Coerce value types for specific fields.

    - budget_amount: attempt to parse numeric, else leave unchanged.
    """
    if key == "budget_amount":
        # Accept int/float or numeric string possibly with $ and commas
        try:
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str):
                cleaned = value.strip().replace("$", "").replace(",", "")
                if cleaned:
                    return int(float(cleaned))
        except Exception:
            logger.debug("Failed to coerce budget_amount from %r", value)
        return value
    return value


def apply_patches(requirements: Dict[str, Any], patches: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply a subset of JSON Patch operations to a requirements dict.

    Only supports 'replace' on a set of top-level paths defined in ALLOWED_PATHS.
    Unknown or invalid patches are ignored.
    """
    updated: Dict[str, Any] = dict(requirements or {})

    if not patches:
        return updated

    for p in patches:
        try:
            if not isinstance(p, dict):
                continue
            op = p.get("op")
            path = p.get("path")
            if op != "replace" or path not in ALLOWED_PATHS:
                continue
            key = ALLOWED_PATHS[path]
            value = _coerce_value(key, p.get("value"))
            updated[key] = value
        except Exception as e:
            logger.debug("Ignoring invalid patch %r due to %s", p, e)
            continue

    return updated

