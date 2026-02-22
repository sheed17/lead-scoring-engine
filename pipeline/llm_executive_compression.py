"""
Optional single LLM call: executive_summary (2–3 sentences) and outreach_angle.

Inputs only: primary_constraint, revenue_gap, cost_leakage_signals, service_focus.
No additional reasoning. Temperature 0, minimal tokens.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT = 30
MAX_TOKENS = 400

SYSTEM_PROMPT = """You are a compression layer. Output ONLY valid JSON with two keys:
- "executive_summary": 2–3 sentences max. No SEO jargon. Revenue/constraint focused.
- "outreach_angle": 1–2 sentences. How to pitch this practice. No markdown, no other text."""

USER_PROMPT_TEMPLATE = """Based strictly on these inputs, output JSON only:
- executive_summary: 2-3 sentences
- outreach_angle: 1-2 sentences

Inputs:
Primary constraint: {primary_constraint}
Revenue gap (annual): {revenue_gap}
Cost leakage signals: {cost_leakage}
Service focus (emphasized): {service_focus}
"""


def _get_client():
    try:
        from openai import OpenAI
        return OpenAI()
    except ImportError:
        return None


def build_executive_summary_and_outreach(
    primary_constraint: str,
    revenue_gap: Optional[Dict[str, Any]] = None,
    cost_leakage_signals: Optional[List[str]] = None,
    service_focus: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Optional LLM call. Returns { "executive_summary": "", "outreach_angle": "" }.
    Returns empty strings on missing API key or failure.
    """
    out = {"executive_summary": "", "outreach_angle": ""}
    if not primary_constraint:
        return out

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return out

    client = _get_client()
    if not client:
        return out

    gap_str = "Not estimated"
    if revenue_gap and isinstance(revenue_gap, dict):
        lo, hi = revenue_gap.get("lower"), revenue_gap.get("upper")
        if lo is not None and hi is not None:
            gap_str = f"${lo:,}–${hi:,} annual"
        elif lo is not None:
            gap_str = f"${lo:,}+ annual"

    leakage = cost_leakage_signals or []
    leakage_str = "; ".join(leakage[:5]) if leakage else "None"

    focus_parts = []
    if service_focus and isinstance(service_focus, dict):
        for k, v in (service_focus or {}).items():
            if isinstance(v, dict) and v.get("emphasized"):
                focus_parts.append(k)
    service_focus_str = ", ".join(focus_parts) if focus_parts else "General"

    user = USER_PROMPT_TEMPLATE.format(
        primary_constraint=primary_constraint[:500],
        revenue_gap=gap_str,
        cost_leakage=leakage_str[:400],
        service_focus=service_focus_str,
    )

    try:
        model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        r = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            temperature=0,
            max_tokens=MAX_TOKENS,
            timeout=REQUEST_TIMEOUT,
        )
        text = (r.choices[0].message.content or "").strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        data = json.loads(text)
        out["executive_summary"] = (data.get("executive_summary") or "").strip()[:800]
        out["outreach_angle"] = (data.get("outreach_angle") or "").strip()[:500]
        return out
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning("Executive compression LLM parse error: %s", e)
        return out
    except Exception as e:
        logger.warning("Executive compression LLM request failed: %s", e)
        return out
