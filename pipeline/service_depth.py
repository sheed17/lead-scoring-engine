"""
Service depth detection for dental leads.

Crawls homepage + main nav, detects high-ticket vs general service pages,
flags missing high-value pages. Used for revenue leverage and intervention quality.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# High-ticket: dedicated pages drive revenue asymmetry
HIGH_TICKET_KEYWORDS = [
    "dental implant",
    "implant",
    "invisalign",
    "veneer",
    "veneers",
    "cosmetic dentistry",
    "cosmetic",
    "sedation dentistry",
    "sedation",
    "emergency dentist",
    "emergency dental",
    "same day crown",
    "same-day crown",
    "sleep apnea",
    "orthodontic",
    "orthodontics",
    "braces",
]
# URL path slugs that indicate dedicated page
HIGH_TICKET_SLUGS = [
    "implant", "implants", "invisalign", "veneer", "veneers",
    "cosmetic", "sedation", "emergency", "same-day-crown", "crown",
    "sleep-apnea", "orthodontic", "orthodontics", "braces",
]
# General services (for general_services_detected)
GENERAL_KEYWORDS = [
    "cleaning", "family dentist", "checkup", "filling", "fillings",
    "general dentistry", "preventive", "exam", "x-ray", "hygiene",
]


def _fetch_html(url: str) -> Optional[str]:
    try:
        import requests
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        r = requests.get(url, timeout=12, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; LeadScoring/1.0)"})
        if r.status_code == 200:
            return r.text
    except Exception as e:
        logger.debug("Service depth fetch failed %s: %s", url[:50], e)
    return None


def _normalize_url(base: str, href: str) -> Optional[str]:
    try:
        full = urljoin(base, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            return None
        return full
    except Exception:
        return None


def _same_domain(base: str, url: str) -> bool:
    try:
        return urlparse(base).netloc.lower() == urlparse(url).netloc.lower()
    except Exception:
        return False


def _extract_links(html: str, base_url: str) -> List[str]:
    """Extract same-domain links from HTML."""
    if not html:
        return []
    links = set()
    # href="..."
    for m in re.finditer(r'href\s*=\s*["\']([^"\']+)["\']', html, re.I):
        full = _normalize_url(base_url, m.group(1).strip())
        if full and _same_domain(base_url, full):
            links.add(full)
    return list(links)[:30]


def _path_slugs(url: str) -> Set[str]:
    path = urlparse(url).path.lower()
    return set(re.findall(r"[a-z0-9]+", path))


def _is_service_like_path(url: str) -> bool:
    slugs = _path_slugs(url)
    for s in HIGH_TICKET_SLUGS + ["service", "services", "treatment", "treatments"]:
        if s in slugs:
            return True
    return False


def _is_pricing_like_path(url: str) -> bool:
    slugs = _path_slugs(url)
    for s in ["pricing", "price", "cost", "fees", "insurance", "payment"]:
        if s in slugs:
            return True
    return False


def get_page_texts_for_llm(
    website_url: Optional[str],
    website_html: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    Return homepage_text, services_page_text, pricing_page_text for LLM structured extraction.
    Keys: "homepage_text", "services_page_text", "pricing_page_text".
    """
    out = {"homepage_text": None, "services_page_text": None, "pricing_page_text": None}
    if not (website_url or "").strip():
        return out
    base_url = website_url if website_url.startswith(("http://", "https://")) else "https://" + website_url
    html = website_html or _fetch_html(base_url)
    if not html:
        return out
    out["homepage_text"] = _strip_html(html)
    links = _extract_links(html, base_url)
    service_like = [u for u in links if _is_service_like_path(u)]
    pricing_like = [u for u in links if _is_pricing_like_path(u)]
    for url in service_like[:1]:
        if url == base_url:
            continue
        h = _fetch_html(url)
        if h:
            out["services_page_text"] = _strip_html(h)
            break
    for url in pricing_like[:1]:
        if url == base_url:
            continue
        h = _fetch_html(url)
        if h:
            out["pricing_page_text"] = _strip_html(h)
            break
    return out


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def _title_h1(html: str) -> str:
    if not html:
        return ""
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    title = (m.group(1) if m else "").strip()
    m2 = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
    h1 = (m2.group(1) if m2 else "").strip()
    return (title + " " + h1).lower()


def _detect_procedure_in_text(text: str, keywords: List[str]) -> Set[str]:
    found = set()
    for kw in keywords:
        if kw in text:
            found.add(kw)
    return found


def _dedicated_for_procedure(url: str, path_slugs: Set[str], page_text: str, title_h1: str) -> Set[str]:
    """Which high-ticket procedures this page is dedicated to (strong signal)."""
    dedicated = set()
    for kw in HIGH_TICKET_KEYWORDS:
        slug = kw.replace(" ", "-").replace(" ", "")
        if slug in path_slugs or kw.replace(" ", "") in path_slugs:
            dedicated.add(kw)
        if kw in title_h1 and len(title_h1) < 200:
            dedicated.add(kw)
    return dedicated


def _mentioned_in_page(page_text: str) -> Set[str]:
    """High-ticket keywords mentioned in page body (weak signal if not dedicated)."""
    return _detect_procedure_in_text(page_text, HIGH_TICKET_KEYWORDS)


def build_service_intelligence(
    website_url: Optional[str],
    website_html: Optional[str] = None,
    procedure_mentions_from_reviews: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Build service_intelligence block: high_ticket_procedures_detected,
    general_services_detected, missing_high_value_pages, procedure_confidence.

    If website_url is None or empty, returns empty lists and 0 confidence.
    """
    out = {
        "high_ticket_procedures_detected": [],
        "general_services_detected": [],
        "missing_high_value_pages": [],
        "procedure_confidence": 0.0,
    }
    if not (website_url or "").strip():
        return out

    base_url = website_url if website_url.startswith(("http://", "https://")) else "https://" + website_url
    html = website_html or _fetch_html(base_url)
    if not html:
        return out

    pages: List[Tuple[str, str, str, Set[str]]] = []  # url, text, title_h1, path_slugs
    text = _strip_html(html)
    title_h1 = _title_h1(html)
    path_slugs = _path_slugs(base_url)
    pages.append((base_url, text, title_h1, path_slugs))

    # Nav/service links: fetch up to 5
    links = _extract_links(html, base_url)
    service_like = [u for u in links if _is_service_like_path(u)][:5]
    for url in service_like:
        if url == base_url:
            continue
        h = _fetch_html(url)
        if h:
            pages.append((url, _strip_html(h), _title_h1(h), _path_slugs(url)))

    all_dedicated: Set[str] = set()
    all_mentioned: Set[str] = set()
    all_general: Set[str] = set()

    for url, page_text, th1, path_slugs in pages:
        dedicated = _dedicated_for_procedure(url, path_slugs, page_text, th1)
        mentioned = _mentioned_in_page(page_text)
        general = _detect_procedure_in_text(page_text, GENERAL_KEYWORDS)
        all_dedicated |= dedicated
        all_mentioned |= mentioned
        all_general |= general

    high_ticket_detected = sorted(all_dedicated | all_mentioned)
    general_detected = sorted(all_general)
    out["high_ticket_procedures_detected"] = high_ticket_detected[:15]
    out["general_services_detected"] = general_detected[:10]

    # Missing: high-ticket mentioned (on site or in reviews) but no dedicated page
    from_reviews = set(procedure_mentions_from_reviews or [])
    high_value_mentioned = all_mentioned | from_reviews
    for kw in high_value_mentioned:
        if kw in all_dedicated:
            continue
        # Normalize to a page name
        label = kw.replace(" ", "_")
        if label not in [m.replace(" ", "_") for m in out["missing_high_value_pages"]]:
            out["missing_high_value_pages"].append(kw)
    out["missing_high_value_pages"] = out["missing_high_value_pages"][:10]

    n_pages = len(pages)
    n_high = len(out["high_ticket_procedures_detected"])
    out["procedure_confidence"] = round(min(1.0, 0.3 + 0.15 * n_pages + 0.1 * n_high), 2)
    return out
