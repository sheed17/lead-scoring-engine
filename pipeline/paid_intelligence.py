"""
Structured Meta Ads Library intelligence: paid_intelligence object.

Deterministic extraction from Ads Library response (active_ad_count, dates, duration,
service keywords, CTA type). Optional LLM when active_ad_count > 0 for service focus,
promotional vs brand, urgency, high_ticket_focus. No raw ad creative in summary.
"""

import re
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Service keywords (dental) for deterministic detection
SERVICE_KEYWORDS = re.compile(
    r"\b(implants?|implant|invisalign|veneers?|veneer|emergency\s*dental?|cleaning|teeth\s*whitening|"
    r"cosmetic\s*dentist|orthodontics?|braces|crowns?|root\s*canal|extraction|sedation)\b",
    re.I,
)
HIGH_TICKET_KEYWORDS = re.compile(
    r"\b(implant|invisalign|veneers?|cosmetic|orthodontics?|sedation)\b",
    re.I,
)
OFFER_PATTERNS = re.compile(
    r"\b(free\s*exam|special\s*offer|\$\d+|%\s*off|new\s*patient\s*deal|discount)\b",
    re.I,
)
# CTA: common Meta CTA types
CTA_PATTERNS = {
    "Call now": re.compile(r"call\s*now|call\s*today|phone", re.I),
    "Book now": re.compile(r"book\s*now|schedule|appointment|book\s*online", re.I),
    "Learn more": re.compile(r"learn\s*more|see\s*more|get\s*started", re.I),
}


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _extract_deterministic(ad_list: List[Dict]) -> Dict[str, Any]:
    """Extract active_ad_count, earliest/most_recent_ad_date, ad_duration_days, unique_creative_count, service_keywords_detected, cta_type."""
    out = {
        "active_ad_count": 0,
        "earliest_ad_date": None,
        "most_recent_ad_date": None,
        "ad_duration_days": 0,
        "unique_creative_count": 0,
        "service_keywords_detected": [],
        "cta_type": None,
    }
    if not ad_list:
        return out

    dates = []
    bodies: List[str] = []
    all_text = ""
    cta_seen: List[str] = []

    for ad in ad_list:
        if not isinstance(ad, dict):
            continue
        created = ad.get("ad_creation_time")
        if created:
            dt = _parse_date(created)
            if dt:
                dates.append(dt)
        body = (ad.get("ad_creative_body") or "").strip()
        if body:
            bodies.append(body[:500])
            all_text += " " + body
        link_cap = (ad.get("ad_creative_link_caption") or "").strip()
        if link_cap:
            all_text += " " + link_cap

    out["active_ad_count"] = len(ad_list)
    if dates:
        out["earliest_ad_date"] = min(dates).isoformat()
        out["most_recent_ad_date"] = max(dates).isoformat()
        out["ad_duration_days"] = (max(dates) - min(dates)).days
    out["unique_creative_count"] = len(set(bodies)) if bodies else 0

    for m in SERVICE_KEYWORDS.findall(all_text):
        m = m.strip().lower()
        if m and m not in out["service_keywords_detected"]:
            out["service_keywords_detected"].append(m)
    out["service_keywords_detected"] = out["service_keywords_detected"][:15]

    for cta_label, pat in CTA_PATTERNS.items():
        if pat.search(all_text) and cta_label not in cta_seen:
            cta_seen.append(cta_label)
    out["cta_type"] = cta_seen[0] if cta_seen else None

    return out


def _primary_service_from_keywords(keywords: List[str]) -> str:
    """Pick one primary service label for display."""
    if not keywords:
        return ""
    order = ["implant", "invisalign", "veneer", "cosmetic", "emergency", "orthodontic", "cleaning"]
    for o in order:
        for k in keywords:
            if o in k:
                return o.replace("_", " ").title()
    return (keywords[0].replace("_", " ").title()) if keywords else ""


def _high_ticket_from_keywords(keywords: List[str], all_text: str) -> bool:
    return bool(keywords and HIGH_TICKET_KEYWORDS.search(" ".join(keywords))) or bool(
        HIGH_TICKET_KEYWORDS.search(all_text)
    )


def _offer_detected(all_text: str) -> bool:
    return bool(OFFER_PATTERNS.search(all_text))


def _confidence(ext: Dict, has_llm: bool) -> int:
    """0-100 from data quality and optional LLM."""
    score = 40
    if ext.get("active_ad_count", 0) > 0:
        score += 20
    if ext.get("ad_duration_days", 0) > 30:
        score += 15
    if ext.get("service_keywords_detected"):
        score += 15
    if ext.get("cta_type"):
        score += 5
    if has_llm:
        score += 5
    return min(100, score)


def _llm_classify_ads(ad_bodies: List[str]) -> Dict[str, Any]:
    """Optional LLM: service focus, promotional vs brand, urgency, high_ticket_focus. Small prompt, headlines/short bodies only."""
    out = {
        "primary_service_promoted": "",
        "promotional_vs_brand": "unknown",
        "urgency_detected": False,
        "high_ticket_focus": False,
    }
    if not ad_bodies or not os.getenv("OPENAI_API_KEY"):
        return out
    text = "\n".join((b[:200] for b in ad_bodies[:10]))
    if len(text) > 3000:
        text = text[:3000]

    try:
        from openai import OpenAI
        client = OpenAI()
    except ImportError:
        return out

    system = "You are a classifier. Reply with JSON only. Keys: primary_service_promoted (one phrase, e.g. implants or Invisalign), promotional_vs_brand (one of: promotional, brand, mixed), urgency_detected (boolean), high_ticket_focus (boolean). No explanation."
    user = f"Classify these ad creatives (headlines/short body only):\n{text}"

    try:
        r = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0,
            max_tokens=200,
        )
        raw = (r.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw).strip()
            raw = re.sub(r"\n?```$", "", raw).strip()
        data = json.loads(raw)
        out["primary_service_promoted"] = (data.get("primary_service_promoted") or "").strip()[:80]
        pvb = (data.get("promotional_vs_brand") or "").strip().lower()
        if pvb in ("promotional", "brand", "mixed"):
            out["promotional_vs_brand"] = pvb
        out["urgency_detected"] = bool(data.get("urgency_detected"))
        out["high_ticket_focus"] = bool(data.get("high_ticket_focus"))
    except Exception as e:
        logger.debug("Paid intelligence LLM classify failed: %s", e)
    return out


def build_paid_intelligence(
    lead: Dict,
    meta_ads_response: Dict,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """
    Build paid_intelligence from Meta Ads Library response.
    When active_ad_count > 0 and use_llm, call LLM to classify service focus, promotional vs brand, urgency, high_ticket_focus.
    Returns paid_intelligence dict; no raw ad creative in output.
    """
    ad_list = meta_ads_response.get("data") or []
    ext = _extract_deterministic(ad_list)

    all_text = ""
    bodies = []
    for ad in ad_list:
        if isinstance(ad, dict):
            b = (ad.get("ad_creative_body") or "").strip()
            if b:
                bodies.append(b)
                all_text += " " + b
            cap = (ad.get("ad_creative_link_caption") or "").strip()
            if cap:
                all_text += " " + cap

    primary_service = _primary_service_from_keywords(ext.get("service_keywords_detected") or [])
    offer_detected = _offer_detected(all_text)
    high_ticket_focus = _high_ticket_from_keywords(
        ext.get("service_keywords_detected") or [], all_text
    )

    llm_out: Dict[str, Any] = {}
    if use_llm and ext.get("active_ad_count", 0) > 0 and bodies:
        llm_out = _llm_classify_ads(bodies)
        if llm_out.get("primary_service_promoted") and not primary_service:
            primary_service = llm_out["primary_service_promoted"]
        if llm_out.get("high_ticket_focus") is True:
            high_ticket_focus = True

    confidence = _confidence(ext, bool(llm_out and ext.get("active_ad_count", 0) > 0))
    paid_confidence_score = min(100, max(0, confidence))

    # Deterministic output for canonical summary
    paid_channels_detected: List[str] = []
    if ext.get("active_ad_count", 0) > 0:
        paid_channels_detected.append("meta")

    paid_evidence: List[str] = []
    if ext.get("active_ad_count", 0) > 0:
        paid_evidence.append(f"Meta Ads Library: {ext['active_ad_count']} active ad(s)")
        if ext.get("ad_duration_days", 0) > 0:
            paid_evidence.append(f"Ad duration: {ext['ad_duration_days']} days")
        if primary_service:
            paid_evidence.append(f"Promoting: {primary_service}")
        if ext.get("cta_type"):
            paid_evidence.append(f"CTA: {ext['cta_type']}")
        if ext.get("service_keywords_detected"):
            paid_evidence.append("Service keywords: " + ", ".join(ext["service_keywords_detected"][:5]))

    # Indicative spend range when we have Meta ads (no direct spend data)
    paid_spend_range_estimate = "Not detected"
    if ext.get("active_ad_count", 0) > 0:
        paid_spend_range_estimate = "$3k–$10k" if high_ticket_focus else "$1k–$4k"

    return {
        "active_ads": ext["active_ad_count"],
        "ad_duration_days": ext["ad_duration_days"],
        "primary_service_promoted": primary_service or None,
        "offer_detected": offer_detected,
        "high_ticket_focus": high_ticket_focus,
        "cta_type": ext.get("cta_type"),
        "confidence": paid_confidence_score,
        "paid_channels_detected": paid_channels_detected,
        "paid_spend_range_estimate": paid_spend_range_estimate,
        "paid_confidence_score": paid_confidence_score,
        "paid_evidence": paid_evidence,
    }
