"""
Natural-language prospect finder endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.services.npl_service import parse_npl_query
from pipeline.db import create_job, get_job, get_latest_diagnostic_by_place_id

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    query: str
    accuracy_mode: str | None = None


class AskEnsureBriefRequest(BaseModel):
    place_id: str | None = None
    business_name: str
    city: str
    state: str | None = None
    website: str | None = None


@router.post("/ask")
def ask_find(body: AskRequest, request: Request):
    user_id = getattr(request.state, "user_id", 1)
    try:
        intent = parse_npl_query(body.query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    accuracy_mode = (body.accuracy_mode or "verified").strip().lower()
    if accuracy_mode not in {"fast", "verified"}:
        raise HTTPException(status_code=400, detail="accuracy_mode must be 'fast' or 'verified'")

    job_id = create_job(
        user_id=user_id,
        job_type="npl_find",
        input_data={"query": body.query, "intent": intent, "accuracy_mode": accuracy_mode},
    )
    return {
        "job_id": job_id,
        "status": "pending",
        "intent": intent,
        "message": (
            f"Verifying {intent.get('vertical', 'prospects')} in {intent.get('city')}{', ' + str(intent.get('state')) if intent.get('state') else ''}..."
            if accuracy_mode == "verified"
            else f"Finding {intent.get('vertical', 'prospects')} in {intent.get('city')}{', ' + str(intent.get('state')) if intent.get('state') else ''}..."
        ),
        "accuracy_mode": accuracy_mode,
    }


@router.get("/ask/jobs/{job_id}/results")
def ask_results(job_id: str, request: Request):
    user_id = getattr(request.state, "user_id", 1)
    job = get_job(job_id)
    if not job or job.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("type") != "npl_find":
        raise HTTPException(status_code=400, detail="Not an ask job")
    if job.get("status") != "completed":
        return {
            "job_id": job_id,
            "status": job.get("status"),
            "result": job.get("result") or None,
        }
    return {
        "job_id": job_id,
        "status": "completed",
        "result": job.get("result") or {},
    }


@router.post("/ask/prospects/ensure-brief")
def ask_ensure_brief(body: AskEnsureBriefRequest, request: Request):
    """Create/ensure a full diagnostic for one Ask row on demand."""
    user_id = getattr(request.state, "user_id", 1)
    place_id = str(body.place_id or "").strip() or None
    business_name = body.business_name.strip()
    city = body.city.strip()
    state = (body.state or "").strip() or None

    if not business_name or not city:
        raise HTTPException(status_code=400, detail="business_name and city are required")

    if place_id:
        existing = get_latest_diagnostic_by_place_id(user_id, place_id)
        if existing:
            return {
                "status": "ready",
                "diagnostic_id": int(existing["id"]),
            }

    job_id = create_job(
        user_id=user_id,
        job_type="diagnostic",
        input_data={
            "place_id": place_id,
            "business_name": business_name,
            "city": city,
            "state": state,
            "website": body.website,
        },
    )
    return {
        "status": "building",
        "job_id": job_id,
    }
