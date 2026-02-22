"""
Semantic signals: deterministic, opinion-free mapping from raw signals to six axes.

Used by the Decision Agent as a stable input vocabulary. No verdicts, no HIGH/MEDIUM/LOW.
Pure functions; no LLM; no API calls.
"""

from typing import Dict, Any

# Six axes for the Decision Agent (plan: growth_intent, rankability, digital_maturity, data_maturity, execution_friction, client_risk)
SEMANTIC_KEYS = [
    "growth_intent",
    "rankability",
    "digital_maturity",
    "data_maturity",
    "execution_friction",
    "client_risk",
]


def _normalize_raw(lead_or_signals: Dict[str, Any]) -> Dict[str, Any]:
    """Accept lead (signal_* keys) or raw signals; return plain key signals."""
    out = {}
    for key, value in lead_or_signals.items():
        if key.startswith("signal_"):
            out[key[7:]] = value
        else:
            out[key] = value
    return out


def _label(key: str, value: Any) -> str:
    """Factual label for a signal value (no verdict)."""
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return f"list_len_{len(value)}"
    s = str(value).strip()
    return s[:80] if s else "unknown"


def _growth_intent(signals: Dict[str, Any]) -> str:
    """Growth intent: hiring, paid ads, review activity (factual only)."""
    parts = []
    hiring = signals.get("hiring_active")
    if hiring is not None:
        parts.append(f"hiring_active_{_label('hiring_active', hiring)}")
    runs_ads = signals.get("runs_paid_ads")
    if runs_ads is not None:
        parts.append(f"runs_paid_ads_{_label('runs_paid_ads', runs_ads)}")
    channels = signals.get("paid_ads_channels")
    if channels and isinstance(channels, list):
        parts.append(f"paid_ads_channels_{','.join(channels[:3])}")
    review_count = signals.get("review_count")
    if review_count is not None:
        parts.append(f"review_count_{review_count}")
    last_review = signals.get("last_review_days_ago")
    if last_review is not None:
        parts.append(f"last_review_days_{last_review}")
    return "__".join(parts) if parts else "unknown"


def _rankability(signals: Dict[str, Any]) -> str:
    """Rankability / SEO technical base: website, schema, content signals (factual only)."""
    parts = []
    has_website = signals.get("has_website")
    if has_website is not None:
        parts.append(f"has_website_{_label('has_website', has_website)}")
    schema = signals.get("has_schema_microdata")
    if schema is not None:
        parts.append(f"has_schema_{_label('has_schema_microdata', schema)}")
    schema_types = signals.get("schema_types")
    if schema_types and isinstance(schema_types, list):
        parts.append(f"schema_types_{','.join(schema_types[:3])}")
    mobile = signals.get("mobile_friendly")
    if mobile is not None:
        parts.append(f"mobile_friendly_{_label('mobile_friendly', mobile)}")
    return "__".join(parts) if parts else "unknown"


def _digital_maturity(signals: Dict[str, Any]) -> str:
    """Digital maturity: website, SSL, mobile, scheduling (factual only)."""
    parts = []
    has_website = signals.get("has_website")
    if has_website is not None:
        parts.append(f"has_website_{_label('has_website', has_website)}")
    has_ssl = signals.get("has_ssl")
    if has_ssl is not None:
        parts.append(f"has_ssl_{_label('has_ssl', has_ssl)}")
    mobile = signals.get("mobile_friendly")
    if mobile is not None:
        parts.append(f"mobile_friendly_{_label('mobile_friendly', mobile)}")
    scheduling = signals.get("has_automated_scheduling")
    if scheduling is not None:
        parts.append(f"has_automated_scheduling_{_label('has_automated_scheduling', scheduling)}")
    accessible = signals.get("website_accessible")
    if accessible is not None:
        parts.append(f"website_accessible_{_label('website_accessible', accessible)}")
    return "__".join(parts) if parts else "unknown"


def _data_maturity(signals: Dict[str, Any]) -> str:
    """Data maturity: what we know (reviews, rating, recency) (factual only)."""
    parts = []
    review_count = signals.get("review_count")
    if review_count is not None:
        parts.append(f"review_count_{review_count}")
    rating = signals.get("rating")
    if rating is not None:
        parts.append(f"rating_{rating}")
    last_review = signals.get("last_review_days_ago")
    if last_review is not None:
        parts.append(f"last_review_days_{last_review}")
    velocity = signals.get("review_velocity_30d")
    if velocity is not None:
        parts.append(f"review_velocity_30d_{velocity}")
    return "__".join(parts) if parts else "unknown"


def _execution_friction(signals: Dict[str, Any]) -> str:
    """Execution friction: contact form, phone, scheduling (factual only)."""
    parts = []
    form = signals.get("has_contact_form")
    if form is not None:
        parts.append(f"has_contact_form_{_label('has_contact_form', form)}")
    phone = signals.get("has_phone")
    if phone is not None:
        parts.append(f"has_phone_{_label('has_phone', phone)}")
    scheduling = signals.get("has_automated_scheduling")
    if scheduling is not None:
        parts.append(f"has_automated_scheduling_{_label('has_automated_scheduling', scheduling)}")
    email = signals.get("has_email")
    if email is not None:
        parts.append(f"has_email_{_label('has_email', email)}")
    return "__".join(parts) if parts else "unknown"


def _client_risk(signals: Dict[str, Any]) -> str:
    """Client risk: reputation/review signals (factual only)."""
    parts = []
    review_count = signals.get("review_count")
    if review_count is not None:
        parts.append(f"review_count_{review_count}")
    rating = signals.get("rating")
    if rating is not None:
        parts.append(f"rating_{rating}")
    last_review = signals.get("last_review_days_ago")
    if last_review is not None:
        parts.append(f"last_review_days_{last_review}")
    delta = signals.get("rating_delta_60d")
    if delta is not None:
        parts.append(f"rating_delta_60d_{delta}")
    return "__".join(parts) if parts else "unknown"


def build_semantic_signals(lead_or_signals: Dict[str, Any]) -> Dict[str, str]:
    """
    Map raw signals to six semantic axes. Deterministic and opinion-free.

    Args:
        lead_or_signals: Lead dict with signal_* keys, or raw signals dict.

    Returns:
        Dict with exactly: growth_intent, rankability, digital_maturity,
        data_maturity, execution_friction, client_risk. Values are short
        factual labels (no verdicts).
    """
    signals = _normalize_raw(lead_or_signals)
    return {
        "growth_intent": _growth_intent(signals),
        "rankability": _rankability(signals),
        "digital_maturity": _digital_maturity(signals),
        "data_maturity": _data_maturity(signals),
        "execution_friction": _execution_friction(signals),
        "client_risk": _client_risk(signals),
    }
