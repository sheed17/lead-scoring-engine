"""
Sales & Intervention Intelligence Layer.

Turns lead + dentist_profile + verdict into sales-grade reasoning and execution guidance:
- Executive sales summary (readable on a call, no SEO jargon, revenue-risk framing)
- Primary conversation anchor (ONE issue to lead with)
- Intervention prioritization plan (SEO | CRO | Reputation)
- Access request logic (what to ask for, when, why)
- Objection anticipation
- Go-to-market recommendation (Direct | Agency | Defer)
- Outcome learning hooks (placeholders for future model learning)

Read-only: does not change scores or signals. Consumes existing data only.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT = 60

SYSTEM_PROMPT = """You are a senior sales consultant for an SEO/CRO agency that sells to dental practices.
Your job is to help the sales team diagnose problems, prioritize one conversation anchor, and guide onboarding—not to add more SEO metrics.

Rules:
- Think like a top-performing sales consultant: diagnose, prioritize, guide.
- Use NO SEO jargon (no "rankings", "SERP", "backlinks", "keywords"). Frame around revenue risk and patient flow.
- Do NOT promise outcomes. Be specific to THIS business using only the provided signals.
- Choose exactly ONE primary issue to lead the conversation. Salespeople must NOT pitch everything at once.
- Be concise, credible, and actionable. Tone: calm, consultative, not salesy."""

USER_PROMPT_TEMPLATE = """Using the following business intelligence for a dental practice, generate the Sales & Intervention Intelligence.

You must respond with a single JSON object only (no markdown, no other text). Use exactly this structure:

{
  "executive_sales_summary": "One short paragraph a salesperson could read on a call. No SEO jargon. Frame around revenue risk / demand not converting. Specific to this business.",
  "primary_sales_anchor": {
    "issue": "Exactly one issue to lead with (e.g. review reputation suppressing visibility, paid ads waste due to trust gaps, booking friction, missing high-intent pages)",
    "why_this_first": "Why lead with this issue for this practice",
    "what_happens_if_ignored": "Revenue/patient impact if they do nothing",
    "confidence": 0.0
  },
  "intervention_plan": [
    {
      "priority": 1,
      "action": "Short action description",
      "category": "SEO | CRO | Reputation",
      "why_now": "Why this matters now",
      "expected_impact": "Directional impact (e.g. more calls, fewer drop-offs)",
      "time_to_signal_days": 30,
      "confidence": 0.0
    }
  ],
  "required_access": [
    {
      "access_type": "e.g. Google Business Profile – Manager",
      "why_needed": "Brief reason",
      "risk_level": "Low | Medium | High",
      "when_to_ask": "e.g. After initial agreement"
    }
  ],
  "likely_objections": [
    {
      "objection": "What they might say",
      "suggested_response": "Short, calm, non-salesy answer"
    }
  ],
  "go_to_market_recommendation": {
    "best_path": "Direct | Agency | Defer",
    "why": ["Reason 1", "Reason 2"],
    "risk_flags": ["Any flags"],
    "confidence": 0.0
  },
  "outcome_learning_hooks": {
    "access_granted": null,
    "intervention_applied": null,
    "booking_lift_observed": null,
    "time_to_first_signal_days": null
  }
}

- executive_sales_summary: 2–4 sentences, verbatim-ready for a call.
- primary_sales_anchor: ONE issue only. confidence 0–1.
- intervention_plan: 3–6 items, ranked. category must be exactly "SEO", "CRO", or "Reputation". time_to_signal_days a number.
- required_access: 1–4 items. Minimum access needed for the interventions.
- likely_objections: 2–5 items based on signals (e.g. "We already run ads", "Reviews are out of our control").
- go_to_market_recommendation: best_path exactly "Direct", "Agency", or "Defer". why and risk_flags arrays.
- outcome_learning_hooks: leave all four fields as null (for future logging).

Here is the data:
{{STRUCTURED_JSON}}"""


def _get_client():
    try:
        from openai import OpenAI
        return OpenAI()
    except ImportError:
        return None


def _build_input(
    business_snapshot: Dict[str, Any],
    dentist_profile_v1: Dict[str, Any],
    context_dimensions: List[Dict],
    verdict: Optional[str],
    confidence: Optional[float],
    llm_reasoning_layer: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Build input for the sales LLM (no raw HTML)."""
    snapshot = {
        "name": business_snapshot.get("name"),
        "place_id": business_snapshot.get("place_id"),
        "signal_rating": business_snapshot.get("signal_rating"),
        "signal_review_count": business_snapshot.get("signal_review_count"),
        "signal_has_website": business_snapshot.get("signal_has_website"),
        "signal_has_automated_scheduling": business_snapshot.get("signal_has_automated_scheduling"),
        "signal_has_phone": business_snapshot.get("signal_has_phone"),
        "signal_has_contact_form": business_snapshot.get("signal_has_contact_form"),
        "signal_review_summary_text": (business_snapshot.get("signal_review_summary_text") or "")[:1500],
        "signal_last_review_days_ago": business_snapshot.get("signal_last_review_days_ago"),
        "signal_runs_paid_ads": business_snapshot.get("signal_runs_paid_ads"),
    }
    payload = {
        "business_snapshot": snapshot,
        "dentist_profile_v1": dentist_profile_v1,
        "context_dimensions": context_dimensions[:20],
        "verdict": verdict,
        "confidence": confidence,
    }
    if llm_reasoning_layer and isinstance(llm_reasoning_layer, dict):
        payload["llm_reasoning_layer"] = {
            "executive_summary": llm_reasoning_layer.get("executive_summary"),
            "recommended_outreach_angle": llm_reasoning_layer.get("recommended_outreach_angle"),
        }
    return payload


def _ensure_list(val: Any, max_items: int = 15) -> List[Any]:
    if isinstance(val, list):
        return list(val)[:max_items]
    return []


def _normalize_primary_anchor(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        return {"issue": "", "why_this_first": "", "what_happens_if_ignored": "", "confidence": 0.0}
    return {
        "issue": str(obj.get("issue") or "").strip(),
        "why_this_first": str(obj.get("why_this_first") or "").strip(),
        "what_happens_if_ignored": str(obj.get("what_happens_if_ignored") or "").strip(),
        "confidence": _clamp_confidence(obj.get("confidence")),
    }


def _normalize_intervention_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    cat = str(item.get("category") or "").strip().upper()
    if "CRO" in cat or cat == "CRO":
        cat = "CRO"
    elif "REPUTATION" in cat or "REVIEW" in cat:
        cat = "Reputation"
    else:
        cat = "SEO"
    return {
        "priority": int(item["priority"]) if isinstance(item.get("priority"), (int, float)) else 0,
        "action": str(item.get("action") or "").strip(),
        "category": cat,
        "why_now": str(item.get("why_now") or "").strip(),
        "expected_impact": str(item.get("expected_impact") or "").strip(),
        "time_to_signal_days": int(item["time_to_signal_days"]) if isinstance(item.get("time_to_signal_days"), (int, float)) else 30,
        "confidence": _clamp_confidence(item.get("confidence")),
    }


def _normalize_access_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    return {
        "access_type": str(item.get("access_type") or "").strip(),
        "why_needed": str(item.get("why_needed") or "").strip(),
        "risk_level": str(item.get("risk_level") or "Low").strip(),
        "when_to_ask": str(item.get("when_to_ask") or "").strip(),
    }


def _normalize_objection_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    return {
        "objection": str(item.get("objection") or "").strip(),
        "suggested_response": str(item.get("suggested_response") or "").strip(),
    }


def _normalize_gtm(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        return {"best_path": "Direct", "why": [], "risk_flags": [], "confidence": 0.0}
    path = str(obj.get("best_path") or "Direct").strip()
    if path not in ("Direct", "Agency", "Defer"):
        path = "Direct"
    return {
        "best_path": path,
        "why": _ensure_list(obj.get("why"), 5),
        "risk_flags": _ensure_list(obj.get("risk_flags"), 5),
        "confidence": _clamp_confidence(obj.get("confidence")),
    }


def _clamp_confidence(val: Any) -> float:
    if isinstance(val, (int, float)):
        return round(max(0.0, min(1.0, float(val))), 2)
    return 0.0


def _outcome_hooks_template() -> Dict[str, Optional[Any]]:
    return {
        "access_granted": None,
        "intervention_applied": None,
        "booking_lift_observed": None,
        "time_to_first_signal_days": None,
    }


def build_sales_intervention_intelligence(
    business_snapshot: Dict[str, Any],
    dentist_profile_v1: Dict[str, Any],
    context_dimensions: Optional[List[Dict]] = None,
    verdict: Optional[str] = None,
    confidence: Optional[float] = None,
    llm_reasoning_layer: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Generate Sales & Intervention Intelligence for a dental lead.

    Returns a structure with:
    - executive_sales_summary
    - primary_sales_anchor
    - intervention_plan
    - required_access
    - likely_objections
    - go_to_market_recommendation
    - outcome_learning_hooks

    Returns {} on missing API key, parse error, or invalid response.
    """
    if not dentist_profile_v1:
        return {}
    if os.getenv("USE_LLM_SALES_INTERVENTION", "").strip().lower() not in ("1", "true", "yes"):
        return {}
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set; skipping sales intervention intelligence")
        return {}

    client = _get_client()
    if not client:
        logger.warning("openai package not installed; skipping sales intervention intelligence")
        return {}

    payload = _build_input(
        business_snapshot,
        dentist_profile_v1,
        context_dimensions or [],
        verdict,
        confidence,
        llm_reasoning_layer,
    )
    structured_json = json.dumps(payload, indent=2, default=str)
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

        # Normalize and validate
        primary = _normalize_primary_anchor(data.get("primary_sales_anchor"))
        intervention_raw = _ensure_list(data.get("intervention_plan"), 10)
        intervention_plan = [_normalize_intervention_item(x) for x in intervention_raw if _normalize_intervention_item(x)]
        intervention_plan.sort(key=lambda x: x.get("priority", 0))
        for i, item in enumerate(intervention_plan):
            item["priority"] = i + 1

        access_raw = _ensure_list(data.get("required_access"), 6)
        required_access = [_normalize_access_item(x) for x in access_raw if _normalize_access_item(x).get("access_type")]

        objections_raw = _ensure_list(data.get("likely_objections"), 8)
        likely_objections = [_normalize_objection_item(x) for x in objections_raw if _normalize_objection_item(x).get("objection")]

        gtm = _normalize_gtm(data.get("go_to_market_recommendation"))
        outcome_hooks = data.get("outcome_learning_hooks")
        if isinstance(outcome_hooks, dict):
            outcome_hooks = {k: outcome_hooks.get(k) for k in _outcome_hooks_template()}
        else:
            outcome_hooks = _outcome_hooks_template()

        return {
            "executive_sales_summary": str(data.get("executive_sales_summary") or "").strip(),
            "primary_sales_anchor": primary,
            "intervention_plan": intervention_plan,
            "required_access": required_access,
            "likely_objections": likely_objections,
            "go_to_market_recommendation": gtm,
            "outcome_learning_hooks": outcome_hooks,
        }
    except json.JSONDecodeError as e:
        logger.warning("Sales intervention LLM parse error: %s; discarding", e)
        return {}
    except Exception as e:
        logger.warning("Sales intervention LLM request failed: %s; discarding", e)
        return {}
