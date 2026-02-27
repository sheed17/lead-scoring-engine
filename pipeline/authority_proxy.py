"""
Internal authority proxy (clearly labeled, deterministic).
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _norm(v: Optional[float], low: float, high: float) -> float:
    if v is None:
        return 0.0
    if high <= low:
        return 0.0
    x = (float(v) - low) / (high - low)
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return x


def build_authority_proxy(
    service_intelligence: Dict[str, Any],
    serp_presence: Optional[Dict[str, Any]] = None,
    domain_age_years: Optional[float] = None,
) -> Dict[str, Any]:
    page_count = int(service_intelligence.get("pages_crawled") or 0)
    blog_page_count = int(service_intelligence.get("blog_page_count") or 0)
    serp_appearances = 0
    if serp_presence and isinstance(serp_presence.get("keywords"), list):
        serp_appearances = sum(1 for k in serp_presence["keywords"] if isinstance(k, dict) and k.get("in_top_10"))

    # Methodology:
    # score = 40% page count + 20% blog coverage + 20% serp appearances + 20% domain age
    score = (
        0.40 * _norm(page_count, 0, 120)
        + 0.20 * _norm(blog_page_count, 0, 50)
        + 0.20 * _norm(serp_appearances, 0, 6)
        + 0.20 * _norm(domain_age_years, 0, 15)
    )
    authority_score = round(score * 100, 1)

    return {
        "page_count": page_count,
        "blog_page_count": blog_page_count,
        "domain_age_years": domain_age_years,
        "serp_keyword_appearances": serp_appearances,
        "authority_proxy_score": authority_score,
        "methodology": "Weighted proxy: 40% page count, 20% blog pages, 20% SERP top-10 appearances, 20% domain age (when available). Not a Domain Rating.",
    }

