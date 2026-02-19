"""
Lightweight competitor sampling for dental leads.

Uses Nearby Search with tiered radius (2 mi → 5 mi → 8 mi). Tracks search_radius_used_miles.
Distance-aware competitor dicts (haversine). competitive_profile labels only; no numeric scores.
No percentiles. No LLM. Deterministic.
"""

import os
import math
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Tiered radius (meters): 2 mi → 5 mi → 8 mi (hard stop)
RADIUS_BASE_M = 3218   # 2 miles
RADIUS_MID_M = 8046    # 5 miles
RADIUS_MAX_M = 12874   # 8 miles
MAX_COMPETITORS = 8
KEYWORD = "dentist"
MIN_COMPETITORS_BEFORE_EXPAND = 5

KM_PER_MILE = 1.609344
MILES_PER_KM = 1.0 / KM_PER_MILE


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance between two points in miles (deterministic)."""
    R_KM = 6371.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R_KM * c * MILES_PER_KM, 1)


def fetch_competitors_nearby(
    lat: float,
    lng: float,
    exclude_place_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Fetch up to MAX_COMPETITORS dentists using tiered radius.
    Base radius = 2 mi. If fewer than 5 competitors → expand to 5 mi.
    If still fewer than 5 → expand to 8 mi. Hard stop after 8 mi.

    Returns (competitors, search_radius_used_miles) where competitors have:
    name, rating, reviews, distance_miles (from lead; 1 decimal).
    search_radius_used_miles is 2, 5, or 8.
    """
    try:
        from pipeline.fetch import PlacesFetcher  # noqa: avoid circular import
    except ImportError:
        logger.warning("PlacesFetcher not available; competitor sampling skipped")
        return ([], 2)
    key = api_key or os.getenv("GOOGLE_PLACES_API_KEY")
    if not key:
        return ([], 2)

    fetcher = PlacesFetcher(api_key=key)
    radius_used_miles = 2

    def raw_to_competitor(p: Dict, lead_lat: float, lead_lng: float) -> Optional[Dict[str, Any]]:
        if not p.get("place_id"):
            return None
        loc = (p.get("geometry") or {}).get("location") or {}
        plat, plng = loc.get("lat"), loc.get("lng")
        if plat is None or plng is None:
            return None
        dist = _haversine_miles(lead_lat, lead_lng, float(plat), float(plng))
        rating = p.get("rating")
        reviews = p.get("user_ratings_total") or 0
        return {
            "name": p.get("name") or "",
            "rating": float(rating) if rating is not None else None,
            "reviews": int(reviews),
            "distance_miles": dist,
        }

    def fetch_at_radius(radius_m: int) -> List[Dict[str, Any]]:
        raw = fetcher.fetch_nearby_places(lat=lat, lng=lng, radius_m=radius_m, keyword=KEYWORD)
        out = []
        seen_pids = set()
        for p in raw:
            pid = p.get("place_id")
            if pid == exclude_place_id or pid in seen_pids:
                continue
            c = raw_to_competitor(p, lat, lng)
            if c:
                seen_pids.add(pid)
                out.append(c)
        return out

    seen_names: set = set()
    out: List[Dict[str, Any]] = []

    def add_from(candidates: List[Dict[str, Any]]) -> None:
        for c in candidates:
            key = (c.get("name") or "").strip() or str(c.get("distance_miles"))
            if key in seen_names:
                continue
            seen_names.add(key)
            out.append(c)
            if len(out) >= MAX_COMPETITORS:
                return

    base_list = fetch_at_radius(RADIUS_BASE_M)
    add_from(base_list)
    if len(out) >= MIN_COMPETITORS_BEFORE_EXPAND:
        radius_used_miles = 2
    else:
        mid_list = fetch_at_radius(RADIUS_MID_M)
        add_from(mid_list)
        if len(out) >= MIN_COMPETITORS_BEFORE_EXPAND:
            radius_used_miles = 5
        else:
            max_list = fetch_at_radius(RADIUS_MAX_M)
            add_from(max_list)
            radius_used_miles = 8

    return (out[:MAX_COMPETITORS], radius_used_miles)


def _review_positioning_tier(review_ratio: Optional[float]) -> Optional[str]:
    if review_ratio is None:
        return None
    if review_ratio >= 1.75:
        return "Dominant"
    if review_ratio >= 1.2:
        return "Above Average"
    if review_ratio >= 0.8:
        return "Competitive"
    if review_ratio >= 0.5:
        return "Below Average"
    return "Weak"


def build_competitive_snapshot(
    lead: Dict,
    competitors: List[Dict[str, Any]],
    search_radius_used_miles: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Build competitive_snapshot. No percentiles, no numeric pressure scores.
    Schema: dentists_sampled, search_radius_used_miles, avg_review_count, avg_rating,
    lead_review_count, review_positioning_tier, review_positioning, market_density_score,
    competitive_profile, competitor_summary (nearest, strongest by reviews),
    competitive_context_summary, confidence.
    """
    out: Dict[str, Any] = {
        "dentists_sampled": 0,
        "search_radius_used_miles": search_radius_used_miles if search_radius_used_miles is not None else 2,
        "avg_review_count": 0.0,
        "avg_rating": 0.0,
        "lead_review_count": None,
        "review_positioning_tier": None,
        "review_positioning": None,
        "market_density_score": "Low",
        "competitive_profile": {},
        "competitor_summary": {},
        "competitive_context_summary": None,
        "confidence": 0.0,
    }

    if not competitors:
        out["competitor_summary"] = {}
        return out

    lead_count = lead.get("signal_review_count") or lead.get("review_count") or lead.get("user_ratings_total") or 0
    lead_count = int(lead_count)
    counts = [c.get("reviews") or c.get("user_ratings_total") or 0 for c in competitors]
    ratings = [c.get("rating") for c in competitors if c.get("rating") is not None]

    n = len(competitors)
    out["dentists_sampled"] = n
    out["lead_review_count"] = lead_count
    if search_radius_used_miles is not None:
        out["search_radius_used_miles"] = search_radius_used_miles

    avg_rev = 0.0
    if counts:
        avg_rev = round(sum(counts) / len(counts), 1)
        out["avg_review_count"] = avg_rev
        review_ratio = (lead_count / avg_rev) if avg_rev > 0 else None
        out["review_positioning_tier"] = _review_positioning_tier(review_ratio)
        if lead_count > avg_rev:
            out["review_positioning"] = "Above sample average"
        elif lead_count < avg_rev:
            out["review_positioning"] = "Below sample average"
        else:
            out["review_positioning"] = "In line with sample average"

    avg_rating = 0.0
    if ratings:
        avg_rating = round(sum(ratings) / len(ratings), 2)
        out["avg_rating"] = avg_rating

    # Market density
    if n >= 6 and avg_rev >= 100:
        out["market_density_score"] = "High"
    elif n >= 4 or avg_rev >= 60:
        out["market_density_score"] = "Moderate"
    else:
        out["market_density_score"] = "Low"

    # competitive_profile (labels only)
    review_volume_profile = "Low Volume Market"
    if avg_rev >= 150:
        review_volume_profile = "High Volume Market"
    elif avg_rev >= 60:
        review_volume_profile = "Moderate Volume Market"

    competitor_strength_profile = "Weak"
    if avg_rating >= 4.5:
        competitor_strength_profile = "Strong"
    elif avg_rating >= 4.0:
        competitor_strength_profile = "Mixed"

    competitive_intensity = "Fragmented"
    if n >= 6 and avg_rev >= 100:
        competitive_intensity = "Crowded & Established"
    elif n >= 4:
        competitive_intensity = "Competitive"

    out["competitive_profile"] = {
        "review_volume_profile": review_volume_profile,
        "competitor_strength_profile": competitor_strength_profile,
        "competitive_intensity": competitive_intensity,
    }

    # competitor_summary: nearest_competitor, strongest_competitor_by_reviews, nearest_competitors (top 3)
    entries = []
    nearest = None
    strongest = None
    for c in competitors:
        dist = c.get("distance_miles")
        revs = c.get("reviews") or c.get("user_ratings_total") or 0
        entry = {
            "name": c.get("name") or "",
            "rating": c.get("rating"),
            "reviews": revs,
            "distance_miles": dist,
        }
        entries.append(entry)
        if dist is not None and (nearest is None or dist < nearest.get("distance_miles", float("inf"))):
            nearest = entry.copy()
        if strongest is None or revs > (strongest.get("reviews") or 0):
            strongest = entry.copy()

    if nearest is not None:
        out["competitor_summary"]["nearest_competitor"] = nearest
    if strongest is not None:
        out["competitor_summary"]["strongest_competitor_by_reviews"] = strongest

    # nearest_competitors: top 3 by distance_miles (if available), else top 3 by reviews
    has_dist = any(e.get("distance_miles") is not None for e in entries)
    if has_dist:
        sorted_entries = sorted(entries, key=lambda e: (e.get("distance_miles") if e.get("distance_miles") is not None else float("inf"), -(e.get("reviews") or 0)))
    else:
        sorted_entries = sorted(entries, key=lambda e: -(e.get("reviews") or 0))
    out["competitor_summary"]["nearest_competitors"] = sorted_entries[:3]

    # competitive_context_summary
    tier = out.get("review_positioning_tier") or "—"
    density = out["market_density_score"]
    radius = out.get("search_radius_used_miles") or 2
    out["competitive_context_summary"] = (
        f"{lead_count} reviews vs {avg_rev:.0f} local avg across {n} dentists within {radius} miles. "
        f"Market is {density}. Review tier: {tier}."
    )

    out["confidence"] = round(min(1.0, 0.4 + 0.15 * n), 2)
    return out
