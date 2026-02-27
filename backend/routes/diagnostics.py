"""
Diagnostics CRUD — list / detail / delete saved diagnostics.
"""

import io
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

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
from pipeline.db import (
    count_diagnostics,
    create_brief_share_token,
    delete_diagnostic,
    get_diagnostic,
    get_outcome_summary_for_user,
    list_diagnostics,
    list_outcomes_for_user,
)

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


def _render_pdf_from_lines(title: str, lines: List[str]) -> bytes:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="PDF export dependency missing (reportlab). Install with: pip install reportlab",
        ) from exc

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 48
    c.setFont("Helvetica-Bold", 14)
    c.drawString(48, y, title[:110])
    y -= 28
    c.setFont("Helvetica", 10)
    for line in lines:
        text = (line or "").strip()
        if not text:
            y -= 8
            continue
        wrapped: List[str] = []
        while len(text) > 112:
            cut = text.rfind(" ", 0, 112)
            if cut <= 0:
                cut = 112
            wrapped.append(text[:cut])
            text = text[cut:].lstrip()
        wrapped.append(text)
        for part in wrapped:
            if y < 56:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = height - 48
            c.drawString(48, y, part)
            y -= 14
    c.save()
    return buffer.getvalue()


def _brief_pdf_lines(resp: Dict[str, Any]) -> List[str]:
    brief = resp.get("brief") or {}
    ed = brief.get("executive_diagnosis") or {}
    mp = brief.get("market_position") or {}
    cc = brief.get("competitive_context") or {}
    csg = brief.get("competitive_service_gap") or {}
    ds = brief.get("demand_signals") or {}
    ht = brief.get("high_ticket_gaps") or {}
    rucg = brief.get("revenue_upside_capture_gap") or {}
    sg = brief.get("strategic_gap") or {}
    ci = brief.get("conversion_infrastructure") or {}
    convs = brief.get("conversion_structure") or {}
    geo = brief.get("geo_coverage") or {}
    plan = brief.get("intervention_plan") or []
    risks = brief.get("risk_flags") or []
    evidence = brief.get("evidence_bullets") or []

    def _opp_label() -> str:
        opp = ed.get("opportunity_profile")
        if isinstance(opp, dict):
            lbl = opp.get("label") or "—"
            why = opp.get("why")
            return f"{lbl} ({why})" if why else str(lbl)
        return str(opp or resp.get("opportunity_profile") or "—")

    lines: List[str] = [
        f"Business: {resp.get('business_name', '')}",
        f"Location: {resp.get('city', '')}{', ' + str(resp.get('state')) if resp.get('state') else ''}",
        "",
        "Executive Diagnosis",
        f"Constraint: {ed.get('constraint') or resp.get('constraint') or '—'}",
        f"Primary Leverage: {ed.get('primary_leverage') or resp.get('primary_leverage') or '—'}",
        f"Opportunity Profile: {_opp_label()}",
        f"Modeled Upside: {ed.get('modeled_revenue_upside') or '—'}",
        "",
        "Market Position",
        f"Revenue Band: {mp.get('revenue_band') or '—'}",
        f"Reviews: {mp.get('reviews') or '—'}",
        f"Local Avg: {mp.get('local_avg') or '—'}",
        f"Market Density: {mp.get('market_density') or '—'}",
    ]

    if cc:
        lines.extend(["", "Competitive Context"])
        if cc.get("line1"):
            lines.append(str(cc.get("line1")))
        if cc.get("line2"):
            lines.append(str(cc.get("line2")))
        if cc.get("line3"):
            lines.append(str(cc.get("line3")))

    if csg:
        lines.extend(["", "Competitive Service Gap"])
        lines.append(f"Type: {csg.get('type') or '—'}")
        lines.append(f"Service: {csg.get('service') or '—'}")
        lines.append(f"Nearest competitor: {csg.get('competitor_name') or '—'}")
        if csg.get("distance_miles") is not None:
            lines.append(f"Distance: {csg.get('distance_miles')} mi")

    if ds:
        lines.extend(["", "Demand Signals"])
        if ds.get("google_ads_line"):
            lines.append(f"Google Ads: {ds.get('google_ads_line')}")
        if ds.get("meta_ads_line"):
            lines.append(f"Meta Ads: {ds.get('meta_ads_line')}")
        if ds.get("organic_visibility_tier"):
            reason = f" — {ds.get('organic_visibility_reason')}" if ds.get("organic_visibility_reason") else ""
            lines.append(f"Organic Visibility: {ds.get('organic_visibility_tier')}{reason}")
        if ds.get("last_review_days_ago") is not None:
            lines.append(f"Last Review: ~{ds.get('last_review_days_ago')} days ago")
        if ds.get("review_velocity_30d") is not None:
            lines.append(f"Review Velocity (30d): ~{ds.get('review_velocity_30d')}")

    if ht:
        lines.extend(["", "Local SEO & High-Value Service Pages"])
        detected = ht.get("high_ticket_services_detected") or []
        missing = ht.get("missing_landing_pages") or []
        if detected:
            lines.append(f"Detected services: {', '.join(str(x) for x in detected)}")
        if missing:
            lines.append(f"Missing landing pages: {', '.join(str(x) for x in missing)}")
        if ht.get("schema"):
            lines.append(f"Schema: {ht.get('schema')}")

    if rucg and rucg.get("primary_service"):
        lines.extend(["", f"Modeled Revenue Upside — {rucg.get('primary_service')} Capture Gap"])
        lines.append(f"{rucg.get('consult_low', '—')}–{rucg.get('consult_high', '—')} additional consults/month")
        lines.append(f"${int(rucg.get('case_low', 0)):,}–${int(rucg.get('case_high', 0)):,} per case")
        lines.append(f"${int(rucg.get('annual_low', 0)):,}–${int(rucg.get('annual_high', 0)):,} annually")

    if sg and sg.get("competitor_name"):
        lines.extend(["", "Strategic Gap"])
        lines.append(
            f"Nearest competitor {sg.get('competitor_name')} holds {sg.get('competitor_reviews', '—')} reviews "
            f"within {sg.get('distance_miles', '—')} miles in a {sg.get('market_density', '—')} density market."
        )

    if ci:
        lines.extend(["", "Conversion Infrastructure"])
        if ci.get("online_booking") is not None:
            lines.append(f"Online Booking: {'Yes' if ci.get('online_booking') else 'No'}")
        if ci.get("contact_form") is not None:
            lines.append(f"Contact Form: {'Yes' if ci.get('contact_form') else 'No'}")
        if ci.get("phone_prominent") is not None:
            lines.append(f"Phone Prominent: {'Yes' if ci.get('phone_prominent') else 'No'}")
        if ci.get("mobile_optimized") is not None:
            lines.append(f"Mobile Optimized: {'Yes' if ci.get('mobile_optimized') else 'No'}")
        if ci.get("page_load_ms") is not None:
            lines.append(f"Page Load: {ci.get('page_load_ms')} ms")

    if convs:
        lines.extend(["", "Conversion Structure"])
        if convs.get("phone_clickable") is not None:
            lines.append(f"Phone clickable: {'Yes' if convs.get('phone_clickable') else 'No'}")
        if convs.get("cta_count") is not None:
            lines.append(f"CTA count: {convs.get('cta_count')}")
        if convs.get("form_single_or_multi_step"):
            lines.append(f"Form structure: {convs.get('form_single_or_multi_step')}")

    if geo:
        lines.extend(["", "Geographic Coverage"])
        if geo.get("city_or_near_me_page_count") is not None:
            lines.append(f"City/near-me pages: {geo.get('city_or_near_me_page_count')}")
        if geo.get("has_multi_location_page") is not None:
            lines.append(f"Multi-location page: {'Detected' if geo.get('has_multi_location_page') else 'Not detected'}")

    if plan:
        lines.extend(["", "Intervention Plan"])
        for step in plan[:3]:
            lines.append(f"- {step}")
    if risks:
        lines.extend(["", "Risk Flags"])
        for risk in risks[:5]:
            lines.append(f"- {risk}")
    if evidence:
        lines.extend(["", "Evidence"])
        for item in evidence[:12]:
            lines.append(f"- {item}")
    return lines


@router.get("/outcomes/summary")
def outcomes_summary(request: Request):
    user_id = getattr(request.state, "user_id", 1)
    return get_outcome_summary_for_user(user_id)


@router.get("/outcomes")
def outcomes_list(request: Request, limit: int = Query(default=200, ge=1, le=1000)):
    user_id = getattr(request.state, "user_id", 1)
    return {"items": list_outcomes_for_user(user_id, limit=limit)}


@router.post("/{diagnostic_id}/share")
def create_share_link(diagnostic_id: int, request: Request):
    user_id = getattr(request.state, "user_id", 1)
    row = get_diagnostic(diagnostic_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Diagnostic not found")
    token = secrets.token_hex(16)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    create_brief_share_token(
        diagnostic_id=diagnostic_id,
        user_id=user_id,
        token=token,
        expires_at=expires_at,
    )
    base = str(request.base_url).rstrip("/")
    return {
        "token": token,
        "share_url": f"{base}/brief/s/{token}",
        "expires_at": expires_at,
    }


@router.get("/{diagnostic_id}/brief.pdf")
def diagnostic_brief_pdf(diagnostic_id: int, request: Request):
    user_id = getattr(request.state, "user_id", 1)
    row = get_diagnostic(diagnostic_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Diagnostic not found")
    resp = row.get("response") or {}
    business = str(resp.get("business_name") or f"diagnostic-{diagnostic_id}").replace("/", "-")
    city = str(resp.get("city") or "").replace("/", "-")
    filename = f"Brief-{business}-{city}.pdf".replace(" ", "-")
    pdf_bytes = _render_pdf_from_lines(
        f"Revenue Intelligence Brief — {resp.get('business_name', 'Business')}",
        _brief_pdf_lines(resp),
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


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
