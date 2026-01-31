"""
Signal extraction module for lead enrichment.

Extracts actionable signals from:
- Place Details data (phone, reviews)
- Website analysis (lightweight, no headless browser)

Design Philosophy:
- Observer, not actor (never submit forms, never execute JS)
- Accuracy > perfection (reduce false negatives)
- Cheap, deterministic signals > deep audits
- 1 GET request per website (+ optional HTTP fallback for SSL issues)

Cost Optimization:
- Uses simple HTTP requests, no Lighthouse or Puppeteer
- Single GET request per website extracts all signals
- Timeout aggressively on slow sites (they're likely low quality anyway)
"""

import re
import time
import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests

logger = logging.getLogger(__name__)

# Website analysis configuration
WEBSITE_TIMEOUT = 10  # Aggressive timeout - slow sites = low quality signal
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Automated scheduling system patterns
# These are THIRD-PARTY scheduling tools that indicate operational maturity.
# For HVAC: Phone + contact forms are the PRIMARY booking mechanisms.
# Automated scheduling is an ops maturity signal, NOT a booking requirement.
#
# Interpretation:
#   has_automated_scheduling = true  → Operationally mature, possibly saturated
#   has_automated_scheduling = false → Manual ops, higher optimization opportunity
AUTOMATED_SCHEDULING_PATTERNS = [
    # Field service management (HVAC-specific)
    r'servicetitan\.com',
    r'housecallpro\.com', 
    r'jobber\.com',
    r'fieldedge\.com',
    r'successware\.com',
    
    # General scheduling tools
    r'calendly\.com',
    r'acuityscheduling\.com',
    r'squareup\.com/appointments',
    r'square\.site',
    r'setmore\.com',
    r'schedulicity\.com',
    r'simplybook\.me',
    r'appointy\.com',
    
    # Booking platforms (less common for HVAC)
    r'booksy\.com',
    r'vagaro\.com',
]

# =============================================================================
# CONTACT FORM DETECTION (AGENCY-SAFE)
# =============================================================================
# Philosophy: false negatives destroy agency trust.
# Only emit false when we can PROVE absence (extremely rare).
# Default to null (unknown) when uncertain.
#
# Tri-State Semantics:
#   true  = Confidently observed (human can clearly submit a request)
#   null  = Unknown / cannot be determined
#   false = Explicit evidence of absence ONLY (e.g., "phone only")
# =============================================================================

# Strong HTML evidence - if ANY of these exist, has_contact_form = true
CONTACT_FORM_HTML_PATTERNS = [
    # Form elements
    r'<form\b',                          # Form tag (word boundary)
    r'<input[^>]*type=["\']email["\']',  # Email input field
    r'<input[^>]*type=["\']tel["\']',    # Phone input field
    r'<textarea\b',                      # Text area
    
    # Known form plugins (very high confidence)
    r'wpcf7',                            # WordPress Contact Form 7
    r'wpforms',                          # WPForms
    r'elementor-form',                   # Elementor forms
    r'gravity[-_]?forms?',               # Gravity Forms
    r'ninja[-_]?forms?',                 # Ninja Forms
    r'formidable',                       # Formidable Forms
    r'contact[-_]?form[-_]?7',
    r'formspree',
    r'formstack',
    r'jotform',
    r'typeform',
    r'hubspot.*form',
    r'mailchimp.*form',
    r'netlify-form',
    r'data-form',
    r'quote[-_]?form',
]

# Strong CTA text evidence - BUSINESS CRITICAL
# If a human can clearly see lead-capture intent → true
# These patterns indicate the business WANTS inbound contact
#
# RULE: If a human viewing the page would understand they can submit a request,
#       this MUST be true. This overrides lack of <form> tags.
CONTACT_FORM_TEXT_PATTERNS = [
    # ==========================================================================
    # CALLBACK REQUESTS (extremely strong signal for HVAC)
    # ==========================================================================
    r'request\s+a\s+call\s*back',       # "request a call back"
    r'request\s+a\s+callback',          # "request a callback" (one word)
    r'request\s+call\s*back',           # "request callback"
    r'call\s*back\s+(request|form)',    # "callback request", "callback form"
    r'we\'?ll\s+call\s+you',            # "we'll call you"
    r'have\s+us\s+call',                # "have us call"
    r'call\s+you\s+back',               # "call you back"
    
    # ==========================================================================
    # QUOTE / ESTIMATE REQUESTS (very common for HVAC)
    # ==========================================================================
    r'free\s+quote',                    # "free quote"
    r'get\s+(a\s+)?quote',              # "get a quote", "get quote"
    r'request\s+(a\s+)?quote',          # "request a quote"
    r'for\s+a\s+free\s+quote',          # "for a free quote"
    r'free\s+estimate',                 # "free estimate"
    r'get\s+(a\s+)?free\s+estimate',    # "get a free estimate"
    r'request\s+(an?\s+)?estimate',     # "request an estimate"
    r'instant\s+quote',                 # "instant quote"
    r'online\s+quote',                  # "online quote"
    r'quick\s+quote',                   # "quick quote"
    r'no[- ]?obligation\s+quote',       # "no-obligation quote"
    
    # ==========================================================================
    # FORM SUBMISSION LANGUAGE (explicit form reference)
    # ==========================================================================
    r'fill\s+(out|in)\s+(the|our|this|an?)?\s*(online\s+)?form',  # "fill out our online form"
    r'submit\s+(the\s+|your\s+)?(form|request|inquiry)',          # "submit form"
    r'complete\s+(the|this|our)\s+form',                          # "complete the form"
    r'online\s+form',                   # "online form"
    r'contact\s+form',                  # "contact form"
    r'quote\s+form',                    # "quote form"
    r'request\s+form',                  # "request form"
    
    # ==========================================================================
    # SERVICE SCHEDULING
    # ==========================================================================
    r'schedule\s+(a\s+)?service',           # "schedule a service"
    r'schedule\s+(an?\s+)?appointment',     # "schedule an appointment"
    r'schedule\s+(a\s+)?consultation',      # "schedule a consultation"
    r'schedule\s+(your\s+)?visit',          # "schedule your visit"
    r'book\s+(an?\s+)?appointment',         # "book an appointment"
    r'book\s+(a\s+)?service',               # "book a service"
    r'book\s+online',                       # "book online"
    r'request\s+(a\s+)?service',            # "request a service"
    r'request\s+(a\s+)?consultation',       # "request a consultation"
    r'request\s+an?\s+appointment',         # "request an appointment"
    
    # ==========================================================================
    # CONTACT INTENT LANGUAGE
    # ==========================================================================
    r'contact\s+us',                    # "contact us"
    r'get\s+in\s+touch',                # "get in touch"
    r'send\s+(us\s+)?(a\s+)?message',   # "send us a message"
    r'reach\s+out',                     # "reach out"
    r'let\'?s\s+talk',                  # "let's talk"
    r'drop\s+us\s+a\s+line',            # "drop us a line"
    r'inquiry\s+form',                  # "inquiry form"
    r'message\s+us',                    # "message us"
    r'write\s+to\s+us',                 # "write to us"
    r'email\s+us',                      # "email us"
    
    # ==========================================================================
    # HVAC-SPECIFIC CTAs
    # ==========================================================================
    r'call\s+(us\s+)?(today|now|for)',          # "call us today"
    r'call\s+for\s+(immediate|emergency|same[- ]?day)',  # "call for immediate service"
    r'24[/-]?7\s+(service|emergency|available)', # "24/7 service"
    r'speak\s+(to|with)\s+(a|an)\s+\w+',        # "speak with a technician"
    r'talk\s+to\s+(a|an)\s+\w+',                # "talk to a specialist"
    r'free\s+consultation',                     # "free consultation"
    r'free\s+inspection',                       # "free inspection"
]

# Explicit absence evidence - ONLY set false if these are found
# These are rare and indicate the business explicitly does NOT want online contact
CONTACT_FORM_ABSENCE_PATTERNS = [
    r'phone\s+(inquiries?|calls?)\s+only',
    r'call\s+only',
    r'no\s+online\s+(forms?|requests?|inquiries?)',
    r'no\s+email',
    r'phone\s+only\s*[-–—]\s*no\s+(email|online|web)',
]

# Email extraction patterns
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
MAILTO_PATTERN = r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'

# Trust badge patterns - indicates established business
TRUST_BADGE_PATTERNS = [
    r'bbb\.org',                         # Better Business Bureau
    r'better\s+business\s+bureau',
    r'homeadvisor\.com',
    r'home\s*advisor',
    r'angi\.com',                        # Angi (formerly Angie's List)
    r'angie\'?s?\s*list',
    r'thumbtack\.com',
    r'thumbtack',
    r'yelp\.com/biz',
    r'google\s*reviews?',
    r'facebook\.com/.*reviews',
    r'elite\s+service',
    r'top[- ]?rated',
    r'screened\s+(&|and)\s+approved',
    r'licensed\s+(&|and)\s+insured',
    r'bonded\s+(&|and)\s+insured',
    r'nate[- ]?certified',               # HVAC-specific certification
    r'epa[- ]?certified',
    r'energy\s+star\s+partner',
]


def normalize_domain(url: str) -> str:
    """
    Extract and normalize domain from URL.
    
    Strips protocol, www prefix, and trailing paths.
    
    Args:
        url: Full URL string
    
    Returns:
        Normalized domain (e.g., "example.com")
    """
    if not url:
        return ""
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Remove port if present
        domain = domain.split(':')[0]
        
        return domain.lower()
    except Exception:
        return ""


def normalize_phone(
    formatted_phone: Optional[str],
    international_phone: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """
    Normalize phone number, preferring international format.
    
    Args:
        formatted_phone: Local formatted phone (e.g., "(408) 555-1234")
        international_phone: International format (e.g., "+1 408-555-1234")
    
    Returns:
        Tuple of (has_phone: bool, normalized_phone: str or None)
    """
    # Prefer international format
    phone = international_phone or formatted_phone
    
    if not phone:
        return False, None
    
    # Basic normalization: keep only digits and leading +
    cleaned = phone.strip()
    
    # If it starts with +, keep it
    if cleaned.startswith('+'):
        prefix = '+'
        digits = re.sub(r'[^\d]', '', cleaned[1:])
        normalized = prefix + digits
    else:
        digits = re.sub(r'[^\d]', '', cleaned)
        # Add +1 for US numbers if 10 digits
        if len(digits) == 10:
            normalized = '+1' + digits
        elif len(digits) == 11 and digits.startswith('1'):
            normalized = '+' + digits
        else:
            normalized = digits
    
    return True, normalized


def calculate_days_since_review(reviews: List[Dict]) -> Optional[int]:
    """
    Calculate days since the most recent review.
    
    Args:
        reviews: List of review dicts from Place Details API
    
    Returns:
        Days since last review, or None if no reviews
    """
    if not reviews:
        return None
    
    latest_timestamp = None
    
    for review in reviews:
        # Google provides 'time' as Unix timestamp
        review_time = review.get('time')
        if review_time:
            if latest_timestamp is None or review_time > latest_timestamp:
                latest_timestamp = review_time
    
    if latest_timestamp is None:
        return None
    
    # Calculate days ago
    review_date = datetime.fromtimestamp(latest_timestamp, tz=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    delta = now - review_date
    
    return delta.days


def _fetch_website_html(url: str, headers: Dict) -> Tuple[Optional[str], int, bool, str]:
    """
    Fetch website HTML with SSL fallback.
    
    If HTTPS fails with SSL error, retries once with HTTP.
    This handles small-business sites with misconfigured certs.
    
    Args:
        url: URL to fetch
        headers: Request headers
    
    Returns:
        Tuple of (html_content, load_time_ms, has_ssl, final_url)
        html_content is None if fetch failed
    """
    # Normalize URL - ensure it has a protocol
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Try HTTPS first
    try:
        start_time = time.time()
        response = requests.get(
            url,
            headers=headers,
            timeout=WEBSITE_TIMEOUT,
            allow_redirects=True
        )
        load_time_ms = int((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            final_url = response.url
            has_ssl = final_url.startswith('https')
            return response.text, load_time_ms, has_ssl, final_url
        else:
            logger.debug(f"Website returned {response.status_code}: {url}")
            return None, load_time_ms, url.startswith('https'), url
            
    except requests.exceptions.SSLError:
        # SSL verification failed - try HTTP fallback
        logger.debug(f"SSL error for {url}, trying HTTP fallback")
        
        # Only try HTTP fallback if we were on HTTPS
        if url.startswith('https://'):
            http_url = url.replace('https://', 'http://', 1)
            try:
                start_time = time.time()
                response = requests.get(
                    http_url,
                    headers=headers,
                    timeout=WEBSITE_TIMEOUT,
                    allow_redirects=True
                )
                load_time_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code == 200:
                    final_url = response.url
                    # Site works but SSL is broken
                    has_ssl = final_url.startswith('https')
                    return response.text, load_time_ms, has_ssl, final_url
                    
            except requests.exceptions.RequestException:
                pass
        
        # Both HTTPS and HTTP failed
        return None, 0, False, url
        
    except requests.exceptions.Timeout:
        logger.debug(f"Website timeout: {url}")
        return None, WEBSITE_TIMEOUT * 1000, url.startswith('https'), url
        
    except requests.exceptions.ConnectionError:
        logger.debug(f"Connection error for {url}")
        return None, 0, url.startswith('https'), url
        
    except requests.exceptions.RequestException as e:
        logger.debug(f"Request error for {url}: {e}")
        return None, 0, url.startswith('https'), url


def _extract_emails(html: str) -> List[str]:
    """
    Extract email addresses from HTML content.
    
    Sources:
    - mailto: links
    - Visible email text in HTML
    
    Args:
        html: Raw HTML content
    
    Returns:
        List of unique email addresses found
    """
    emails = set()
    
    # Extract from mailto: links (highest confidence)
    mailto_matches = re.findall(MAILTO_PATTERN, html, re.IGNORECASE)
    emails.update(mailto_matches)
    
    # Extract visible email addresses
    email_matches = re.findall(EMAIL_PATTERN, html)
    for email in email_matches:
        # Filter out common false positives
        email_lower = email.lower()
        if not any(fp in email_lower for fp in [
            'example.com', 'domain.com', 'email.com', 'test.com',
            'yoursite.com', 'website.com', 'company.com',
            '.png', '.jpg', '.gif', '.css', '.js'
        ]):
            emails.add(email)
    
    return list(emails)


def _analyze_html_content(html: str) -> Dict:
    """
    Analyze HTML content for signals using AGENCY-SAFE tri-state semantics.
    
    CRITICAL: False negatives destroy agency trust.
    
    Tri-State Signal Semantics:
    - true  = Confidently observed (human can clearly see it)
    - null  = Unknown / cannot be determined (DEFAULT for uncertainty)
    - false = Explicit evidence of ABSENCE only (extremely rare)
    
    Contact Form Logic (AGENCY-SAFE):
    - true  → Form HTML OR strong CTA text found
    - null  → Cannot determine (no evidence either way)
    - false → ONLY if explicit absence (e.g., "phone only, no forms")
    
    Email Logic:
    - true  → Email found in HTML
    - null  → No email found (but may exist elsewhere)
    - NEVER false (email may exist on other pages, Google listing, etc.)
    
    Args:
        html: HTML content
    
    Returns:
        Dictionary with tri-state signals
    """
    html_lower = html.lower()
    
    # Check if we have substantial HTML content
    has_substantial_html = len(html_lower) > 500 and '<body' in html_lower
    
    # =========================================================================
    # MOBILE-FRIENDLY: Viewport meta tag detection
    # =========================================================================
    has_viewport = bool(
        re.search(r'<meta[^>]*name=["\']viewport["\']', html_lower) or
        re.search(r'<meta[^>]*viewport[^>]*width\s*=\s*device-width', html_lower) or
        re.search(r'<meta[^>]*content=[^>]*width\s*=\s*device-width', html_lower)
    )
    mobile_friendly = has_viewport  # true/false based on tag presence
    
    # =========================================================================
    # CONTACT FORM: Agency-safe detection
    # =========================================================================
    # Check for strong HTML evidence
    has_form_html = any(
        re.search(pattern, html_lower, re.IGNORECASE)
        for pattern in CONTACT_FORM_HTML_PATTERNS
    )
    
    # Check for strong CTA text evidence
    # If a human can clearly see lead-capture intent → true
    has_form_text = any(
        re.search(pattern, html_lower, re.IGNORECASE)
        for pattern in CONTACT_FORM_TEXT_PATTERNS
    )
    
    # Check for explicit absence evidence (very rare)
    has_explicit_absence = any(
        re.search(pattern, html_lower, re.IGNORECASE)
        for pattern in CONTACT_FORM_ABSENCE_PATTERNS
    )
    
    # Determine has_contact_form with AGENCY-SAFE logic
    if has_form_html or has_form_text:
        # Confidently observed - human can clearly submit a request
        has_contact_form = True
    elif has_explicit_absence:
        # Explicit evidence of absence - defensible to reviewer
        has_contact_form = False
    else:
        # Unknown - could be JS-rendered, iframe, multi-page flow
        # DEFAULT TO NULL, NOT FALSE
        has_contact_form = None
    
    # =========================================================================
    # EMAIL: Extract and signal
    # =========================================================================
    emails = _extract_emails(html)
    
    if emails:
        has_email = True
        email_address = emails[0]  # Return first found (usually primary)
    else:
        # No email found, but may exist elsewhere (Google listing, other pages)
        # NEVER set false - email may exist, we just can't see it
        has_email = None
        email_address = None
    
    # =========================================================================
    # AUTOMATED SCHEDULING: Operational maturity signal
    # =========================================================================
    has_scheduling_evidence = any(
        re.search(pattern, html_lower, re.IGNORECASE)
        for pattern in AUTOMATED_SCHEDULING_PATTERNS
    )
    
    if has_scheduling_evidence:
        has_automated_scheduling = True
    elif has_substantial_html:
        # Page analyzed, no scheduling tools found - can set false
        # (This is different from contact form - scheduling tools are explicit)
        has_automated_scheduling = False
    else:
        has_automated_scheduling = None
    
    # =========================================================================
    # TRUST BADGES: Established business indicator
    # =========================================================================
    has_badge_evidence = any(
        re.search(pattern, html_lower, re.IGNORECASE)
        for pattern in TRUST_BADGE_PATTERNS
    )
    
    if has_badge_evidence:
        has_trust_badges = True
    elif has_substantial_html:
        has_trust_badges = False
    else:
        has_trust_badges = None
    
    return {
        "mobile_friendly": mobile_friendly,
        "has_contact_form": has_contact_form,
        "has_email": has_email,
        "email_address": email_address,
        "has_automated_scheduling": has_automated_scheduling,
        "has_trust_badges": has_trust_badges,
        "_has_substantial_html": has_substantial_html,
    }


def analyze_website(url: str) -> Dict:
    """
    Perform lightweight website analysis with tri-state signal semantics.
    
    Tri-State Signal Semantics:
    - true  = Confidently observed (evidence found)
    - false = Confidently absent (page analyzed, no evidence)
    - null  = Unknown / not determinable (page inaccessible, JS-rendered, etc.)
    
    Design:
    - 1 GET request (+ 1 retry on SSL failure via HTTP)
    - No headless browser, no JS execution
    - Unknown ≠ False (epistemically honest)
    - SSL errors don't block analysis - we try HTTP fallback
    
    Args:
        url: Website URL to analyze
    
    Returns:
        Dictionary of website signals with tri-state values
    """
    # Initialize signals with NULL defaults (unknown state)
    # Only set true/false when we have confident evidence
    # AGENCY-SAFE: Never default to false for contact form or email
    signals = {
        "has_website": True,
        "website_url": url,
        "domain": normalize_domain(url),
        "has_ssl": None,               # Unknown until we try to connect
        "mobile_friendly": None,       # Unknown until HTML analyzed
        "has_contact_form": None,      # Unknown until HTML analyzed (NEVER default false)
        "has_email": None,             # Unknown until HTML analyzed (NEVER false)
        "email_address": None,
        "has_automated_scheduling": None,
        "has_trust_badges": None,
        "page_load_time_ms": None,
        "website_accessible": None,
    }
    
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }
    
    # Fetch HTML with SSL fallback
    html, load_time_ms, has_ssl, final_url = _fetch_website_html(url, headers)
    
    # Update connection-based signals (these we can determine from the attempt)
    signals["page_load_time_ms"] = load_time_ms if load_time_ms > 0 else None
    signals["has_ssl"] = has_ssl  # This is determined from the connection
    signals["website_url"] = final_url
    
    if html:
        # Successfully retrieved HTML - we can make confident assessments
        signals["website_accessible"] = True
        
        # Analyze HTML content - returns tri-state values
        content_signals = _analyze_html_content(html)
        signals["mobile_friendly"] = content_signals["mobile_friendly"]
        signals["has_contact_form"] = content_signals["has_contact_form"]
        signals["has_email"] = content_signals["has_email"]
        signals["email_address"] = content_signals["email_address"]
        signals["has_automated_scheduling"] = content_signals["has_automated_scheduling"]
        signals["has_trust_badges"] = content_signals["has_trust_badges"]
    else:
        # Could not retrieve HTML - site is not accessible
        # We KNOW it's not accessible (confident false)
        # But we DON'T KNOW about content signals (null = unknown)
        # AGENCY-SAFE: All content signals remain null
        signals["website_accessible"] = False
    
    return signals


def extract_signals(lead: Dict) -> Dict:
    """
    Extract all signals from an enriched lead.
    
    Combines Place Details data and website analysis into
    a structured LeadSignals object.
    
    Args:
        lead: Lead dict with '_place_details' from enrichment
    
    Returns:
        LeadSignals dictionary
    """
    # Get Place Details enrichment data
    details = lead.get("_place_details", {})
    
    # Extract phone signals
    has_phone, phone_number = normalize_phone(
        details.get("formatted_phone_number"),
        details.get("international_phone_number")
    )
    
    # Extract review signals
    reviews = details.get("reviews", [])
    review_count = lead.get("user_ratings_total", 0) or len(reviews)
    rating = lead.get("rating")
    last_review_days_ago = calculate_days_since_review(reviews)
    
    # Extract website signals
    website_url = details.get("website")
    
    if website_url:
        website_signals = analyze_website(website_url)
    else:
        # No website listed in Place Details
        # has_website = False (we KNOW they don't have one listed)
        # Other signals = null (unknown - we can't analyze what doesn't exist)
        # 
        # AGENCY-SAFE Tri-state semantics:
        # - has_website: false (confidently absent from Google listing)
        # - Other signals: null (unknown, not determinable, NEVER false)
        website_signals = {
            "has_website": False,        # Confidently absent from listing
            "website_url": None,
            "domain": None,
            "has_ssl": None,             # Unknown
            "mobile_friendly": None,     # Unknown
            "has_contact_form": None,    # Unknown (NEVER false)
            "has_email": None,           # Unknown (NEVER false)
            "email_address": None,
            "has_automated_scheduling": None,
            "has_trust_badges": None,
            "page_load_time_ms": None,
            "website_accessible": None,
        }
    
    # Build final signals object with AGENCY-SAFE TRI-STATE SEMANTICS
    # 
    # Tri-State Values:
    #   true  = Confidently observed (evidence found)
    #   null  = Unknown / not determinable (DEFAULT for uncertainty)
    #   false = Confidently absent (RARE - only when defensible)
    #
    # AGENCY-SAFE Rules:
    # - has_contact_form: NEVER default to false (destroys trust)
    #   * true  = Form HTML or strong CTA text found
    #   * null  = Unknown (JS-rendered, iframe, etc.)
    #   * false = ONLY explicit absence ("phone only", etc.)
    # - has_email: NEVER false (email may exist elsewhere)
    #   * true  = Email found in HTML
    #   * null  = Not found (but may exist on Google listing, etc.)
    # - has_automated_scheduling: Can be false (scheduling tools are explicit)
    #   * true  = Scheduling platform detected
    #   * false = Page analyzed, none found (manual ops = opportunity)
    #   * null  = Page not analyzable
    #
    signals = {
        "place_id": lead.get("place_id"),
        
        # Phone signals - PRIMARY booking mechanism for HVAC
        "has_phone": has_phone,
        "phone_number": phone_number,
        
        # Website signals
        "has_website": website_signals["has_website"],
        "website_url": website_signals["website_url"],
        "domain": website_signals["domain"],
        "has_ssl": website_signals["has_ssl"],
        "mobile_friendly": website_signals["mobile_friendly"],
        
        # Inbound readiness - AGENCY-SAFE (never default false)
        "has_contact_form": website_signals["has_contact_form"],
        
        # Email reachability - NEVER false
        "has_email": website_signals["has_email"],
        "email_address": website_signals["email_address"],
        
        # Operational maturity - can be false (explicit signal)
        "has_automated_scheduling": website_signals["has_automated_scheduling"],
        
        # Trust/reputation signals
        "has_trust_badges": website_signals["has_trust_badges"],
        
        "page_load_time_ms": website_signals["page_load_time_ms"],
        "website_accessible": website_signals["website_accessible"],
        
        # Review signals - business activity indicator
        "rating": rating,
        "review_count": review_count,
        "last_review_days_ago": last_review_days_ago,
    }
    
    return signals


def extract_signals_batch(
    leads: List[Dict],
    progress_interval: int = 10
) -> List[Dict]:
    """
    Extract signals from multiple leads.
    
    Args:
        leads: List of enriched lead dictionaries
        progress_interval: Log progress every N leads
    
    Returns:
        List of LeadSignals dictionaries
    """
    signals_list = []
    total = len(leads)
    websites_analyzed = 0
    
    for i, lead in enumerate(leads, 1):
        signals = extract_signals(lead)
        signals_list.append(signals)
        
        if signals["has_website"]:
            websites_analyzed += 1
        
        if i % progress_interval == 0:
            logger.info(
                f"Extracted signals for {i}/{total} leads "
                f"({websites_analyzed} websites analyzed)"
            )
    
    logger.info(
        f"Signal extraction complete: {total} leads, "
        f"{websites_analyzed} websites analyzed"
    )
    
    return signals_list


def merge_signals_into_lead(lead: Dict, signals: Dict) -> Dict:
    """
    Merge extracted signals back into the lead record.
    
    Creates a flat structure suitable for database storage.
    
    Args:
        lead: Original lead dictionary
        signals: Extracted signals dictionary
    
    Returns:
        Lead dictionary with signals merged in
    """
    merged = lead.copy()
    
    # Remove internal enrichment data
    if "_place_details" in merged:
        del merged["_place_details"]
    
    # Add signal fields with 'signal_' prefix to avoid conflicts
    for key, value in signals.items():
        if key != "place_id":  # Don't duplicate place_id
            merged[f"signal_{key}"] = value
    
    return merged
