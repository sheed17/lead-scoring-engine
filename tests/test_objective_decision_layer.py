"""
Unit tests for the Objective Decision Layer.

Scenarios:
  A) Strong reputation + high reviews + no booking -> must NOT always be conversion_limited; evaluate saturation/visibility/demand.
  B) Weak rating + low review count + ads running -> likely trust_limited first.
  C) No website / no SSL / no contact options -> conversion_limited or visibility_limited depending on signals.
  D) High saturation proxy + average signals -> saturation_limited or defer.
"""

import os
import sys
import importlib.util

# Project root
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

# Load only objective_decision_layer to avoid pulling in requests etc.
_spec = importlib.util.spec_from_file_location(
    "objective_decision_layer",
    os.path.join(_root, "pipeline", "objective_decision_layer.py"),
)
_obj_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_obj_mod)

compute_objective_decision_layer = _obj_mod.compute_objective_decision_layer
_compute_demand_capture_conversion_model = _obj_mod._compute_demand_capture_conversion_model
_compute_root_bottleneck = _obj_mod._compute_root_bottleneck
_compute_seo_best_lever = _obj_mod._compute_seo_best_lever
_compute_comparative_context = _obj_mod._compute_comparative_context
ROOT_BOTTLENECKS = _obj_mod.ROOT_BOTTLENECKS


def _signal_block(status: str, evidence: list, confidence: float) -> dict:
    return {"status": status, "evidence": evidence, "confidence": confidence}


def _dentist_profile(overrides: dict) -> dict:
    base = {
        "dental_practice_profile": {"practice_type": "general_dentistry", "procedure_focus_detected": [], "estimated_ltv_class": "Medium", "confidence": 0.75},
        "patient_acquisition_readiness": {"booking_friction": "Moderate", "conversion_leaks": ["Phone-only intake; no online booking"], "chair_fill_risk": "Moderate", "confidence": 0.8},
        "local_search_positioning": {"review_count_vs_market": "Average", "rating_strength": "Moderate", "map_pack_competitiveness": "Moderate", "visibility_gap": "Competitive", "confidence": 0.8},
        "trust_conversion_signals": {"insurance_accepted_visible": True, "before_after_gallery": False, "doctor_credentials_visible": True, "confidence": 0.6},
        "review_intent_analysis": {"procedure_mentions": [], "urgency_language_detected": False, "insurance_mentions": True, "confidence": 0.7},
        "agency_fit_reasoning": {"ideal_for_seo_outreach": True, "why": [], "risk_flags": [], "confidence": 0.7},
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    return base


def _lead(overrides: dict, dentist_profile: dict = None) -> dict:
    base = {
        "name": "Test Dental",
        "place_id": "test-1",
        "signal_rating": 4.5,
        "signal_review_count": 60,
        "signal_last_review_days_ago": 45,
        "signal_has_website": True,
        "signal_has_automated_scheduling": False,
        "signal_has_contact_form": True,
        "signal_has_phone": True,
        "signal_runs_paid_ads": False,
        "signal_review_summary_text": "Great care",
        "signal_review_sample_snippets": [],
    }
    base.update(overrides)
    if dentist_profile is not None:
        base["dentist_profile_v1"] = dentist_profile
    return base


# --- Scenario A: Strong reputation + high reviews + no booking ---
def test_a_strong_rep_high_reviews_no_booking_not_always_conversion_limited():
    """Should NOT always be conversion_limited; evaluate saturation/differentiation first."""
    # Strong trust, strong capture (saturated), weak conversion, no niche -> differentiation_limited (or saturation_limited).
    # With Saturated + High map_pack and Strong trust and no niche -> differentiation_limited. NOT conversion_limited.
    lead = _lead({
        "signal_rating": 4.9,
        "signal_review_count": 200,
        "signal_last_review_days_ago": 14,
        "signal_has_automated_scheduling": False,
        "signal_has_contact_form": False,
    })
    profile = _dentist_profile({
        "patient_acquisition_readiness": {"booking_friction": "High", "conversion_leaks": ["Phone-only intake; no online booking", "No contact form for web leads"], "chair_fill_risk": "High", "confidence": 0.9},
        "local_search_positioning": {"review_count_vs_market": "Above Average", "rating_strength": "Strong", "map_pack_competitiveness": "High", "visibility_gap": "Saturated", "confidence": 0.9},
        "trust_conversion_signals": {"insurance_accepted_visible": True, "before_after_gallery": True, "doctor_credentials_visible": True, "confidence": 0.9},
    })
    lead["dentist_profile_v1"] = profile
    dcm = _compute_demand_capture_conversion_model(lead, profile)
    root = _compute_root_bottleneck(lead, profile, dcm)
    assert root["bottleneck"] in ("saturation_limited", "differentiation_limited"), f"Expected saturation or differentiation limited, not conversion; got {root['bottleneck']}"


# --- Scenario B: Weak rating + low review count + ads running ---
def test_b_weak_rating_low_reviews_ads_trust_limited_first():
    """Likely trust_limited first."""
    lead = _lead({
        "signal_rating": 3.6,
        "signal_review_count": 8,
        "signal_last_review_days_ago": 120,
        "signal_runs_paid_ads": True,
    })
    profile = _dentist_profile({
        "local_search_positioning": {"review_count_vs_market": "Below Average", "rating_strength": "Weak", "map_pack_competitiveness": "Low", "visibility_gap": "Underutilized", "confidence": 0.7},
        "trust_conversion_signals": {"insurance_accepted_visible": False, "before_after_gallery": False, "doctor_credentials_visible": False, "confidence": 0.3},
    })
    lead["dentist_profile_v1"] = profile
    dcm = _compute_demand_capture_conversion_model(lead, profile)
    root = _compute_root_bottleneck(lead, profile, dcm)
    assert root["bottleneck"] == "trust_limited", f"Expected trust_limited; got {root['bottleneck']}"


# --- Scenario C: No website / no SSL / no contact options ---
def test_c_no_website_no_contact_conversion_or_visibility_limited():
    """Conversion_limited or visibility_limited depending on signals."""
    lead = _lead({
        "signal_has_website": False,
        "signal_has_contact_form": False,
        "signal_has_phone": True,
        "signal_review_count": 25,
        "signal_rating": 4.2,
    })
    profile = _dentist_profile({
        "patient_acquisition_readiness": {"booking_friction": "High", "conversion_leaks": ["No contact form for web leads", "Phone-only intake; no online booking"], "chair_fill_risk": "High", "confidence": 0.7},
        "local_search_positioning": {"review_count_vs_market": "Below Average", "rating_strength": "Moderate", "map_pack_competitiveness": "Low", "visibility_gap": "Underutilized", "confidence": 0.6},
        "trust_conversion_signals": {"insurance_accepted_visible": False, "before_after_gallery": False, "doctor_credentials_visible": False, "confidence": 0.0},
    })
    lead["dentist_profile_v1"] = profile
    dcm = _compute_demand_capture_conversion_model(lead, profile)
    root = _compute_root_bottleneck(lead, profile, dcm)
    # Trust could be Weak (no website trust signals). Or demand/capture/conversion weak.
    assert root["bottleneck"] in ("trust_limited", "visibility_limited", "conversion_limited", "demand_limited"), f"Expected one of trust/visibility/conversion/demand limited; got {root['bottleneck']}"


# --- Scenario D: High saturation + average signals ---
def test_d_high_saturation_average_signals_saturation_limited_or_defer():
    """Saturation_limited or defer."""
    lead = _lead({
        "signal_rating": 4.3,
        "signal_review_count": 80,
        "signal_last_review_days_ago": 60,
        "signal_has_website": True,
        "signal_has_contact_form": True,
        "signal_has_automated_scheduling": False,
    })
    profile = _dentist_profile({
        "local_search_positioning": {"review_count_vs_market": "Average", "rating_strength": "Moderate", "map_pack_competitiveness": "High", "visibility_gap": "Saturated", "confidence": 0.8},
        "trust_conversion_signals": {"insurance_accepted_visible": True, "before_after_gallery": False, "doctor_credentials_visible": True, "confidence": 0.6},
    })
    lead["dentist_profile_v1"] = profile
    dcm = _compute_demand_capture_conversion_model(lead, profile)
    root = _compute_root_bottleneck(lead, profile, dcm)
    assert root["bottleneck"] in ("saturation_limited", "differentiation_limited"), f"Expected saturation or differentiation limited; got {root['bottleneck']}"


# --- SEO best lever ---
def test_seo_best_lever_false_for_trust_limited():
    dcm = {
        "trust_signals": _signal_block("Weak", ["Low rating"], 0.7),
        "capture_signals": _signal_block("Moderate", [], 0.6),
        "conversion_signals": _signal_block("Moderate", [], 0.6),
        "demand_signals": _signal_block("Moderate", [], 0.6),
    }
    out = _compute_seo_best_lever("trust_limited", dcm)
    assert out["is_primary_growth_lever"] is False
    assert "trust" in out["reasoning"].lower() or "reputation" in out["reasoning"].lower()


def test_seo_best_lever_true_for_visibility_limited_strong_trust():
    dcm = {
        "trust_signals": _signal_block("Strong", [], 0.8),
        "capture_signals": _signal_block("Weak", [], 0.7),
        "conversion_signals": _signal_block("Moderate", [], 0.6),
        "demand_signals": _signal_block("Moderate", [], 0.6),
    }
    out = _compute_seo_best_lever("visibility_limited", dcm)
    assert out["is_primary_growth_lever"] is True


# --- Full block shape ---
def test_compute_objective_decision_layer_returns_all_sections():
    lead = _lead({"signal_review_count": 40, "signal_rating": 4.6})
    lead["dentist_profile_v1"] = _dentist_profile({})
    out = compute_objective_decision_layer(lead)
    assert out is not None
    assert "root_bottleneck_classification" in out
    assert out["root_bottleneck_classification"]["bottleneck"] in ROOT_BOTTLENECKS
    assert "seo_lever_assessment" in out
    assert "is_primary_growth_lever" in out["seo_lever_assessment"]
    assert "reasoning" in out["seo_lever_assessment"]
    assert "demand_capture_conversion_model" in out
    assert "comparative_context" in out
    assert "primary_sales_anchor" in out
    assert "intervention_plan" in out
    assert "access_request_plan" in out
    assert "de_risking_questions" in out
    dcm = out["demand_capture_conversion_model"]
    for key in ("demand_signals", "capture_signals", "conversion_signals", "trust_signals"):
        assert key in dcm
        assert dcm[key]["status"] in ("Strong", "Moderate", "Weak")
    assert len(out["de_risking_questions"]) <= 3


def test_compute_objective_decision_layer_empty_without_dentist_profile():
    lead = _lead({})
    lead.pop("dentist_profile_v1", None)
    out = compute_objective_decision_layer(lead)
    assert out == {}


# --- New scenarios: differentiation_limited, seo_sales_value_score ---
def test_high_review_high_competition_no_niche_differentiation_limited():
    """A) High review + high competition + no niche -> differentiation_limited."""
    lead = _lead({"signal_rating": 4.7, "signal_review_count": 120, "signal_has_website": True})
    profile = _dentist_profile({
        "local_search_positioning": {"review_count_vs_market": "Above Average", "rating_strength": "Strong", "map_pack_competitiveness": "High", "visibility_gap": "Saturated", "confidence": 0.9},
        "trust_conversion_signals": {"insurance_accepted_visible": True, "before_after_gallery": False, "doctor_credentials_visible": True, "confidence": 0.7},
    })
    lead["dentist_profile_v1"] = profile
    dcm = _compute_demand_capture_conversion_model(lead, profile)
    # No service_intelligence with high-ticket, no revenue_leverage High -> no strong niche
    root = _compute_root_bottleneck(lead, profile, dcm, service_intelligence={}, competitive_snapshot={"market_density_score": "High"}, revenue_leverage={"estimated_revenue_asymmetry": "Low"})
    assert root["bottleneck"] == "differentiation_limited", f"Expected differentiation_limited; got {root['bottleneck']}"


def test_low_reviews_implants_offered_visibility_limited():
    """B) Low reviews + implants offered -> visibility_limited (capture weak)."""
    lead = _lead({"signal_review_count": 12, "signal_rating": 4.2, "signal_has_website": True})
    profile = _dentist_profile({
        "dental_practice_profile": {"procedure_focus_detected": ["implant", "cosmetic"], "estimated_ltv_class": "High", "confidence": 0.7},
        "local_search_positioning": {"review_count_vs_market": "Below Average", "rating_strength": "Moderate", "map_pack_competitiveness": "Low", "visibility_gap": "Underutilized", "confidence": 0.7},
    })
    lead["dentist_profile_v1"] = profile
    dcm = _compute_demand_capture_conversion_model(lead, profile)
    root = _compute_root_bottleneck(lead, profile, dcm, service_intelligence={"high_ticket_procedures_detected": ["dental implant"], "missing_high_value_pages": [], "procedure_confidence": 0.6})
    assert root["bottleneck"] == "visibility_limited", f"Expected visibility_limited; got {root['bottleneck']}"


def test_strong_everything_no_asymmetry_low_seo_sales_value():
    """C) Strong everything + no asymmetry -> seo_sales_value_score should be lower."""
    lead = _lead({"signal_rating": 4.8, "signal_review_count": 150, "signal_has_automated_scheduling": True, "signal_runs_paid_ads": True})
    profile = _dentist_profile({
        "local_search_positioning": {"review_count_vs_market": "Above Average", "rating_strength": "Strong", "map_pack_competitiveness": "High", "visibility_gap": "Saturated", "confidence": 0.9},
        "trust_conversion_signals": {"insurance_accepted_visible": True, "doctor_credentials_visible": True, "confidence": 0.8},
    })
    lead["dentist_profile_v1"] = profile
    out = compute_objective_decision_layer(lead, service_intelligence={"high_ticket_procedures_detected": [], "missing_high_value_pages": [], "procedure_confidence": 0.3}, competitive_snapshot={"dentists_sampled": 5, "avg_review_count": 80, "review_positioning": "Above sample average", "market_density_score": "High", "confidence": 0.7}, revenue_leverage={"estimated_revenue_asymmetry": "Low"})
    assert "seo_sales_value_score" in out
    assert out["seo_sales_value_score"] < 55, f"Expected lower score for strong+no asymmetry; got {out['seo_sales_value_score']}"


def test_no_website_low_reviews_conversion_or_visibility_limited():
    """D) No website + low reviews -> conversion_limited or visibility_limited or trust_limited."""
    lead = _lead({"signal_has_website": False, "signal_review_count": 8, "signal_rating": 4.0, "signal_has_contact_form": False})
    profile = _dentist_profile({
        "patient_acquisition_readiness": {"booking_friction": "High", "conversion_leaks": ["No contact form for web leads", "Phone-only intake; no online booking"], "chair_fill_risk": "High", "confidence": 0.6},
        "local_search_positioning": {"review_count_vs_market": "Below Average", "rating_strength": "Weak", "map_pack_competitiveness": "Low", "visibility_gap": "Underutilized", "confidence": 0.5},
        "trust_conversion_signals": {"insurance_accepted_visible": False, "before_after_gallery": False, "doctor_credentials_visible": False, "confidence": 0.0},
    })
    lead["dentist_profile_v1"] = profile
    dcm = _compute_demand_capture_conversion_model(lead, profile)
    root = _compute_root_bottleneck(lead, profile, dcm)
    assert root["bottleneck"] in ("trust_limited", "visibility_limited", "conversion_limited", "demand_limited"), f"Expected one of trust/visibility/conversion/demand; got {root['bottleneck']}"


if __name__ == "__main__":
    test_a_strong_rep_high_reviews_no_booking_not_always_conversion_limited()
    test_b_weak_rating_low_reviews_ads_trust_limited_first()
    test_c_no_website_no_contact_conversion_or_visibility_limited()
    test_d_high_saturation_average_signals_saturation_limited_or_defer()
    test_seo_best_lever_false_for_trust_limited()
    test_seo_best_lever_true_for_visibility_limited_strong_trust()
    test_compute_objective_decision_layer_returns_all_sections()
    test_compute_objective_decision_layer_empty_without_dentist_profile()
    test_high_review_high_competition_no_niche_differentiation_limited()
    test_low_reviews_implants_offered_visibility_limited()
    test_strong_everything_no_asymmetry_low_seo_sales_value()
    test_no_website_low_reviews_conversion_or_visibility_limited()
    print("All tests passed.")
