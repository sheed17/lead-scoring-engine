"""
Revenue leverage analysis for dental leads.

Uses service_intelligence + signals to compute primary_revenue_driver_detected,
estimated_revenue_asymmetry, highest_leverage_growth_vector. Feeds root bottleneck and seo_best_lever.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

HIGH_ASYMMETRY_PROCEDURES = ["implant", "invisalign", "veneer", "cosmetic", "sedation", "emergency", "same day crown", "sleep apnea", "orthodontic"]


def build_revenue_leverage_analysis(
    lead: Dict,
    dentist_profile: Dict,
    service_intelligence: Dict[str, Any],
    competitive_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Returns revenue_leverage_analysis:
    - primary_revenue_driver_detected: implants | general | cosmetic | unknown
    - estimated_revenue_asymmetry: Low | Moderate | High
    - highest_leverage_growth_vector: one sentence
    - confidence
    """
    out = {
        "primary_revenue_driver_detected": "unknown",
        "estimated_revenue_asymmetry": "Low",
        "highest_leverage_growth_vector": "",
        "confidence": 0.0,
    }
    high_ticket = (service_intelligence.get("high_ticket_procedures_detected") or [])
    missing = (service_intelligence.get("missing_high_value_pages") or [])
    general = (service_intelligence.get("general_services_detected") or [])
    proc_conf = service_intelligence.get("procedure_confidence") or 0.0

    if any("implant" in str(p).lower() for p in high_ticket):
        out["primary_revenue_driver_detected"] = "implants"
    elif any(k in str(p).lower() for p in high_ticket for k in ["cosmetic", "veneer", "invisalign"]):
        out["primary_revenue_driver_detected"] = "cosmetic"
    elif general or high_ticket:
        out["primary_revenue_driver_detected"] = "general"

    # Asymmetry: high-ticket dedicated pages or strong high-ticket focus
    high_ticket_str = " ".join(str(p).lower() for p in high_ticket)
    has_high = any(k in high_ticket_str for k in HIGH_ASYMMETRY_PROCEDURES)
    if has_high and (len(high_ticket) >= 2 or len(missing) == 0):
        out["estimated_revenue_asymmetry"] = "High"
    elif has_high or len(missing) > 0:
        out["estimated_revenue_asymmetry"] = "Moderate"
    else:
        out["estimated_revenue_asymmetry"] = "Low"

    # Highest leverage growth vector (one sentence)
    if missing:
        first_miss = missing[0] if isinstance(missing[0], str) else str(missing[0])
        out["highest_leverage_growth_vector"] = f"Add dedicated service presence for {first_miss} to capture high-intent demand."
    elif out["estimated_revenue_asymmetry"] == "High":
        out["highest_leverage_growth_vector"] = "Strengthen visibility for existing high-ticket services in local search."
    elif out["primary_revenue_driver_detected"] == "general":
        out["highest_leverage_growth_vector"] = "Differentiate with targeted service pages or local positioning to improve capture."
    else:
        out["highest_leverage_growth_vector"] = "Clarify service focus and local visibility to improve demand capture."

    out["confidence"] = round(min(1.0, 0.3 + proc_conf * 0.5), 2)
    return out


def compute_seo_sales_value_score(
    lead: Dict,
    dentist_profile: Dict,
    service_intelligence: Dict[str, Any],
    competitive_snapshot: Dict[str, Any],
    revenue_leverage: Dict[str, Any],
    root_bottleneck: str,
    dcm: Dict[str, Any],
) -> int:
    """
    Internal prioritization score 0–100. Not shown to dentist.
    Increases: high asymmetry, weak visibility, below-median percentile, missing high-value pages, low competition.
    Decreases: saturation + strong reviews, no leverage, strong booking + ads + trust.
    """
    score = 50
    # + High revenue asymmetry
    if revenue_leverage.get("estimated_revenue_asymmetry") == "High":
        score += 15
    elif revenue_leverage.get("estimated_revenue_asymmetry") == "Moderate":
        score += 8
    # + Weak visibility
    if dcm.get("capture_signals", {}).get("status") == "Weak":
        score += 12
    elif dcm.get("capture_signals", {}).get("status") == "Moderate":
        score += 5
    # + Below sample average (no percentile from small samples)
    positioning = competitive_snapshot.get("review_positioning")
    if positioning == "Below sample average":
        score += 10
    elif positioning == "In line with sample average":
        score += 4
    # + Missing high-value pages
    missing = service_intelligence.get("missing_high_value_pages") or []
    if len(missing) >= 2:
        score += 10
    elif len(missing) == 1:
        score += 5
    # + Low competition / underpenetrated
    density = competitive_snapshot.get("market_density_score", "")
    if density == "Low":
        score += 8
    elif density == "Moderate":
        score += 2
    # - High saturation + strong reviews
    if root_bottleneck == "saturation_limited" and dcm.get("trust_signals", {}).get("status") == "Strong":
        score -= 25
    # - No revenue leverage
    if revenue_leverage.get("estimated_revenue_asymmetry") == "Low" and not missing:
        score -= 10
    # - Strong booking + strong ads + strong trust
    conv = dcm.get("conversion_signals", {}).get("status")
    trust = dcm.get("trust_signals", {}).get("status")
    if conv == "Strong" and trust == "Strong" and lead.get("signal_runs_paid_ads") is True:
        score -= 20
    return max(0, min(100, score))
