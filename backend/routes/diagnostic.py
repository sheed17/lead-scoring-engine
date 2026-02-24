"""
POST /diagnostic route.
"""

import logging
from fastapi import APIRouter, HTTPException

from backend.models.schemas import DiagnosticRequest, DiagnosticResponse, InterventionPlanItem
from backend.services.enrichment_service import run_diagnostic

router = APIRouter(prefix="/diagnostic", tags=["diagnostic"])


@router.post("", response_model=DiagnosticResponse)
def post_diagnostic(body: DiagnosticRequest):
    """
    Run diagnostic enrichment on a business.

    Required: business_name, city
    Optional: website
    """
    try:
        result = run_diagnostic(
            business_name=body.business_name.strip(),
            city=body.city.strip(),
            website=body.website.strip() if body.website else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Business not found")
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Pipeline or API error")
    except Exception as e:
        logging.getLogger(__name__).exception("Diagnostic failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

    # Convert intervention_plan dicts to Pydantic models
    plan = [
        InterventionPlanItem(step=item["step"], category=item["category"], action=item["action"])
        for item in result.get("intervention_plan", [])
    ]
    return DiagnosticResponse(
        lead_id=result["lead_id"],
        business_name=result["business_name"],
        city=result["city"],
        opportunity_profile=result["opportunity_profile"],
        constraint=result["constraint"],
        primary_leverage=result["primary_leverage"],
        market_density=result["market_density"],
        review_position=result["review_position"],
        paid_status=result["paid_status"],
        intervention_plan=plan,
    )
