"""
API routes for outcome tracking and model calibration.
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


class RecordOutcomeRequest(BaseModel):
    diagnostic_id: int
    outcome_type: str  # "user_reported" | "revenue_reported" | "conversion_reported"
    outcome_data: Dict[str, Any]


class OutcomeResponse(BaseModel):
    success: bool
    message: str


@router.post("", response_model=OutcomeResponse)
def record_outcome(req: RecordOutcomeRequest, request: Request):
    """Record an outcome for a diagnostic."""
    from pipeline.outcome_tracking import record_outcome, ensure_outcome_tables

    valid_types = {"user_reported", "revenue_reported", "conversion_reported"}
    if req.outcome_type not in valid_types:
        raise HTTPException(400, f"outcome_type must be one of: {', '.join(valid_types)}")

    ensure_outcome_tables()
    record_outcome(req.diagnostic_id, req.outcome_type, req.outcome_data)

    return OutcomeResponse(success=True, message="Outcome recorded")


@router.get("/calibration")
def get_calibration(request: Request):
    """Get model calibration statistics from recorded outcomes."""
    from pipeline.outcome_tracking import get_calibration_stats, ensure_outcome_tables

    ensure_outcome_tables()
    stats = get_calibration_stats()
    return stats


@router.get("/{diagnostic_id}")
def get_outcomes(diagnostic_id: int, request: Request):
    """Get all recorded outcomes for a specific diagnostic."""
    from pipeline.outcome_tracking import ensure_outcome_tables
    from pipeline.db import _get_conn
    import json

    ensure_outcome_tables()
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM diagnostic_outcomes WHERE diagnostic_id = ? ORDER BY created_at DESC",
            (diagnostic_id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "diagnostic_id": row["diagnostic_id"],
                "outcome_type": row["outcome_type"],
                "outcome_data": json.loads(row["outcome_json"]) if row["outcome_json"] else {},
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()
