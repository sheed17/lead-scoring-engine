"""
Sixty-second summary: one block per lead for 30–60 min research → 60 second decision.

All values derived from existing computed fields. No new APIs or LLM calls.
"""

from typing import Dict, Any


def build_sixty_second_summary(lead: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the sixty_second_summary block from existing lead fields only.

    Returns:
        {
            "pipeline_priority": "HIGH" | "MEDIUM" | "LOW",
            "primary_sales_anchor": str,
            "first_action": str,
            "competitors_sampled": int,
            "competitor_avg_review_count": float | None,
            "review_positioning": str | None,
            "root_bottleneck": str,
            "seo_lever_assessment_summary": str,
            "seo_priority_score": int
        }
    """
    obj = lead.get("objective_decision_layer") or {}
    sales = lead.get("sales_intervention_intelligence") or {}
    root = obj.get("root_bottleneck_classification") or {}
    bottleneck = root.get("bottleneck", "")
    comp = obj.get("competitive_snapshot") or {}

    # --- seo_priority_score (direct) ---
    score = obj.get("seo_sales_value_score")
    if score is None:
        score = 50
    try:
        score = int(round(float(score)))
    except (TypeError, ValueError):
        score = 50
    score = max(0, min(100, score))

    # --- pipeline_priority (HIGH / MEDIUM / LOW) ---
    has_website = lead.get("signal_has_website") is True
    if score < 55 or bottleneck == "trust_limited" or not has_website:
        pipeline_priority = "LOW"
    elif score >= 70 and bottleneck != "trust_limited" and has_website:
        pipeline_priority = "HIGH"
    else:
        pipeline_priority = "MEDIUM"

    # --- primary_sales_anchor (one clean sentence) ---
    anchor = (obj.get("primary_sales_anchor") or sales.get("primary_sales_anchor")) or {}
    issue = (anchor.get("issue") or "").strip()
    if not issue:
        issue = "Visibility and conversion opportunity; review evidence before outreach."
    if "." in issue:
        issue = issue.split(".")[0].strip() + "."
    primary_sales_anchor = issue[:300]

    # --- first_action ---
    first_action = ""
    plan = (obj.get("intervention_plan") or sales.get("intervention_plan")) or []
    if isinstance(plan, list) and plan:
        first = plan[0]
        if isinstance(first, dict):
            first_action = (first.get("action") or "").strip()
    if not first_action:
        first_action = "Review root bottleneck and intervention plan for first action."

    # --- competitors_sampled, competitor_avg_review_count, review_positioning ---
    competitors_sampled = comp.get("dentists_sampled") or 0
    competitor_avg_review_count = comp.get("avg_review_count")
    if competitor_avg_review_count is not None:
        competitor_avg_review_count = round(float(competitor_avg_review_count), 1)
    review_positioning = comp.get("review_positioning")

    # --- seo_lever_assessment_summary (short string from existing reasoning) ---
    seo_assess = obj.get("seo_lever_assessment") or {}
    reasoning = (seo_assess.get("reasoning") or obj.get("seo_best_lever_reasoning") or "").strip()
    seo_lever_assessment_summary = reasoning[:200] if reasoning else "Review objective_decision_layer for SEO lever assessment."

    return {
        "pipeline_priority": pipeline_priority,
        "primary_sales_anchor": primary_sales_anchor,
        "first_action": first_action,
        "competitors_sampled": competitors_sampled,
        "competitor_avg_review_count": competitor_avg_review_count,
        "review_positioning": review_positioning,
        "root_bottleneck": bottleneck,
        "seo_lever_assessment_summary": seo_lever_assessment_summary,
        "seo_priority_score": score,
    }
