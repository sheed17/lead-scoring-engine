"""
Lightweight competitor sampling for dental leads.

Uses Nearby Search (1.5 mi) to get top dentists, aggregates review_count and rating,
computes lead percentile and market density. Used for root bottleneck and comparative context.
"""

import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

RADIUS_M = 2414   # 1.5 miles
MAX_COMPETITORS = 5
KEYWORD = "dentist"


def fetch_competitors_nearby(
    lat: float,
    lng: float,
    exclude_place_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch up to MAX_COMPETITORS dentists within 1.5 mi; exclude lead's place_id."""
    try:
        from pipeline.fetch import PlacesFetcher  # noqa: avoid circular import
    except ImportError:
        logger.warning("PlacesFetcher not available; competitor sampling skipped")
        return []
    key = api_key or os.getenv("GOOGLE_PLACES_API_KEY")
    if not key:
        return []
    fetcher = PlacesFetcher(api_key=key)
    results = fetcher.fetch_nearby_places(lat=lat, lng=lng, radius_m=RADIUS_M, keyword=KEYWORD)
    out = []
    for p in results:
        pid = p.get("place_id")
        if pid and pid == exclude_place_id:
            continue
        out.append({
            "place_id": pid,
            "name": p.get("name"),
            "rating": p.get("rating"),
            "user_ratings_total": p.get("user_ratings_total", 0) or 0,
        })
        if len(out) >= MAX_COMPETITORS:
            break
    return out


def build_competitive_snapshot(
    lead: Dict,
    competitors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build competitive_snapshot from list of competitor dicts (place_id, rating, user_ratings_total).

    Includes: dentists_sampled, avg_review_count (competitor_avg_review_count), lead_review_count,
    review_positioning (Above/Below/In line with sample average), market_density_score, confidence.
    No percentile from small samples.
    """
    out = {
        "dentists_sampled": 0,
        "avg_review_count": 0.0,
        "avg_rating": 0.0,
        "percent_with_booking": None,
        "lead_review_count": None,
        "review_positioning": None,
        "market_density_score": "Low",
        "confidence": 0.0,
    }
    if not competitors:
        return out

    lead_count = lead.get("signal_review_count") or lead.get("review_count") or lead.get("user_ratings_total") or 0
    lead_count = int(lead_count)
    counts = [c.get("user_ratings_total") or 0 for c in competitors]
    ratings = [c.get("rating") for c in competitors if c.get("rating") is not None]

    out["dentists_sampled"] = len(competitors)
    out["lead_review_count"] = lead_count
    if counts:
        avg_rev = round(sum(counts) / len(counts), 1)
        out["avg_review_count"] = avg_rev
        # Review positioning vs sample average (no percentile from small samples)
        if lead_count > avg_rev:
            out["review_positioning"] = "Above sample average"
        elif lead_count < avg_rev:
            out["review_positioning"] = "Below sample average"
        else:
            out["review_positioning"] = "In line with sample average"
    if ratings:
        out["avg_rating"] = round(sum(ratings) / len(ratings), 2)

    # Market density: based on competitor count and avg review volume
    n = len(competitors)
    avg = out["avg_review_count"] or 0
    if n >= 5 and avg >= 80:
        out["market_density_score"] = "High"
    elif n >= 3 or avg >= 40:
        out["market_density_score"] = "Moderate"
    else:
        out["market_density_score"] = "Low"

    out["confidence"] = round(min(1.0, 0.4 + 0.15 * len(competitors)), 2)
    return out
