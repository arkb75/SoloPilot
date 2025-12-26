"""Helpers for deriving proposal budget totals."""

from decimal import Decimal
import re
from typing import Any, Dict, Iterable, Optional


def _parse_amount(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    raw = str(value).strip()
    if not raw:
        return None

    multiplier = 1000 if "k" in raw.lower() else 1
    cleaned = raw.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        amount = float(match.group(0)) * multiplier
    except ValueError:
        return None
    return int(round(amount))


def _sum_pricing_items(pricing_items: Iterable[Dict[str, Any]]) -> Optional[int]:
    total = 0
    found = False
    for item in pricing_items:
        if not isinstance(item, dict):
            continue
        parsed = _parse_amount(item.get("amount"))
        if parsed is None:
            continue
        total += parsed
        found = True
    return total if found and total > 0 else None


def compute_budget_total(
    requirements: Optional[Dict[str, Any]],
    proposal_data: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    if requirements:
        total = _sum_pricing_items(requirements.get("pricing_breakdown") or [])
        if total:
            return total
        parsed_budget = _parse_amount(requirements.get("budget_amount"))
        if parsed_budget:
            return parsed_budget

    if proposal_data:
        total = _sum_pricing_items(proposal_data.get("pricing") or [])
        if total:
            return total

    return None
