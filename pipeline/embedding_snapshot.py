"""
Embedding snapshot: build stable, minimal text for lead embeddings.

Uses objective_intelligence + competitive_snapshot + key service gap flags.
No numbers invented. Structural state only.
"""

from typing import Dict, Any


def build_embedding_snapshot_v1(lead: Dict[str, Any]) -> str:
    """
    Build a stable, minimal text snapshot for embeddings (structural state, not verbose LLM text).
    Use objective_intelligence + competitive_snapshot + key service gap flags.
    No numbers invented.
    Keep under 5k chars (truncate).
    Returns "" if objective_intelligence missing (skip embedding).
    """
    oi = lead.get("objective_intelligence")
    if not oi or not isinstance(oi, dict):
        return ""

    parts = ["vertical: dentist"]

    # root_constraint
    rc = oi.get("root_constraint") or {}
    label = (rc.get("label") or "").strip()
    if label:
        parts.append(f"constraint: {label}")

    # primary_growth_vector
    pgv = oi.get("primary_growth_vector") or {}
    pgv_label = (pgv.get("label") or "").strip()
    if pgv_label:
        parts.append(f"growth_vector: {pgv_label}")

    # competitive_profile
    cp = oi.get("competitive_profile") or {}
    market_density = (cp.get("market_density") or "").strip()
    if market_density:
        parts.append(f"market_density: {market_density}")
    review_tier = (cp.get("review_tier") or "").strip()
    if review_tier and review_tier != "—":
        parts.append(f"review_tier: {review_tier}")

    # service_intel
    si = oi.get("service_intel") or {}
    missing = si.get("missing_high_value_pages")
    if missing and isinstance(missing, list) and missing:
        parts.append(f"missing_pages: {', '.join(str(m) for m in missing[:10])}")
    schema = si.get("schema_detected")
    if schema is not None:
        parts.append(f"schema_missing: {not schema}")

    # google_ads_active from signals
    signals = lead.get("signals") or {}
    if not isinstance(signals, dict):
        signals = {k: v for k, v in lead.items() if k.startswith("signal_")}
    runs_ads = signals.get("signal_runs_paid_ads") is True
    channels = signals.get("signal_paid_ads_channels") or []
    if not isinstance(channels, list):
        channels = [channels] if channels else []
    channels_lower = [str(c).strip().lower() for c in channels if c]
    google_active = runs_ads and "google" in channels_lower
    parts.append(f"google_ads_active: {str(google_active).lower()}")

    out = " | ".join(parts)
    if len(out) > 5000:
        return out[:5000]
    return out
