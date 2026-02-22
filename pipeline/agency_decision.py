"""
Canonical agency_decision_v1: single output object consumed by the UI.

summary_60s is built by pipeline.canonical_summary (single source of truth).
This module delegates to build_canonical_summary_60s and adds drilldown fields for debug.
"""

from typing import Dict, Any, Optional

from pipeline.canonical_summary import build_canonical_summary_60s


def build_agency_decision_v1(
    lead: Dict[str, Any],
    dentist_profile: Dict[str, Any],
    objective_layer: Dict[str, Any],
    revenue_intelligence: Dict[str, Any],
    llm_extraction: Optional[Dict[str, Any]] = None,
    executive_summary: Optional[str] = None,
    outreach_angle: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the single canonical agency_decision_v1 object for UI consumption.
    summary_60s is the single source of truth (from canonical_summary); all other keys are drilldown.
    """
    summary_60s = build_canonical_summary_60s(
        lead,
        dentist_profile,
        objective_layer,
        revenue_intelligence,
        lead.get("paid_intelligence"),
    )

    obj = objective_layer or {}
    rev = revenue_intelligence or {}
    root = obj.get("root_bottleneck_classification") or {}
    evidence = root.get("evidence") or []
    primary_anchor = obj.get("primary_sales_anchor") or {}
    intervention_plan = obj.get("intervention_plan") or []

    traffic_index = rev.get("traffic_index")
    if traffic_index is None:
        traffic_index = 0
    traffic_efficiency = rev.get("traffic_efficiency_score")
    if traffic_efficiency is None:
        traffic_efficiency = 50
    seo_sales_value = int(obj.get("seo_sales_value_score") or 50)
    seo_revenue_score = max(0, min(100, (seo_sales_value + traffic_efficiency) // 2))
    verdict = lead.get("verdict") or "LOW"
    if verdict == "HIGH" and seo_revenue_score >= 60:
        pipeline_tier = "High"
    elif verdict == "LOW" or seo_revenue_score < 40:
        pipeline_tier = "Low"
    else:
        pipeline_tier = "Medium"

    primary_constraint = (root.get("why_root_cause") or root.get("bottleneck") or "visibility_limited").replace("_", " ").title()
    cost_leakage = list(rev.get("cost_leakage_signals") or [])
    evidence_bullets = list(evidence)[:10] + cost_leakage[:5]
    evidence_bullets = evidence_bullets[:15]
    if not outreach_angle:
        outreach_angle = primary_anchor.get("issue") or f"Focus on {primary_constraint} to capture revenue upside."

    return {
        "summary_60s": summary_60s,
        "worth_pursuing": summary_60s["worth_pursuing"],
        "worth_pursuing_reason": summary_60s["worth_pursuing_reason"],
        "primary_revenue_driver": summary_60s["primary_revenue_driver"],
        "market_position_one_line": summary_60s["market_position_one_line"],
        "right_lever_summary": summary_60s["right_lever_summary"],
        "confidence_summary": summary_60s["confidence_summary"],
        "seo_revenue_score": seo_revenue_score,
        "pipeline_tier": pipeline_tier,
        "revenue_band_estimate": summary_60s["revenue_band"],
        "organic_revenue_gap_estimate": summary_60s["organic_revenue_gap_estimate"],
        "paid_spend_range_estimate": summary_60s["paid_spend_range_estimate"],
        "traffic_index": traffic_index,
        "traffic_estimate_tier": rev.get("traffic_estimate_tier") or "Low",
        "traffic_efficiency_score": traffic_efficiency,
        "traffic_efficiency_interpretation": rev.get("traffic_efficiency_interpretation") or "Moderate",
        "revenue_confidence_score": rev.get("revenue_confidence_score"),
        "model_versions": summary_60s["model_versions"],
        "primary_constraint": primary_constraint[:500],
        "primary_intervention": summary_60s["highest_leverage_move"],
        "cost_leakage_signals": summary_60s["cost_leakage_signals"],
        "evidence_bullets": evidence_bullets,
        "outreach_angle": (outreach_angle or "")[:500],
        "executive_summary": executive_summary or "",
    }
