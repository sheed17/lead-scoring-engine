"""
Pydantic schemas for the diagnostic API.
"""

from typing import Optional, List, Any, Dict
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Diagnostic input / output
# ---------------------------------------------------------------------------

class DiagnosticRequest(BaseModel):
    """Request body for POST /diagnostic."""

    business_name: str
    city: str
    state: str
    website: Optional[str] = None


class InterventionPlanItem(BaseModel):
    step: int
    category: str
    action: str


class ServiceIntelligence(BaseModel):
    detected_services: List[str] = []
    missing_services: List[str] = []
    schema_detected: Optional[bool] = None


class RevenueBreakdown(BaseModel):
    service: str
    consults_per_month: str
    revenue_per_case: str
    annual_revenue_range: str


class ConversionInfrastructure(BaseModel):
    online_booking: Optional[bool] = None
    contact_form: Optional[bool] = None
    phone_prominent: Optional[bool] = None
    mobile_optimized: Optional[bool] = None
    page_load_ms: Optional[int] = None


class EvidenceItem(BaseModel):
    label: str
    value: str


class DiagnosticResponse(BaseModel):
    """Structured JSON summary returned by POST /diagnostic."""

    lead_id: int
    business_name: str
    city: str
    state: Optional[str] = None
    opportunity_profile: str
    constraint: str
    primary_leverage: str
    market_density: str
    review_position: str
    paid_status: str
    intervention_plan: List[InterventionPlanItem]
    brief: Optional[Dict[str, Any]] = None
    service_intelligence: Optional[ServiceIntelligence] = None
    revenue_breakdowns: List[RevenueBreakdown] = []
    conversion_infrastructure: Optional[ConversionInfrastructure] = None
    risk_flags: List[str] = []
    evidence: List[EvidenceItem] = []


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class JobSubmitResponse(BaseModel):
    job_id: str
    status: str = "pending"


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    diagnostic_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Diagnostics (SaaS layer)
# ---------------------------------------------------------------------------

class DiagnosticListItem(BaseModel):
    id: int
    business_name: str
    city: str
    state: Optional[str] = None
    place_id: Optional[str] = None
    created_at: str
    opportunity_profile: Optional[str] = None
    constraint: Optional[str] = None
    modeled_revenue_upside: Optional[str] = None


class DiagnosticListResponse(BaseModel):
    items: List[DiagnosticListItem]
    total: int
    limit: int
    offset: int
