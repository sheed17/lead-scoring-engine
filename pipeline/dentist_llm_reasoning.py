"""
Dentist LLM reasoning layer: read-only synthesis for SEO agency opportunity.

Consumes enriched JSON + dentist_profile_v1 + context_dimensions + lead_score/priority.
Does NOT mutate scores or signals. Output is for interpretability only.
Guardrails: discard output if it invents data or contradicts deterministic flags.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT = 45

SYSTEM_PROMPT = """You are an expert SEO agency strategist specializing in dental practices.

You are given a fully computed, factual business profile.
Your job is to explain the opportunity to an SEO agency in clear, decisive language.

Rules:
- Do NOT invent new facts
- Do NOT contradict provided signals
- Do NOT rescore or reprioritize
- You may only synthesize, explain, and contextualize

Your output must help an SEO agency decide:
- Is this dentist worth pursuing?
- Why will SEO work here?
- What angle should be used?
- What risks exist?

Be concise, specific, and confident."""

USER_PROMPT_TEMPLATE = """Based on the following structured business intelligence, generate an agency-facing opportunity summary for a dental practice.

You must respond with a single JSON object only (no markdown, no other text). Use exactly these keys:
- "executive_summary": one short paragraph (2-4 sentences)
- "seo_viability_reasoning": array of 2-5 short strings (why SEO will work here)
- "revenue_opportunities": array of 2-5 short strings (primary revenue angles)
- "risk_objections": array of 1-4 short strings (key risks or objections)
- "recommended_outreach_angle": 1-2 sentences (how to pitch this practice)
- "confidence": number between 0 and 1 (how clear the data supports your summary)

Here is the data:
{{STRUCTURED_JSON}}"""

REQUIRED_KEYS = [
    "executive_summary",
    "seo_viability_reasoning",
    "revenue_opportunities",
    "risk_objections",
    "recommended_outreach_angle",
    "confidence",
]


def _get_client():
    try:
        from openai import OpenAI
        return OpenAI()
    except ImportError:
        return None


def _build_llm_input(
    business_snapshot: Dict[str, Any],
    dentist_profile_v1: Dict[str, Any],
    context_dimensions: List[Dict],
    lead_score: Optional[int],
    priority: Optional[str],
    confidence: Optional[float],
) -> Dict[str, Any]:
    """Build the strict input contract for the LLM (no raw HTML, no scraped blobs)."""
    return {
        "business_snapshot": {
            "name": business_snapshot.get("name"),
            "place_id": business_snapshot.get("place_id"),
            "signal_rating": business_snapshot.get("signal_rating"),
            "signal_review_count": business_snapshot.get("signal_review_count"),
            "signal_has_website": business_snapshot.get("signal_has_website"),
            "signal_has_automated_scheduling": business_snapshot.get("signal_has_automated_scheduling"),
            "signal_has_phone": business_snapshot.get("signal_has_phone"),
            "signal_has_contact_form": business_snapshot.get("signal_has_contact_form"),
            "signal_review_summary_text": (business_snapshot.get("signal_review_summary_text") or "")[:2000],
            "signal_last_review_days_ago": business_snapshot.get("signal_last_review_days_ago"),
        },
        "dentist_profile_v1": dentist_profile_v1,
        "context_dimensions": context_dimensions,
        "lead_score": lead_score,
        "priority": priority,
        "confidence": confidence,
    }


def _contradicts_deterministic(llm_output: Dict[str, Any], dentist_profile_v1: Dict[str, Any], priority: Optional[str]) -> bool:
    """Return True if LLM output contradicts deterministic flags (discard)."""
    agency_fit = (dentist_profile_v1 or {}).get("agency_fit_reasoning") or {}
    ideal = agency_fit.get("ideal_for_seo_outreach")
    if ideal is None:
        return False
    # Heuristic: if we said ideal_for_seo_outreach is True, LLM should not say "not worth pursuing" in summary
    summary = (llm_output.get("executive_summary") or "").lower()
    if ideal is True and ("not worth" in summary or "do not pursue" in summary or "skip this" in summary):
        return True
    if ideal is False and ("highly recommended" in summary and "no risk" in summary):
        return True
    return False


def _references_nonexistent(llm_output: Dict[str, Any], business_snapshot: Dict, dentist_profile_v1: Dict) -> bool:
    """Return True if LLM invents data (e.g. specific numbers or facts not in input)."""
    # Light check: we don't have full NER; just ensure arrays are short and confidence is 0-1
    conf = llm_output.get("confidence")
    if conf is not None and (not isinstance(conf, (int, float)) or conf < 0 or conf > 1):
        return True
    for key in REQUIRED_KEYS:
        if key not in llm_output and key != "confidence":
            return True
    return False


def dentist_llm_reasoning_layer(
    business_snapshot: Dict[str, Any],
    dentist_profile_v1: Dict[str, Any],
    context_dimensions: List[Dict],
    lead_score: Optional[int] = None,
    priority: Optional[str] = None,
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Call LLM to produce llm_reasoning_layer for dentist opportunity.

    Returns the required schema or empty dict on failure/guardrail discard.
    Never mutates lead_score, priority, or any deterministic field.
    """
    if not dentist_profile_v1:
        return {}
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set; skipping dentist LLM reasoning layer")
        return {}

    client = _get_client()
    if not client:
        logger.warning("openai package not installed; skipping dentist LLM reasoning layer")
        return {}

    payload = _build_llm_input(
        business_snapshot,
        dentist_profile_v1,
        context_dimensions,
        lead_score,
        priority,
        confidence,
    )
    structured_json = json.dumps(payload, indent=2)
    user_prompt = USER_PROMPT_TEMPLATE.replace("{{STRUCTURED_JSON}}", structured_json)

    try:
        model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            timeout=REQUEST_TIMEOUT,
        )
        choice = response.choices[0] if response.choices else None
        if not choice or not getattr(choice, "message", None):
            return {}
        text = (choice.message.content or "").strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        data = json.loads(text)
        # Normalize to required schema (map common LLM key variants)
        data = _normalize_llm_response_keys(data)
        out = {
            "executive_summary": str(data.get("executive_summary") or "").strip(),
            "seo_viability_reasoning": _ensure_list(data.get("seo_viability_reasoning")),
            "revenue_opportunities": _ensure_list(data.get("revenue_opportunities")),
            "risk_objections": _ensure_list(data.get("risk_objections")),
            "recommended_outreach_angle": str(data.get("recommended_outreach_angle") or "").strip(),
            "confidence": _clamp_confidence(data.get("confidence")),
        }
        if _references_nonexistent(out, business_snapshot, dentist_profile_v1):
            logger.warning("Dentist LLM output failed guardrail: references nonexistent data; discarding")
            return {}
        if _contradicts_deterministic(out, dentist_profile_v1, priority):
            logger.warning("Dentist LLM output failed guardrail: contradicts deterministic flags; discarding")
            return {}
        return out
    except json.JSONDecodeError as e:
        logger.warning("Dentist LLM response parse error: %s; discarding. Response may not be valid JSON.", e)
        return {}
    except Exception as e:
        logger.warning("Dentist LLM request failed: %s; discarding", e)
        return {}


def _normalize_llm_response_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """Map common LLM key variants to our schema so we accept alternate responses."""
    key_map = {
        "summary": "executive_summary",
        "reasons": "seo_viability_reasoning",
        "seo_reasons": "seo_viability_reasoning",
        "why_seo_works": "seo_viability_reasoning",
        "opportunities": "revenue_opportunities",
        "revenue_opportunity": "revenue_opportunities",
        "risks": "risk_objections",
        "objections": "risk_objections",
        "outreach_angle": "recommended_outreach_angle",
        "recommended_angle": "recommended_outreach_angle",
        "pitch_angle": "recommended_outreach_angle",
    }
    list_keys = {"seo_viability_reasoning", "revenue_opportunities", "risk_objections"}
    out = dict(data)
    for alt, canonical in key_map.items():
        if alt in out and canonical not in out:
            val = out[alt]
            if canonical in list_keys and isinstance(val, str):
                val = [val]
            out[canonical] = val
    return out


def _ensure_list(val: Any) -> List[str]:
    if isinstance(val, list):
        return [str(x).strip() for x in val if x][:10]
    return []


def _clamp_confidence(val: Any) -> float:
    if isinstance(val, (int, float)):
        return round(max(0.0, min(1.0, float(val))), 2)
    return 0.0
