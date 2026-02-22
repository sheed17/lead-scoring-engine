"""
Layer B — Deterministic decision model. Produces ONE canonical object: canonical_summary_v1.

No verdicts/summaries/prose in Layer A; this layer is the single owner of:
worth_pursuing, root_constraint, primary_intervention (and thus pipeline tier).
All inputs from Layer A (signals, competitive_snapshot, service_intelligence, revenue_intelligence, objective_layer).
Fully deterministic, traceable, reproducible.
"""

from typing import Dict, Any, List, Optional

from pipeline.canonical_summary import (
    _compute_worth_pursuing,
    _market_position_one_line,
    _right_lever_summary,
    _confidence_summary,
)
from pipeline.evidence_registry import collect_evidence_ids


def build_canonical_summary_v1(
    signals: Dict[str, Any],
    competitive_snapshot: Dict[str, Any],
    service_intelligence: Dict[str, Any],
    revenue_intelligence: Dict[str, Any],
    objective_layer: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Produce canonical_summary_v1 — the single contract for UI. No duplicate fields, no debug duplication.

    Inputs: Layer A only (signals dict, competitive_snapshot, service_intelligence, revenue_intelligence, objective_layer).
    Output: worth_pursuing, worth_pursuing_reason, root_constraint, right_lever_summary, primary_intervention,
    revenue_band_estimate, organic_revenue_gap_estimate, traffic_estimate_monthly, paid_clicks_estimate_monthly,
    traffic_efficiency_score, market_position_one_line, confidence_summary, evidence_ids, model_versions.
    """
    obj = objective_layer or {}
    rev = revenue_intelligence or {}
    comp = competitive_snapshot or {}
    svc = service_intelligence or {}

    root = obj.get("root_bottleneck_classification") or {}
    seo_lever = obj.get("seo_lever_assessment") or {}
    bottleneck = root.get("bottleneck") or "visibility_limited"
    why_root = root.get("why_root_cause") or ""

    revenue_band_estimate = rev.get("revenue_band_estimate") or {}
    organic_revenue_gap_estimate = rev.get("organic_revenue_gap_estimate")
    traffic_efficiency = rev.get("traffic_efficiency_score")
    if traffic_efficiency is None:
        traffic_efficiency = 50
    revenue_confidence_score = rev.get("revenue_confidence_score")
    if revenue_confidence_score is None:
        revenue_confidence_score = 50
    model_versions = rev.get("model_versions") or {}

    seo_sales_value = int(obj.get("seo_sales_value_score") or 50)
    seo_revenue_score = max(0, min(100, (seo_sales_value + traffic_efficiency) // 2))
    verdict = signals.get("verdict") or "LOW"
    is_seo_primary = seo_lever.get("is_primary_growth_lever") is True
    alternative_lever = (seo_lever.get("alternative_primary_lever") or "").strip()

    worth_pursuing, worth_pursuing_reason = _compute_worth_pursuing(
        signals, bottleneck, why_root, is_seo_primary, alternative_lever,
        seo_revenue_score, verdict, revenue_confidence_score,
    )

    if worth_pursuing == "No" and organic_revenue_gap_estimate and isinstance(organic_revenue_gap_estimate, dict):
        organic_revenue_gap_estimate = None

    root_constraint = bottleneck.replace("_", " ").title()
    right_lever_summary = _right_lever_summary(seo_lever)
    market_position_one_line = _market_position_one_line(comp)
    confidence_summary = _confidence_summary(revenue_confidence_score, signals)

    intervention_plan = obj.get("intervention_plan") or []
    primary_anchor = obj.get("primary_sales_anchor") or {}
    first_intervention = intervention_plan[0] if intervention_plan else {}
    lever = first_intervention.get("action") or primary_anchor.get("issue") or "Improve local visibility and capture"
    rationale = first_intervention.get("expected_impact") or primary_anchor.get("why_this_first") or "Addresses root constraint."
    time_to_signal_days = first_intervention.get("time_to_signal_days")
    if time_to_signal_days is None or not isinstance(time_to_signal_days, (int, float)):
        time_to_signal_days = 30
    time_to_signal_days = int(time_to_signal_days)
    revenue_upside_estimate = None
    if organic_revenue_gap_estimate and isinstance(organic_revenue_gap_estimate, dict):
        revenue_upside_estimate = {
            "lower": organic_revenue_gap_estimate.get("lower"),
            "upper": organic_revenue_gap_estimate.get("upper"),
            "currency": organic_revenue_gap_estimate.get("currency", "USD"),
            "period": organic_revenue_gap_estimate.get("period", "annual"),
        }
    primary_intervention = {
        "lever": lever[:500] if isinstance(lever, str) else str(lever)[:500],
        "rationale": rationale[:500] if isinstance(rationale, str) else str(rationale)[:500],
        "time_to_signal_days": time_to_signal_days,
        "revenue_upside_estimate": revenue_upside_estimate,
    }

    traffic_estimate_monthly = rev.get("traffic_estimate_monthly")
    paid_clicks_estimate_monthly = rev.get("paid_clicks_estimate_monthly")

    evidence_ids = collect_evidence_ids(
        signals, comp, svc, rev, obj,
    )

    return {
        "worth_pursuing": worth_pursuing,
        "worth_pursuing_reason": worth_pursuing_reason,
        "root_constraint": root_constraint,
        "right_lever_summary": right_lever_summary,
        "primary_intervention": primary_intervention,
        "revenue_band_estimate": revenue_band_estimate,
        "organic_revenue_gap_estimate": organic_revenue_gap_estimate,
        "traffic_estimate_monthly": traffic_estimate_monthly,
        "paid_clicks_estimate_monthly": paid_clicks_estimate_monthly,
        "traffic_efficiency_score": traffic_efficiency,
        "market_position_one_line": market_position_one_line,
        "confidence_summary": confidence_summary,
        "evidence_ids": evidence_ids,
        "model_versions": model_versions,
    }
