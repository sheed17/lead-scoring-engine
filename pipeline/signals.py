"""
Signal extraction module for lead enrichment.

Extracts actionable signals from:
- Place Details data (phone, reviews)
- Website analysis (lightweight, no headless browser)

Cost Optimization:
- Uses simple HTTP requests, no Lighthouse or Puppeteer
- Single GET request per website extracts all signals
- HEAD request first to check availability (saves bandwidth)
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
    "Mozilla/5.0 (compatible; LeadBot/1.0; +https://example.com/bot)"
)

# Booking widget patterns (URLs/scripts commonly embedded)
BOOKING_PATTERNS = [
    r'calendly\.com',
    r'setmore\.com',
    r'square\.site',
    r'squareup\.com/appointments',
    r'acuityscheduling\.com',
    r'booksy\.com',
    r'vagaro\.com',
    r'schedulicity\.com',
    r'simplybook\.me',
    r'appointy\.com',
    r'booking\.com/hotel',
    r'opentable\.com',
    r'yelp\.com/biz/.*/reservations',
    r'housecallpro\.com',
    r'jobber\.com',
    r'servicetitan\.com',
]

# Contact form indicators
CONTACT_FORM_PATTERNS = [
    r'<form[^>]*>',  # Any form tag
    r'contact[-_]?form',
    r'contact[-_]?us',
    r'get[-_]?(a[-_]?)?quote',
    r'request[-_]?(a[-_]?)?quote',
    r'free[-_]?estimate',
    r'schedule[-_]?(a[-_]?)?service',
    r'book[-_]?(an[-_]?)?appointment',
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


def analyze_website(url: str) -> Dict:
    """
    Perform lightweight website analysis.
    
    Extracts signals with a single HTTP request:
    - SSL status
    - Mobile-friendly heuristic (viewport meta tag)
    - Contact form detection
    - Booking widget detection
    - Page load time
    
    Args:
        url: Website URL to analyze
    
    Returns:
        Dictionary of website signals
    """
    signals = {
        "has_website": True,
        "website_url": url,
        "domain": normalize_domain(url),
        "has_ssl": url.startswith('https'),
        "mobile_friendly": None,
        "has_contact_form": None,
        "has_booking": None,
        "page_load_time_ms": None,
        "website_accessible": False,
    }
    
    # Ensure URL has protocol
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        signals["website_url"] = url
        signals["has_ssl"] = True
    
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        # Time the request
        start_time = time.time()
        
        response = requests.get(
            url,
            headers=headers,
            timeout=WEBSITE_TIMEOUT,
            allow_redirects=True
        )
        
        load_time_ms = int((time.time() - start_time) * 1000)
        signals["page_load_time_ms"] = load_time_ms
        
        # Check if we got a successful response
        if response.status_code == 200:
            signals["website_accessible"] = True
            
            # Get the final URL after redirects
            final_url = response.url
            signals["has_ssl"] = final_url.startswith('https')
            
            # Analyze HTML content
            html = response.text.lower()
            
            # Mobile-friendly: check for viewport meta tag
            signals["mobile_friendly"] = bool(
                re.search(r'<meta[^>]*name=["\']viewport["\']', html) or
                re.search(r'<meta[^>]*viewport[^>]*width=device-width', html)
            )
            
            # Contact form detection
            signals["has_contact_form"] = any(
                re.search(pattern, html, re.IGNORECASE)
                for pattern in CONTACT_FORM_PATTERNS
            )
            
            # Booking widget detection
            signals["has_booking"] = any(
                re.search(pattern, html, re.IGNORECASE)
                for pattern in BOOKING_PATTERNS
            )
        else:
            logger.debug(f"Website returned {response.status_code}: {url}")
            
    except requests.exceptions.SSLError:
        # SSL error - site might work on HTTP
        signals["has_ssl"] = False
        logger.debug(f"SSL error for {url}")
        
    except requests.exceptions.Timeout:
        logger.debug(f"Website timeout: {url}")
        signals["page_load_time_ms"] = WEBSITE_TIMEOUT * 1000  # Mark as slow
        
    except requests.exceptions.ConnectionError:
        logger.debug(f"Connection error for {url}")
        
    except requests.exceptions.RequestException as e:
        logger.debug(f"Request error for {url}: {e}")
    
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
        # No website - set all website signals to null/false
        website_signals = {
            "has_website": False,
            "website_url": None,
            "domain": None,
            "has_ssl": None,
            "mobile_friendly": None,
            "has_contact_form": None,
            "has_booking": None,
            "page_load_time_ms": None,
            "website_accessible": None,
        }
    
    # Build final signals object
    signals = {
        "place_id": lead.get("place_id"),
        
        # Website signals
        "has_website": website_signals["has_website"],
        "website_url": website_signals["website_url"],
        "domain": website_signals["domain"],
        "has_ssl": website_signals["has_ssl"],
        "mobile_friendly": website_signals["mobile_friendly"],
        "has_contact_form": website_signals["has_contact_form"],
        "has_booking": website_signals["has_booking"],
        "page_load_time_ms": website_signals["page_load_time_ms"],
        "website_accessible": website_signals["website_accessible"],
        
        # Phone signals
        "has_phone": has_phone,
        "phone_number": phone_number,
        
        # Review signals
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
