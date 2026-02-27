"""
Natural-language prospect lookup parsing + Tier-1 / lightweight criteria helpers.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import requests


SERVICE_TOKENS = [
    "implants",
    "invisalign",
    "orthodontics",
    "veneers",
    "emergency",
    "cosmetic",
    "sedation",
    "crowns",
]

EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def parse_npl_query(query: str) -> Dict[str, Any]:
    q = " ".join((query or "").strip().split())
    if not q:
        raise ValueError("Query is required")
    ql = q.lower()

    limit = 10
    m_limit = re.search(r"\b(?:find|top)\s+(\d{1,3})\b", ql)
    if m_limit:
        limit = int(m_limit.group(1))
    limit = max(1, min(limit, 25))

    vertical = "dentist"
    if "orthodontist" in ql:
        vertical = "orthodontist"
    elif "dental" in ql or "dentist" in ql:
        vertical = "dentist"

    city: Optional[str] = None
    state: Optional[str] = None
    m_place = re.search(r"\bin\s+(.+?)(?:\s+(?:that|with|who)\b|$)", q, flags=re.IGNORECASE)
    if m_place:
        place_raw = m_place.group(1).strip(" .")
        if "," in place_raw:
            parts = [p.strip() for p in place_raw.split(",") if p.strip()]
            if parts:
                city = parts[0]
            if len(parts) >= 2:
                state = parts[1]
        else:
            m_st = re.match(r"(.+?)\s+([A-Za-z]{2})$", place_raw)
            if m_st:
                city = m_st.group(1).strip()
                state = m_st.group(2).upper()
            else:
                city = place_raw

    if not city:
        raise ValueError("Could not parse city from query. Try: 'Find 10 dentists in San Jose CA ...'")

    criteria: List[Dict[str, Any]] = []

    if "below review average" in ql or "below review avg" in ql or "low review" in ql or "review gap" in ql:
        criteria.append({"type": "below_review_avg"})

    if "has website" in ql:
        criteria.append({"type": "has_website"})
    elif "no website" in ql or "without website" in ql:
        criteria.append({"type": "no_website"})

    if "high leverage" in ql or "high-leverage" in ql:
        criteria.append({"type": "high_leverage_proxy"})

    for svc in SERVICE_TOKENS:
        if re.search(rf"\bmissing\s+{re.escape(svc)}\b", ql) or re.search(rf"\bno\s+{re.escape(svc)}\b", ql):
            criteria.append({"type": "missing_service_page_light", "service": svc})
            break

    if not any(c.get("type") == "missing_service_page_light" for c in criteria):
        m_missing = re.search(r"\bmissing\s+([a-z ]+?)\s+page\b", ql)
        if m_missing:
            criteria.append({"type": "missing_service_page_light", "service": m_missing.group(1).strip()})

    requires_lightweight = any(c.get("type") == "missing_service_page_light" for c in criteria)

    return {
        "query": q,
        "city": city,
        "state": state,
        "vertical": vertical,
        "limit": limit,
        "criteria": criteria,
        "requires_lightweight": requires_lightweight,
        "requires_deep": False,
    }


def matches_tier1_criteria(criteria: List[Dict[str, Any]], row: Dict[str, Any]) -> bool:
    """Match criteria that can be evaluated from Tier-1 row data only."""
    if not criteria:
        return True

    snapshot = row.get("tier1_snapshot") or {}
    avg_reviews = snapshot.get("avg_market_reviews")
    lead_reviews = row.get("user_ratings_total")

    for c in criteria:
        ctype = c.get("type")
        if ctype == "below_review_avg":
            try:
                if avg_reviews is None or lead_reviews is None:
                    return False
                if float(lead_reviews) >= float(avg_reviews):
                    return False
            except (TypeError, ValueError):
                return False
        elif ctype == "has_website":
            if not row.get("website"):
                return False
        elif ctype == "no_website":
            if row.get("website"):
                return False
        elif ctype == "high_leverage_proxy":
            proxy = 0
            if row.get("below_review_avg"):
                proxy += 1
            if not row.get("has_schema"):
                proxy += 1
            if not row.get("has_contact_form"):
                proxy += 1
            if not row.get("has_website"):
                proxy += 1
            if proxy < 2:
                return False
    return True


def needs_lightweight_check(criteria: List[Dict[str, Any]]) -> bool:
    return any(c.get("type") == "missing_service_page_light" for c in criteria)


def criterion_cache_key(criterion: Dict[str, Any]) -> str:
    ctype = str(criterion.get("type") or "unknown")
    service = str(criterion.get("service") or "").strip().lower().replace(" ", "_")
    return f"{ctype}:{service}" if service else ctype


def run_lightweight_service_page_check(
    website: Optional[str],
    criterion: Dict[str, Any],
    timeout_seconds: int = 5,
) -> Dict[str, Any]:
    """Homepage-first heuristic for service page presence.

    Returns a payload with `matches` indicating criterion pass/fail.
    For "missing service page" criteria, matches=True means likely missing.
    """
    service = str(criterion.get("service") or "").strip().lower()
    if not website or not service:
        return {
            "criterion": criterion,
            "matches": False,
            "reason": "missing website or service",
            "service": service,
            "service_mentioned": False,
            "dedicated_page_detected": False,
        }

    url = website if website.startswith(("http://", "https://")) else f"https://{website}"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Neyma Ask Lightweight)"},
            timeout=(3, timeout_seconds),
            allow_redirects=True,
        )
        html = (resp.text or "")[:350000]
    except Exception:
        return {
            "criterion": criterion,
            "matches": False,
            "reason": "homepage fetch failed",
            "service": service,
            "service_mentioned": False,
            "dedicated_page_detected": False,
        }

    lower = html.lower()
    service_terms = [service]
    if service == "implants":
        service_terms.extend(["implant", "dental implant"])
    elif service == "invisalign":
        service_terms.extend(["invisalign", "clear aligner", "clear aligners"])

    service_mentioned = any(t in lower for t in service_terms)

    hrefs = [h.lower() for h in re.findall(r"href=['\"]([^'\"]+)['\"]", lower)]
    dedicated_page_detected = any(
        any(tok in h for tok in [service.replace(" ", "-"), service.replace(" ", ""), service])
        and ("/" in h)
        and ("http" in h or h.startswith("/"))
        for h in hrefs
    )

    if not dedicated_page_detected:
        path = urlsplit(str(resp.url or url)).path.lower()
        if service.replace(" ", "") in path or service.replace(" ", "-") in path:
            dedicated_page_detected = True

    matches = not dedicated_page_detected
    return {
        "criterion": criterion,
        "matches": bool(matches),
        "reason": "heuristic",
        "service": service,
        "service_mentioned": bool(service_mentioned),
        "dedicated_page_detected": bool(dedicated_page_detected),
    }
