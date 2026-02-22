"""
Validation and sanity checks for signals and context.

Surfaces impossible combos and odd states as warnings (no hard failures).
"""

from typing import Dict, List, Any


def check_lead_signals(signals: Dict[str, Any]) -> List[str]:
    """
    Check for inconsistent or impossible signal combinations.
    Returns list of warning strings (empty if none).
    """
    warnings = []
    # Normalize: accept signal_ prefix
    s = {k.replace("signal_", "") if k.startswith("signal_") else k: v for k, v in signals.items()}

    has_website = s.get("has_website")
    website_accessible = s.get("website_accessible")
    if has_website is False and website_accessible is True:
        warnings.append("has_website=false but website_accessible=true (impossible)")
    if has_website is True and website_accessible is False:
        # This is valid (site exists but down)
        pass
    if has_website is False and s.get("has_contact_form") is True:
        warnings.append("has_website=false but has_contact_form=true (unusual)")
    if has_website is False and s.get("mobile_friendly") is not None:
        warnings.append("has_website=false but mobile_friendly is set (should be unknown)")

    return warnings


def check_context(context: Dict[str, Any]) -> List[str]:
    """
    Check for odd context states (e.g. all Unknown but high confidence).
    Returns list of warning strings.
    """
    warnings = []
    dimensions = context.get("context_dimensions") or []
    confidence = context.get("confidence") or 0
    statuses = [d.get("status") for d in dimensions if d.get("status")]

    if confidence >= 0.7 and all(s == "Unknown" for s in statuses):
        warnings.append("High confidence but all dimensions Unknown (review signals)")
    if not dimensions and confidence > 0:
        warnings.append("No dimensions but confidence > 0")
    return warnings
