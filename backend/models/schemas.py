"""
Pydantic schemas for the diagnostic API.
"""

from typing import Optional, List
from pydantic import BaseModel


class DiagnosticRequest(BaseModel):
    """Request body for POST /diagnostic."""

    business_name: str
    city: str
    website: Optional[str] = None


class InterventionPlanItem(BaseModel):
    step: int
    category: str
    action: str


class DiagnosticResponse(BaseModel):
    """Structured JSON summary returned by POST /diagnostic."""

    lead_id: int
    business_name: str
    city: str
    opportunity_profile: str
    constraint: str
    primary_leverage: str
    market_density: str
    review_position: str
    paid_status: str
    intervention_plan: List[InterventionPlanItem]
