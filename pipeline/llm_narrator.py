"""
Optional LLM narrator: compresses canonical_summary_v1 into 3 lines only.
Contract: Input is ONLY canonical_summary_v1. No raw lead, no HTML, no new numbers/tiers/fields.
Output: executive_summary_1liner, outreach_angle_1liner, objections_1liner. JSON only; numbers must exist in input.
Feature flag: ENABLE_NARRATOR=true. If disabled, UI works normally.
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

ALLOWED_KEYS = {"executive_summary_1liner", "outreach_angle_1liner", "objections_1liner"}

# Reject output containing these phrases (hedging / hallucination risk)
DISALLOWED_PHRASES = (
    "approximately",
    "around",
    "likely",
    "probably",
    "appears",
    "it seems",
)


def _extract_numbers_from_text(text: str) -> set:
    """Return set of numeric values (int/float) mentioned in text (e.g. 50, 1.5, 300000)."""
    if not text or not isinstance(text, str):
        return set()
    numbers = set()
    for m in re.findall(r"\$?[\d,]+(?:\.\d+)?%?", text):
        clean = m.replace("$", "").replace(",", "").replace("%", "")
        try:
            v = float(clean)
            numbers.add(v)
            numbers.add(int(v))
        except ValueError:
            pass
    return numbers


def _numbers_in_canonical(canonical_summary_v1: Dict) -> set:
    """Collect all numeric values present in canonical_summary_v1 (allowed in LLM output)."""
    allowed = set()
    if not canonical_summary_v1:
        return allowed

    def collect(d: Any) -> None:
        if isinstance(d, (int, float)):
            allowed.add(d)
            allowed.add(int(d) if isinstance(d, float) and d == int(d) else d)
        elif isinstance(d, dict):
            for v in d.values():
                collect(v)
        elif isinstance(d, list):
            for x in d:
                collect(x)
        elif isinstance(d, str) and d.replace(".", "").replace(",", "").replace("$", "").replace("%", "").isdigit():
            try:
                allowed.add(float(d.replace(",", "")))
            except ValueError:
                pass

    collect(canonical_summary_v1)
    return allowed


def _contains_disallowed_phrase(text: str) -> bool:
    """True if text contains any DISALLOWED_PHRASES (hedging/hallucination)."""
    if not text or not isinstance(text, str):
        return False
    lower = text.lower()
    return any(phrase in lower for phrase in DISALLOWED_PHRASES)


def _validate_narrator_output(parsed: Dict, allowed_numbers: set) -> bool:
    """Reject if output contains numbers not in allowed set, unknown keys, or disallowed phrases."""
    if not isinstance(parsed, dict):
        return False
    for key in parsed:
        if key not in ALLOWED_KEYS:
            return False
    text = " ".join(str(v) for v in parsed.values() if isinstance(v, str))
    found = _extract_numbers_from_text(text)
    disallowed_numbers = found - allowed_numbers
    if disallowed_numbers:
        logger.warning("LLM narrator introduced numbers not in input: %s", disallowed_numbers)
        return False
    if _contains_disallowed_phrase(text):
        logger.warning("LLM narrator output contained disallowed hedging phrase")
        return False
    return True


def narrate_from_canonical(
    canonical_summary_v1: Dict[str, Any],
    temperature: float = 0.2,
    max_tokens: int = 300,
) -> Optional[Dict[str, Any]]:
    """
    Optional LLM: compress canonical_summary_v1 into 3 lines. No numbers/tiers/signals invented.
    Input: ONLY canonical_summary_v1. Output: executive_summary_1liner, outreach_angle_1liner, objections_1liner.
    Returns None if ENABLE_NARRATOR not set, no API key, or validation fails. Does not block pipeline.
    """
    if os.getenv("ENABLE_NARRATOR", "").strip().lower() not in ("1", "true", "yes"):
        return None
    if not os.getenv("OPENAI_API_KEY"):
        return None
    if temperature > 0.2:
        temperature = 0.2

    # Build prompt from canonical_summary_v1 only (no raw lead, no HTML)
    s = canonical_summary_v1 or {}
    parts = []
    parts.append(f"Worth pursuing: {s.get('worth_pursuing')} - {(s.get('worth_pursuing_reason') or '')[:100]}")
    parts.append(f"Root constraint: {s.get('root_constraint')}")
    parts.append(f"Right lever: {(s.get('right_lever_summary') or '')[:80]}")
    parts.append(f"Market: {(s.get('market_position_one_line') or '')[:80]}")
    parts.append(f"Confidence: {s.get('confidence_summary')}")
    monthly = s.get("traffic_estimate_monthly") or {}
    lo, hi = monthly.get("lower"), monthly.get("upper")
    if lo is not None and hi is not None:
        parts.append(f"Traffic: {lo}-{hi} visits/month")
    paid = s.get("paid_clicks_estimate_monthly")
    if paid and isinstance(paid, dict):
        plo, phi = paid.get("lower"), paid.get("upper")
        if plo is not None and phi is not None:
            parts.append(f"Paid: {plo}-{phi} clicks/month")
    eff = s.get("traffic_efficiency_score")
    if eff is not None:
        parts.append(f"Traffic efficiency score: {eff}")

    prompt_text = "\n".join(parts)[:1000]
    allowed_numbers = _numbers_in_canonical(canonical_summary_v1)

    try:
        from openai import OpenAI
        client = OpenAI()
    except ImportError:
        return None

    system = (
        "You write 1–2 sentence lines for a dental agency. Reply with JSON only. "
        "Keys: executive_summary_1liner, outreach_angle_1liner, objections_1liner. "
        "Do not invent numbers or stats. Use only information from the input. No new fields."
    )
    user = f"Summarize this lead snapshot into the three lines (JSON only):\n{prompt_text}"

    try:
        r = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        raw = (r.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw).strip()
            raw = re.sub(r"\n?```$", "", raw).strip()
        parsed = json.loads(raw)
        if not _validate_narrator_output(parsed, allowed_numbers):
            return None
        return {
            "executive_summary_1liner": (parsed.get("executive_summary_1liner") or "")[:500],
            "outreach_angle_1liner": (parsed.get("outreach_angle_1liner") or "")[:500],
            "objections_1liner": (parsed.get("objections_1liner") or "")[:500],
        }
    except Exception as e:
        logger.debug("LLM narrator failed: %s", e)
        return None
