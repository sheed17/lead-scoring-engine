"""
Deterministic Revenue Intelligence layer for dental SEO pipeline.

Uses revenue_model_v2 (tier-based revenue, capped gap, confidence) and
traffic_model_v3 (composite index, efficiency, debug components). Also computes
paid_spend_range_estimate and cost_leakage_signals. NO LLM calls.
"""

from typing import Dict, Any, List, Optional


def _has_high_ticket(high_ticket_procedures: List[Any]) -> bool:
    return bool(high_ticket_procedures and len(high_ticket_procedures) > 0)


def build_revenue_intelligence(
    context: Dict[str, Any],
    dentist_profile: Dict[str, Any],
    objective_layer: Dict[str, Any],
    pricing_page_detected: bool = False,
    paid_intelligence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute revenue intelligence using v2 revenue model and v3 traffic model (tier-based revenue, composite traffic with debug components).

    context: lead dict (signals, review_count, etc.)
    dentist_profile: dentist_profile_v1
    objective_layer: full objective_decision_layer (service_intelligence, etc.)
    pricing_page_detected: optional, from page texts or LLM extraction
    paid_intelligence: optional from Meta Ads Library (active_ads, high_ticket_focus, ad_duration_days)

    Returns: revenue_band_estimate, organic_revenue_gap_estimate (capped), paid_spend_range_estimate,
    traffic_index, traffic_estimate_tier, traffic_estimate_monthly, traffic_debug_components (v3),
    traffic_efficiency_score, traffic_efficiency_interpretation, revenue_confidence_score,
    cost_leakage_signals, model_versions.
    """
    from pipeline.revenue_model_v2 import compute_revenue_v2
    from pipeline.traffic_model_v3 import compute_traffic_v3

    obj = objective_layer or {}
    svc = obj.get("service_intelligence") or {}
    high_ticket = svc.get("high_ticket_procedures_detected") or []
    missing_pages = svc.get("missing_high_value_pages") or []

    revenue_out = compute_revenue_v2(
        context,
        dentist_profile,
        objective_layer,
        high_income_metro=False,
        pricing_page_detected=pricing_page_detected,
    )
    traffic_out = compute_traffic_v3(context, objective_layer)

    paid = paid_intelligence or {}
    if paid.get("high_ticket_focus") is True and (paid.get("ad_duration_days") or 0) > 45:
        revenue_out["revenue_confidence_score"] = min(
            100,
            revenue_out.get("revenue_confidence_score", 50) + 12,
        )

    ads_active = context.get("signal_runs_paid_ads") is True
    high_ticket_detected = _has_high_ticket(high_ticket)
    if ads_active and high_ticket_detected:
        paid_spend_range_estimate = "$3k–$10k"
    elif ads_active:
        paid_spend_range_estimate = "$1k–$4k"
    else:
        paid_spend_range_estimate = "Not detected"

    schema_present = bool(context.get("signal_has_schema_microdata")) or bool(
        context.get("signal_schema_types") or []
    )
    review_count = int(context.get("signal_review_count") or context.get("user_ratings_total") or 0)
    rating = context.get("signal_rating") or context.get("rating")
    strong_reviews = review_count >= 50 and rating is not None and float(rating) >= 4.3
    weak_schema = not schema_present

    cost_leakage_signals: List[str] = []
    if paid.get("high_ticket_focus") is True and missing_pages:
        cost_leakage_signals.append("High-ticket services promoted in ads but no dedicated landing pages")
    elif high_ticket_detected and missing_pages:
        cost_leakage_signals.append("High-ticket services offered but no dedicated landing pages")
    if ads_active and missing_pages:
        cost_leakage_signals.append("Paid ads running but high-value service pages missing")
    # Use booking_conversion_path when available (dentist-realistic); else fall back to automated_scheduling
    booking_path = context.get("signal_booking_conversion_path")
    has_online_booking = booking_path in ("Online booking (limited)", "Online booking (full)")
    if booking_path is None:
        has_online_booking = context.get("signal_has_automated_scheduling") is True
    if ads_active and not has_online_booking:
        cost_leakage_signals.append("Paid ads running but no online booking")
    if strong_reviews and weak_schema:
        cost_leakage_signals.append("Strong reviews but no schema markup for local visibility")

    return {
        "revenue_band_estimate": revenue_out["revenue_band_estimate"],
        "organic_revenue_gap_estimate": revenue_out["organic_revenue_gap_estimate"],
        "revenue_confidence_score": revenue_out["revenue_confidence_score"],
        "revenue_indicative_only": revenue_out.get("indicative_only", False),
        "revenue_reliability_grade": revenue_out.get("revenue_reliability_grade", "C"),
        "paid_spend_range_estimate": paid_spend_range_estimate,
        "traffic_index": traffic_out["traffic_index"],
        "traffic_estimate_tier": traffic_out["traffic_estimate_tier"],
        "traffic_estimate_monthly": traffic_out.get("traffic_estimate_monthly"),
        "paid_clicks_estimate_monthly": traffic_out.get("paid_clicks_estimate_monthly"),
        "traffic_confidence_score": traffic_out.get("traffic_confidence_score"),
        "traffic_efficiency_score": traffic_out["traffic_efficiency_score"],
        "traffic_efficiency_interpretation": traffic_out["traffic_efficiency_interpretation"],
        "traffic_assumptions": traffic_out.get("traffic_assumptions"),
        "paid_clicks_assumptions": traffic_out.get("paid_clicks_assumptions"),
        "traffic_debug_components": traffic_out.get("traffic_debug_components"),
        "cost_leakage_signals": cost_leakage_signals,
        "model_versions": {
            "revenue_model": revenue_out["model_version"],
            "traffic_model": traffic_out["model_version"],
        },
    }


def build_revenue_intelligence_from_lead(
    lead: Dict[str, Any],
    service_intelligence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Backward-compatible wrapper: build from lead + service_intelligence
    by constructing a minimal objective_layer and dentist_profile.
    """
    obj = {"service_intelligence": service_intelligence or {}}
    profile = lead.get("dentist_profile_v1") or {}
    return build_revenue_intelligence(lead, profile, obj)
