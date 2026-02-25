"""
Service depth detection for dental leads.

Crawls homepage, sitemap, nav links (two levels deep), detects high-ticket
vs general service pages, flags truly missing high-value pages.
Used for revenue leverage and intervention quality.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical service buckets — single source of truth for aliasing
# ---------------------------------------------------------------------------
CANONICAL_BUCKETS: Dict[str, List[str]] = {
    "implants": ["implant", "implants", "dental implant", "dental implants", "all-on-4", "all on 4"],
    "orthodontics": ["orthodontic", "orthodontics", "invisalign", "braces", "clear aligner", "clear aligners"],
    "veneers": ["veneer", "veneers", "porcelain veneer", "porcelain veneers"],
    "cosmetic": ["cosmetic", "cosmetic dentistry", "smile makeover", "teeth whitening", "whitening"],
    "sedation": ["sedation", "sedation dentistry", "iv sedation", "nitrous", "nitrous oxide", "oral sedation", "sleep dentistry"],
    "emergency": ["emergency", "emergency dentist", "emergency dental", "same day", "same-day", "urgent dental"],
    "crowns": ["crown", "crowns", "same day crown", "same-day crown", "dental crown", "dental crowns"],
    "sleep_apnea": ["sleep apnea", "sleep-apnea", "snoring"],
}

CANONICAL_DISPLAY: Dict[str, str] = {
    "implants": "Implants",
    "orthodontics": "Orthodontics",
    "veneers": "Veneers",
    "cosmetic": "Cosmetic",
    "sedation": "Sedation",
    "emergency": "Emergency",
    "crowns": "Crowns",
    "sleep_apnea": "Sleep Apnea",
}

# Flat lookup: keyword → canonical bucket
_KW_TO_BUCKET: Dict[str, str] = {}
_ALL_KEYWORDS: List[str] = []
for _bucket, _aliases in CANONICAL_BUCKETS.items():
    for _alias in _aliases:
        _KW_TO_BUCKET[_alias.lower()] = _bucket
        if _alias.lower() not in _ALL_KEYWORDS:
            _ALL_KEYWORDS.append(_alias.lower())
_ALL_KEYWORDS.sort(key=len, reverse=True)

# URL slug fragments that indicate a service page
SERVICE_PATH_TOKENS = {
    "implant", "implants", "invisalign", "veneer", "veneers",
    "cosmetic", "sedation", "emergency", "crown", "crowns",
    "sleep", "apnea", "orthodontic", "orthodontics", "braces",
    "service", "services", "treatment", "treatments", "procedure",
    "procedures", "whitening", "makeover", "dental", "dentistry",
    "restorative", "preventive", "periodontal", "endodontic",
}

GENERAL_KEYWORDS = [
    "cleaning", "family dentist", "checkup", "filling", "fillings",
    "general dentistry", "preventive", "exam", "x-ray", "hygiene",
    "periodontal", "root canal",
]

# Minimum keyword mentions in body text to count as content-dedicated
CONTENT_DEDICATION_THRESHOLD = 3
# Minimum page text length (chars) to be considered substantial
SUBSTANTIAL_PAGE_LENGTH = 300


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_html(url: str) -> Optional[str]:
    try:
        import requests
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        r = requests.get(
            url, timeout=12, allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        )
        if r.status_code == 200:
            return r.text
    except Exception as e:
        logger.debug("Fetch failed %s: %s", url[:60], e)
    return None


def _normalize_url(base: str, href: str) -> Optional[str]:
    try:
        full = urljoin(base, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            return None
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if clean.endswith("/"):
            clean = clean[:-1]
        return clean
    except Exception:
        return None


def _same_domain(base: str, url: str) -> bool:
    try:
        b = urlparse(base).netloc.lower().replace("www.", "")
        u = urlparse(url).netloc.lower().replace("www.", "")
        return b == u
    except Exception:
        return False


def _extract_links(html: str, base_url: str) -> List[str]:
    """Extract unique same-domain links from HTML."""
    if not html:
        return []
    seen = set()
    out = []
    for m in re.finditer(r'href\s*=\s*["\']([^"\'#]+)["\']', html, re.I):
        full = _normalize_url(base_url, m.group(1).strip())
        if full and _same_domain(base_url, full) and full not in seen:
            seen.add(full)
            out.append(full)
    return out[:120]


def _path_slugs(url: str) -> Set[str]:
    path = urlparse(url).path.lower()
    return set(re.findall(r"[a-z0-9]+", path))


def _stem(word: str) -> str:
    w = word.lower()
    if w.endswith("ics"):
        return w[:-1]
    if w.endswith("es") and len(w) > 3:
        return w[:-2]
    if w.endswith("s") and len(w) > 3:
        return w[:-1]
    return w


def _stems(words: Set[str]) -> Set[str]:
    return {_stem(w) for w in words}


def _is_service_like_path(url: str) -> bool:
    slugs = _path_slugs(url)
    stemmed = _stems(slugs)
    for token in SERVICE_PATH_TOKENS:
        if token in slugs or _stem(token) in stemmed:
            return True
    return False


def _is_pricing_like_path(url: str) -> bool:
    slugs = _path_slugs(url)
    for s in ("pricing", "price", "cost", "fees", "insurance", "payment"):
        if s in slugs:
            return True
    return False


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()


def _extract_headings(html: str) -> str:
    """Extract all h1/h2/h3 text, stripping nested tags."""
    if not html:
        return ""
    parts = []
    for m in re.finditer(r"<h[123][^>]*>(.*?)</h[123]>", html, re.I | re.S):
        inner = re.sub(r"<[^>]+>", " ", m.group(1))
        inner = re.sub(r"\s+", " ", inner).strip()
        if inner:
            parts.append(inner)
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if title_m:
        t = re.sub(r"<[^>]+>", " ", title_m.group(1)).strip()
        if t:
            parts.insert(0, t)
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# Sitemap parsing
# ---------------------------------------------------------------------------

def _fetch_sitemap_urls(base_url: str) -> List[str]:
    """Fetch sitemap.xml and extract same-domain URLs."""
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    urls: List[str] = []

    for sitemap_path in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
        xml = _fetch_html(root + sitemap_path)
        if not xml:
            continue
        for m in re.finditer(r"<loc>\s*(https?://[^<]+?)\s*</loc>", xml, re.I):
            url = m.group(1).strip()
            if _same_domain(base_url, url):
                normalized = _normalize_url(base_url, url)
                if normalized and normalized not in urls:
                    urls.append(normalized)
        if urls:
            break

    return urls[:200]


# ---------------------------------------------------------------------------
# Canonical bucket resolution
# ---------------------------------------------------------------------------

def _to_canonical(keyword: str) -> Optional[str]:
    """Map a raw keyword to its canonical bucket name."""
    return _KW_TO_BUCKET.get(keyword.lower().strip())


def _detect_buckets_in_text(text: str) -> Set[str]:
    """Return set of canonical bucket names mentioned in text."""
    buckets = set()
    for kw in _ALL_KEYWORDS:
        if kw in text:
            b = _to_canonical(kw)
            if b:
                buckets.add(b)
    return buckets


def _count_bucket_mentions(text: str, bucket: str) -> int:
    """Count how many times any alias of a bucket appears in text."""
    count = 0
    for alias in CANONICAL_BUCKETS.get(bucket, []):
        count += len(re.findall(re.escape(alias), text))
    return count


# ---------------------------------------------------------------------------
# Page-level detection
# ---------------------------------------------------------------------------

def _dedicated_buckets_for_page(
    url: str, path_slugs: Set[str], headings: str, page_text: str,
) -> Set[str]:
    """
    Determine which canonical buckets this page is DEDICATED to.
    Three signals (any one is sufficient):
      1. URL path slugs match bucket aliases
      2. Headings (h1/h2/h3/title) contain bucket keywords
      3. Body text mentions a bucket's keywords >= CONTENT_DEDICATION_THRESHOLD times
         AND the page has substantial content (not just a nav listing)
    """
    dedicated: Set[str] = set()
    stemmed_slugs = _stems(path_slugs)

    for bucket, aliases in CANONICAL_BUCKETS.items():
        # Signal 1: URL slug match
        for alias in aliases:
            alias_parts = alias.replace("-", " ").split()
            alias_stems = {_stem(p) for p in alias_parts}
            if alias_stems and alias_stems.issubset(stemmed_slugs):
                dedicated.add(bucket)
                break

        if bucket in dedicated:
            continue

        # Signal 2: Heading match
        for alias in aliases:
            if alias in headings:
                dedicated.add(bucket)
                break

        if bucket in dedicated:
            continue

        # Signal 3: Content-frequency dedication
        if len(page_text) >= SUBSTANTIAL_PAGE_LENGTH:
            mentions = _count_bucket_mentions(page_text, bucket)
            if mentions >= CONTENT_DEDICATION_THRESHOLD:
                dedicated.add(bucket)

    return dedicated


def _mentioned_buckets_in_page(page_text: str) -> Set[str]:
    """Return canonical buckets mentioned at least once in page body."""
    return _detect_buckets_in_text(page_text)


# ---------------------------------------------------------------------------
# Main intelligence builder
# ---------------------------------------------------------------------------

def build_service_intelligence(
    website_url: Optional[str],
    website_html: Optional[str] = None,
    procedure_mentions_from_reviews: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Build service_intelligence block with canonical bucket resolution.

    Crawls homepage → sitemap → nav links (two levels) to build a comprehensive
    page inventory. Detects which high-ticket services have dedicated pages vs.
    are merely mentioned, and flags truly missing opportunities.
    """
    out: Dict[str, Any] = {
        "high_ticket_procedures_detected": [],
        "general_services_detected": [],
        "missing_high_value_pages": [],
        "procedure_confidence": 0.0,
        "pages_crawled": 0,
    }
    if not (website_url or "").strip():
        return out

    base_url = website_url if website_url.startswith(("http://", "https://")) else "https://" + website_url
    html = website_html or _fetch_html(base_url)
    if not html:
        return out

    # -- Phase 1: Collect all known URLs --------------------------------
    all_urls: Set[str] = set()
    homepage_links = _extract_links(html, base_url)
    all_urls.update(homepage_links)

    sitemap_urls = _fetch_sitemap_urls(base_url)
    all_urls.update(sitemap_urls)
    logger.debug("Sitemap yielded %d URLs", len(sitemap_urls))

    # -- Phase 2: Identify service-like URLs to crawl -------------------
    service_urls = [u for u in all_urls if _is_service_like_path(u) and u != base_url]
    service_urls_deduped: List[str] = []
    seen_paths: Set[str] = set()
    for u in service_urls:
        p = urlparse(u).path.lower().rstrip("/")
        if p not in seen_paths:
            seen_paths.add(p)
            service_urls_deduped.append(u)

    # -- Phase 3: Crawl pages (homepage + up to 20 service pages) -------
    PageInfo = Tuple[str, str, str, Set[str]]  # url, text, headings, path_slugs
    pages: List[PageInfo] = []

    homepage_text = _strip_html(html)
    homepage_headings = _extract_headings(html)
    pages.append((base_url, homepage_text, homepage_headings, _path_slugs(base_url)))

    level1_fetched: Set[str] = {base_url}
    level2_candidates: List[str] = []

    for url in service_urls_deduped[:20]:
        if url in level1_fetched:
            continue
        h = _fetch_html(url)
        if not h:
            continue
        level1_fetched.add(url)
        page_text = _strip_html(h)
        headings = _extract_headings(h)
        pages.append((url, page_text, headings, _path_slugs(url)))

        # Two-level crawl: extract links from this sub-page
        sub_links = _extract_links(h, url)
        for sl in sub_links:
            if sl not in level1_fetched and _is_service_like_path(sl):
                level2_candidates.append(sl)

    # Crawl level-2 pages (deeper service pages linked from index pages)
    level2_seen: Set[str] = set()
    for url in level2_candidates:
        if len(pages) >= 35:
            break
        p = urlparse(url).path.lower().rstrip("/")
        if p in seen_paths or url in level2_seen:
            continue
        level2_seen.add(url)
        seen_paths.add(p)
        h = _fetch_html(url)
        if not h:
            continue
        pages.append((url, _strip_html(h), _extract_headings(h), _path_slugs(url)))

    out["pages_crawled"] = len(pages)

    # -- Phase 4: Detect services per page (canonical buckets) ----------
    all_dedicated_buckets: Set[str] = set()
    all_mentioned_buckets: Set[str] = set()
    all_general: Set[str] = set()

    for url, page_text, headings, pslugs in pages:
        dedicated = _dedicated_buckets_for_page(url, pslugs, headings, page_text)
        mentioned = _mentioned_buckets_in_page(page_text)
        general = set()
        for gkw in GENERAL_KEYWORDS:
            if gkw in page_text:
                general.add(gkw)

        all_dedicated_buckets |= dedicated
        all_mentioned_buckets |= mentioned
        all_general |= general

    # -- Phase 5: Also check sitemap URLs by slug (no fetch needed) -----
    # If a sitemap URL clearly matches a bucket via path, count it as dedicated
    for url in sitemap_urls:
        pslugs = _path_slugs(url)
        for bucket, aliases in CANONICAL_BUCKETS.items():
            if bucket in all_dedicated_buckets:
                continue
            stemmed = _stems(pslugs)
            for alias in aliases:
                parts = alias.replace("-", " ").split()
                if {_stem(p) for p in parts}.issubset(stemmed):
                    all_dedicated_buckets.add(bucket)
                    break

    # -- Phase 6: Build output using canonical display names ------------
    all_detected = all_dedicated_buckets | all_mentioned_buckets
    out["high_ticket_procedures_detected"] = sorted(
        [CANONICAL_DISPLAY[b] for b in all_detected if b in CANONICAL_DISPLAY]
    )
    out["general_services_detected"] = sorted(list(all_general))[:10]

    # Missing = mentioned (on site or in reviews) but NO dedicated page
    review_buckets: Set[str] = set()
    for mention in (procedure_mentions_from_reviews or []):
        b = _to_canonical(mention)
        if b:
            review_buckets.add(b)

    all_mentioned_or_review = all_mentioned_buckets | review_buckets
    missing_buckets = all_mentioned_or_review - all_dedicated_buckets
    out["missing_high_value_pages"] = sorted(
        [CANONICAL_DISPLAY[b] for b in missing_buckets if b in CANONICAL_DISPLAY]
    )

    n_pages = len(pages)
    n_high = len(out["high_ticket_procedures_detected"])
    out["procedure_confidence"] = round(min(1.0, 0.3 + 0.1 * n_pages + 0.1 * n_high), 2)
    return out


# ---------------------------------------------------------------------------
# LLM page text helper (unchanged interface)
# ---------------------------------------------------------------------------

def get_page_texts_for_llm(
    website_url: Optional[str],
    website_html: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    Return homepage_text, services_page_text, pricing_page_text for LLM structured extraction.
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
