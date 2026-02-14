"""
Meta Ads Library API client.

Uses META_ACCESS_TOKEN to query the Ads Library (ads_archive) and
confirm whether a business runs Meta ads. Used to augment runs_paid_ads
and paid_ads_channels (evidence source: Meta Ads Library).

Environment:
    META_ACCESS_TOKEN: App or User token with Ads Library API access.

Note: For US, the API returns political/issue ads; commercial ads may
not appear. A hit = confirmed Meta ads. No hit ≠ not running ads (leave
existing signal unchanged).
"""

import os
import time
import logging
from typing import Dict, Optional, List, Any

import requests

logger = logging.getLogger(__name__)

# Meta Graph API
META_ADS_ARCHIVE_URL = "https://graph.facebook.com/v21.0/ads_archive"

# Fields for structured paid intelligence (creation time, body, link caption, snapshot)
META_ADS_ARCHIVE_FIELDS = "ad_creation_time,ad_creative_body,ad_creative_link_caption,ad_snapshot_url"

# Rate limit: avoid 613 (too many calls). Be conservative.
META_REQUEST_DELAY_SEC = 0.5

# Timeout per request
REQUEST_TIMEOUT = 15


def get_meta_access_token() -> Optional[str]:
    """Get Meta access token from environment (stripped of whitespace)."""
    raw = os.getenv("META_ACCESS_TOKEN")
    return raw.strip() if raw else None


def check_meta_ads(
    business_name: str,
    country: str = "US",
    ad_type: str = "ALL",
) -> Dict:
    """
    Query Meta Ads Library for ads matching the business name.

    When we get one or more ads, we treat that as "runs Meta ads".
    When we get zero ads, we do NOT set false (US only returns
    political/issue for many regions; commercial may be missing).

    Args:
        business_name: Business or advertiser name to search.
        country: ISO country code, e.g. "US".
        ad_type: "ALL" or "POLITICAL_AND_ISSUE_ADS". For US, ALL
                 may return nothing; POLITICAL_AND_ISSUE_ADS is
                 the only guaranteed US type.

    Returns:
        {
            "runs_meta_ads": True if ads found, None if no ads or error,
            "ad_count": number of ad objects returned,
            "source": "meta_ads_library",
            "error": optional error message,
        }
    """
    token = get_meta_access_token()
    if not token:
        return {
            "runs_meta_ads": None,
            "ad_count": 0,
            "source": "meta_ads_library",
            "error": "META_ACCESS_TOKEN not set",
        }

    # Search by business name (keyword). API treats space as AND.
    search_terms = (business_name or "").strip()
    if not search_terms:
        return {
            "runs_meta_ads": None,
            "ad_count": 0,
            "source": "meta_ads_library",
            "error": "No business name to search",
        }

    # Limit search term length (API limit 100 chars)
    if len(search_terms) > 100:
        search_terms = search_terms[:100]

    params = {
        "access_token": token,
        "ad_reached_countries": f'["{country}"]',
        "ad_type": ad_type,
        "search_terms": search_terms,
    }

    try:
        resp = requests.get(
            META_ADS_ARCHIVE_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        data = resp.json()

        if "error" in data:
            err = data["error"]
            code = err.get("code")
            msg = err.get("message", "Unknown error")
            logger.debug("Meta Ads Library API error: %s (code %s)", msg, code)
            # Hint when token is invalid so user can fix without re-pasting token in chat
            if "access token" in msg.lower() or "parse" in msg.lower() or code in (190, 102):
                logger.warning(
                    "Meta Ads Library: invalid or expired token. "
                    "Generate a new token at developers.facebook.com and set META_ACCESS_TOKEN again."
                )
            return {
                "runs_meta_ads": None,
                "ad_count": 0,
                "source": "meta_ads_library",
                "error": msg,
            }

        ad_list = data.get("data") or []
        ad_count = len(ad_list)

        return {
            "runs_meta_ads": True if ad_count > 0 else None,
            "ad_count": ad_count,
            "source": "meta_ads_library",
        }

    except requests.exceptions.Timeout:
        logger.debug("Meta Ads Library request timeout for %s", business_name[:30])
        return {
            "runs_meta_ads": None,
            "ad_count": 0,
            "source": "meta_ads_library",
            "error": "Request timeout",
        }
    except requests.exceptions.RequestException as e:
        logger.debug("Meta Ads Library request failed: %s", e)
        return {
            "runs_meta_ads": None,
            "ad_count": 0,
            "source": "meta_ads_library",
            "error": str(e),
        }


def fetch_ads_archive_detailed(
    business_name: str,
    country: str = "US",
    ad_type: str = "ALL",
    fields: Optional[str] = None,
) -> Dict:
    """
    Query Ads Library with optional fields for structured intelligence.
    Returns full API response with data[] (list of ad objects) for downstream extraction.
    """
    token = get_meta_access_token()
    if not token:
        return {"data": [], "source": "meta_ads_library", "error": "META_ACCESS_TOKEN not set"}

    search_terms = (business_name or "").strip()[:100]
    if not search_terms:
        return {"data": [], "source": "meta_ads_library", "error": "No business name to search"}

    params = {
        "access_token": token,
        "ad_reached_countries": f'["{country}"]',
        "ad_type": ad_type,
        "search_terms": search_terms,
    }
    if fields:
        params["fields"] = fields

    try:
        resp = requests.get(META_ADS_ARCHIVE_URL, params=params, timeout=REQUEST_TIMEOUT)
        data = resp.json()
        if "error" in data:
            return {
                "data": [],
                "source": "meta_ads_library",
                "error": data["error"].get("message", "Unknown error"),
            }
        return {
            "data": data.get("data") or [],
            "paging": data.get("paging"),
            "source": "meta_ads_library",
        }
    except requests.exceptions.RequestException as e:
        logger.debug("Meta Ads Library detailed request failed: %s", e)
        return {"data": [], "source": "meta_ads_library", "error": str(e)}


def augment_lead_with_meta_ads(
    lead: Dict,
    delay_seconds: float = META_REQUEST_DELAY_SEC,
    build_paid_intelligence_block: bool = True,
) -> None:
    """
    If META_ACCESS_TOKEN is set, query Ads Library by lead name (with optional
    detailed fields for paid_intelligence). Update paid-ads signals and optionally
    attach paid_intelligence.

    When build_paid_intelligence_block=True, fetches with ad_creation_time,
    ad_creative_body, etc., builds paid_intelligence (deterministic + optional LLM
    when ads found), and sets lead["paid_intelligence"]. No raw creative in output.
    """
    if not get_meta_access_token():
        return

    name = lead.get("name") or ""
    if build_paid_intelligence_block:
        response = fetch_ads_archive_detailed(
            business_name=name,
            country="US",
            ad_type="ALL",
            fields=META_ADS_ARCHIVE_FIELDS,
        )
        ad_list = response.get("data") or []
        ad_count = len(ad_list)
        if ad_count > 0:
            lead["signal_runs_paid_ads"] = True
            channels = lead.get("signal_paid_ads_channels")
            if isinstance(channels, list):
                if "meta" not in channels:
                    lead["signal_paid_ads_channels"] = channels + ["meta"]
            else:
                lead["signal_paid_ads_channels"] = ["meta"]
            lead["signal_meta_ads_source"] = "meta_ads_library"
            lead["signal_meta_ads_count"] = ad_count
            try:
                from pipeline.paid_intelligence import build_paid_intelligence
                lead["paid_intelligence"] = build_paid_intelligence(lead, response, use_llm=True)
            except Exception as e:
                logger.debug("build_paid_intelligence failed: %s", e)
                try:
                    lead["paid_intelligence"] = build_paid_intelligence(lead, {"data": ad_list}, use_llm=False)
                except Exception:
                    lead["paid_intelligence"] = _empty_paid_intelligence()
            logger.info("  Meta Ads Library: %s — %d ad(s) found", name[:40], ad_count)
        else:
            lead["paid_intelligence"] = _empty_paid_intelligence()
            err = response.get("error") or "no ads in library"
            logger.info("  Meta Ads Library: %s — %s", name[:40], err)
    else:
        result = check_meta_ads(business_name=name, country="US", ad_type="ALL")
        ad_count = result.get("ad_count", 0)
        if result.get("runs_meta_ads") is True:
            lead["signal_runs_paid_ads"] = True
            channels = lead.get("signal_paid_ads_channels")
            if isinstance(channels, list):
                if "meta" not in channels:
                    lead["signal_paid_ads_channels"] = channels + ["meta"]
            else:
                lead["signal_paid_ads_channels"] = ["meta"]
            lead["signal_meta_ads_source"] = "meta_ads_library"
            lead["signal_meta_ads_count"] = ad_count
            logger.info("  Meta Ads Library: %s — %d ad(s) found", name[:40], ad_count)
        else:
            err = result.get("error") or "no ads in library"
            logger.info("  Meta Ads Library: %s — %s", name[:40], err)

    time.sleep(delay_seconds)


def _empty_paid_intelligence() -> Dict[str, Any]:
    return {
        "active_ads": 0,
        "ad_duration_days": 0,
        "primary_service_promoted": None,
        "offer_detected": False,
        "high_ticket_focus": False,
        "cta_type": None,
        "confidence": 0,
    }


