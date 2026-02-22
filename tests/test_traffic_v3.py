"""
Test traffic model v3: output shape, debug components, no hallucinated values.
Japantown Dental-style fixture: high reviews, paid ads, moderate density, above average positioning.
"""

import os
import sys
import json

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)


def _japantown_style_lead():
    """Minimal fixture resembling Japantown Dental from test_small_results_dentist.json."""
    return {
        "signal_has_website": True,
        "signal_domain": "japantowndental.com",
        "signal_review_count": 277,
        "user_ratings_total": 277,
        "signal_rating": 4.8,
        "signal_review_velocity_30d": 2,
        "signal_review_velocity_90d": 6,  # optional: 2*3 = 6 for stable ratio
        "signal_has_ssl": True,
        "signal_has_schema_microdata": False,
        "signal_schema_types": [],
        "signal_mobile_friendly": True,
        "signal_has_contact_form": True,
        "signal_has_phone": True,
        "signal_runs_paid_ads": True,
        "signal_paid_ads_channels": ["google"],
        "signal_ad_duration_days": 45,  # optional: 30-89 -> +8 stability
        "signal_social_platforms": ["yelp", "youtube"],
        "signal_booking_conversion_path": "Online booking (full)",
        "signal_page_load_time_ms": 948,
    }


def _japantown_objective_layer():
    return {
        "competitive_snapshot": {
            "dentists_sampled": 5,
            "review_positioning": "Above sample average",
            "market_density_score": "Moderate",
            "lead_review_count": 277,
            "avg_review_count": 75,
        },
        "service_intelligence": {
            "high_ticket_procedures_detected": [{"procedure": "Implants"}, {"procedure": "Cleaning"}],
            "general_services_detected": ["General", "Preventive"],
            "missing_high_value_pages": [],
            "procedure_confidence": 0.85,
        },
    }


def test_v3_output_structure():
    from pipeline.traffic_model_v3 import compute_traffic_v3

    context = _japantown_style_lead()
    objective_layer = _japantown_objective_layer()
    out = compute_traffic_v3(context, objective_layer)

    assert out["model_version"] == "v3"
    assert "traffic_index" in out
    assert "traffic_estimate_tier" in out
    assert "traffic_estimate_monthly" in out
    assert "paid_clicks_estimate_monthly" in out
    assert "traffic_confidence_score" in out
    assert "traffic_efficiency_score" in out
    assert "traffic_efficiency_interpretation" in out
    assert "traffic_assumptions" in out
    assert "traffic_debug_components" in out

    debug = out["traffic_debug_components"]
    for key in ("authority", "acceleration_bonus", "keyword_footprint", "technical", "backlink_proxy", "paid_stability"):
        assert key in debug, f"missing {key}"
        assert isinstance(debug[key], (int, float)), f"{key} not numeric"

    assert 0 <= out["traffic_index"] <= 100
    monthly = out["traffic_estimate_monthly"]
    assert monthly["unit"] == "visits/month"
    assert isinstance(monthly["lower"], int) and monthly["lower"] >= 0
    assert isinstance(monthly["upper"], int) and monthly["upper"] >= 0
    assert out["traffic_estimate_tier"] in ("Low", "Moderate", "High", "Very High")


def test_v3_v2_index_moderate_shift():
    """V3 index should not be extreme vs v2 for same inputs."""
    from pipeline.traffic_model_v2 import compute_traffic_v2
    from pipeline.traffic_model_v3 import compute_traffic_v3

    context = _japantown_style_lead()
    objective_layer = _japantown_objective_layer()
    v2 = compute_traffic_v2(context, objective_layer)
    v3 = compute_traffic_v3(context, objective_layer)

    # Moderate shift: within 25 points
    assert abs(v3["traffic_index"] - v2["traffic_index"]) <= 25
    # V3 should still produce valid range
    assert v3["traffic_estimate_monthly"]["upper"] >= v3["traffic_estimate_monthly"]["lower"]


def test_v3_optional_signals_safe():
    """Missing optional signals (velocity_90d, ad_duration_days, zip_income) must not crash."""
    from pipeline.traffic_model_v3 import compute_traffic_v3

    context = {
        "signal_has_website": True,
        "signal_review_count": 50,
        "user_ratings_total": 50,
        "signal_rating": 4.5,
    }
    objective_layer = {"competitive_snapshot": {}, "service_intelligence": {}}
    out = compute_traffic_v3(context, objective_layer)
    assert out["model_version"] == "v3"
    assert "traffic_debug_components" in out
    assert 0 <= out["traffic_index"] <= 100
