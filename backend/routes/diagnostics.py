"""
Diagnostics CRUD — list / detail / delete saved diagnostics.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from backend.models.schemas import (
    DiagnosticListItem,
    DiagnosticListResponse,
    DiagnosticResponse,
    InterventionPlanItem,
    ServiceIntelligence,
    RevenueBreakdown,
    ConversionInfrastructure,
    EvidenceItem,
)
from pipeline.db import list_diagnostics, get_diagnostic, delete_diagnostic, count_diagnostics

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def _response_from_saved(resp: dict) -> DiagnosticResponse:
    """Build a DiagnosticResponse from the stored response_json dict."""
    plan = [
        InterventionPlanItem(step=p["step"], category=p["category"], action=p["action"])
        for p in resp.get("intervention_plan", [])
        if isinstance(p, dict) and "step" in p
    ]

    si_raw = resp.get("service_intelligence")
    si = ServiceIntelligence(**si_raw) if isinstance(si_raw, dict) else None

    rbs = [
        RevenueBreakdown(
            service=rb.get("service", ""),
            consults_per_month=rb.get("consults_per_month", ""),
            revenue_per_case=rb.get("revenue_per_case", ""),
            annual_revenue_range=rb.get("annual_revenue_range", ""),
        )
        for rb in resp.get("revenue_breakdowns", [])
        if isinstance(rb, dict)
    ]

    ci_raw = resp.get("conversion_infrastructure")
    ci = ConversionInfrastructure(**ci_raw) if isinstance(ci_raw, dict) else None

    evidence = [
        EvidenceItem(label=e.get("label", ""), value=e.get("value", ""))
        for e in resp.get("evidence", [])
        if isinstance(e, dict)
    ]

    return DiagnosticResponse(
        lead_id=resp.get("lead_id", 0),
        business_name=resp.get("business_name", ""),
        city=resp.get("city", ""),
        state=resp.get("state"),
        opportunity_profile=resp.get("opportunity_profile", ""),
        constraint=resp.get("constraint", ""),
        primary_leverage=resp.get("primary_leverage", ""),
        market_density=resp.get("market_density", ""),
        review_position=resp.get("review_position", ""),
        paid_status=resp.get("paid_status", ""),
        intervention_plan=plan,
        brief=resp.get("brief"),
        service_intelligence=si,
        revenue_breakdowns=rbs,
        conversion_infrastructure=ci,
        risk_flags=resp.get("risk_flags", []),
        evidence=evidence,
    )


@router.get("", response_model=DiagnosticListResponse)
def list_all(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    user_id = getattr(request.state, "user_id", 1)
    rows = list_diagnostics(user_id, limit=limit, offset=offset)
    total = count_diagnostics(user_id)

    items = []
    for row in rows:
        resp = row.get("response", {})
        brief = resp.get("brief", {}) or {}
        ed = brief.get("executive_diagnosis", {}) or {}

        items.append(DiagnosticListItem(
            id=row["id"],
            business_name=row["business_name"],
            city=row["city"],
            state=row.get("state"),
            place_id=row.get("place_id"),
            created_at=row["created_at"],
            opportunity_profile=resp.get("opportunity_profile"),
            constraint=resp.get("constraint"),
            modeled_revenue_upside=ed.get("modeled_revenue_upside"),
        ))

    return DiagnosticListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{diagnostic_id}", response_model=DiagnosticResponse)
def get_one(diagnostic_id: int, request: Request):
    user_id = getattr(request.state, "user_id", 1)
    row = get_diagnostic(diagnostic_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Diagnostic not found")
    return _response_from_saved(row["response"])


@router.delete("/{diagnostic_id}")
def remove(diagnostic_id: int, request: Request):
    user_id = getattr(request.state, "user_id", 1)
    deleted = delete_diagnostic(diagnostic_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Diagnostic not found")
    return {"deleted": True}
