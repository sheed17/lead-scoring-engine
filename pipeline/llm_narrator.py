"""
Optional LLM narrator: narrative compression from canonical summary_60s only.
Contract: summary_60s is the ONLY source. No raw lead fields, no HTML, no external scraping.
Input: canonical summary_60s. Output: strict JSON (1–2 sentences each).
Temperature <= 0.2, small max tokens. Hard no-hallucination: reject unknown numbers and DISALLOWED_PHRASES.
UI works without this; feature-flagged.
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


def _numbers_in_canonical(summary_60s: Dict) -> set:
    """Collect all numeric values present in the canonical summary (allowed in LLM output)."""
    allowed = set()
    if not summary_60s:
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

    collect(summary_60s)
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
    summary_60s: Dict[str, Any],
    temperature: float = 0.2,
    max_tokens: int = 300,
) -> Optional[Dict[str, Any]]:
    """
    Optional LLM: compress canonical summary into 1–2 sentence lines.
    Input: ONLY canonical summary_60s (no raw lead, no HTML, no scraping). Output: executive_summary_1liner, outreach_angle_1liner, objections_1liner.
    Returns None if disabled, no API key, or validation fails. Does not block pipeline.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return None
    if temperature > 0.2:
        temperature = 0.2

    # Build prompt from canonical summary_60s only (no raw lead, no HTML, no scraping)
    parts = []
    parts.append(f"Worth pursuing: {summary_60s.get('worth_pursuing')} - {summary_60s.get('worth_pursuing_reason', '')[:100]}")
    parts.append(f"Root constraint: {summary_60s.get('root_constraint')}")
    parts.append(f"Right lever: {summary_60s.get('right_lever_summary', '')[:80]}")
    parts.append(f"Market: {summary_60s.get('market_position_one_line', '')[:80]}")
    parts.append(f"Confidence: {summary_60s.get('confidence_summary')}")
    cost_leakage = summary_60s.get("cost_leakage_signals") or []
    if cost_leakage:
        parts.append("Leakage: " + "; ".join(cost_leakage[:3]))

    # Traffic narrator integration: explicit traffic numbers so LLM may reference but not invent
    traffic_est = summary_60s.get("traffic_estimate") or {}
    monthly = traffic_est.get("traffic_estimate_monthly") or {}
    lo = monthly.get("lower")
    hi = monthly.get("upper")
    conf = monthly.get("confidence")
    if lo is not None and hi is not None:
        parts.append(f"Traffic: {lo}-{hi} visits/month (confidence {conf})")
    paid_clicks = traffic_est.get("paid_clicks_estimate_monthly")
    if paid_clicks and isinstance(paid_clicks, dict):
        plo = paid_clicks.get("lower")
        phi = paid_clicks.get("upper")
        if plo is not None and phi is not None:
            parts.append(f"Paid: {plo}-{phi} clicks/month")
    eff = traffic_est.get("traffic_efficiency_interpretation")
    if eff:
        parts.append(f"Efficiency: {eff}")
    traffic_conf = traffic_est.get("traffic_confidence_score")
    if traffic_conf is not None:
        parts.append(f"Traffic confidence: {traffic_conf}")

    prompt_text = "\n".join(parts)[:1000]

    # Whitelist: only numbers present in canonical summary (LLM may reference, may not generate new)
    allowed_numbers = _numbers_in_canonical(summary_60s)

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
