"""
SERP presence snapshot (optional).

Uses SerpAPI when SERPAPI_API_KEY is available. Non-blocking; returns None on
missing configuration or request errors.
"""

from __future__ import annotations

import datetime as _dt
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests


def _normalize_domain(url_or_domain: str) -> str:
    val = (url_or_domain or "").strip().lower()
    if not val:
        return ""
    if "://" not in val:
        val = "https://" + val
    parsed = urlparse(val)
    return (parsed.netloc or "").replace("www.", "")


def _seed_keywords(city: str) -> List[str]:
    c = (city or "").strip()
    if not c:
        return []
    return [
        f"dentist in {c}",
        f"invisalign {c}",
        f"dental implants {c}",
    ]


def _page_type_from_url(url: str) -> str:
    p = (urlparse(url).path or "").lower()
    if any(x in p for x in ("/blog", "/article", "/news")):
        return "blog"
    if any(x in p for x in ("/service", "/services", "/treatment", "/procedure")):
        return "service"
    if any(x in p for x in ("/location", "/locations", "/area", "/areas-we-serve")):
        return "location"
    return "other"


def build_serp_presence(
    city: str,
    state: Optional[str],
    website_url: Optional[str],
    keywords: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    api_key = os.getenv("SERPAPI_API_KEY")
    domain = _normalize_domain(website_url or "")
    if not api_key or not domain:
        return None

    kws = keywords or _seed_keywords(city)
    if not kws:
        return None

    rows: List[Dict[str, Any]] = []
    for kw in kws[:6]:
        try:
            params = {
                "engine": "google",
                "q": kw,
                "num": 10,
                "api_key": api_key,
                "gl": "us",
                "hl": "en",
            }
            resp = requests.get("https://serpapi.com/search.json", params=params, timeout=15)
            if resp.status_code != 200:
                rows.append({"keyword": kw, "position": None, "in_top_10": False, "page_type": None})
                continue
            data = resp.json() if resp.content else {}
            organic = data.get("organic_results") or []
            pos = None
            found_url = None
            for i, r in enumerate(organic[:10], start=1):
                link = str(r.get("link") or "").strip()
                if not link:
                    continue
                if _normalize_domain(link) == domain:
                    pos = i
                    found_url = link
                    break
            rows.append(
                {
                    "keyword": kw,
                    "position": pos,
                    "in_top_10": bool(pos is not None),
                    "page_type": _page_type_from_url(found_url) if found_url else None,
                }
            )
        except Exception:
            rows.append({"keyword": kw, "position": None, "in_top_10": False, "page_type": None})

    return {
        "domain": domain,
        "keywords": rows,
        "as_of_date": _dt.datetime.utcnow().date().isoformat(),
        "provider": "serpapi",
    }

