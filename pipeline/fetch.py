"""
Google Places API fetching module.

Handles Nearby Search API calls with:
- Pagination (next_page_token)
- Rate limiting and delays
- Exponential backoff on errors
- Request counting and logging
"""

import os
import time
import logging
from typing import List, Dict, Optional, Generator
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Configuration
PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
MAX_PAGES_PER_QUERY = 3  # Google limits to 3 pages (60 results max)
PAGE_TOKEN_DELAY = 2.0   # Required delay before using next_page_token
REQUEST_DELAY = 0.1      # Base delay between requests to respect rate limits
MAX_RETRIES = 3          # Maximum retry attempts on failure
BACKOFF_FACTOR = 2       # Exponential backoff multiplier


class PlacesFetcher:
    """
    Handles Google Places API requests with rate limiting and error handling.
    
    Attributes:
        api_key: Google Places API key
        request_count: Total API requests made
        total_results: Total places fetched
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the fetcher with an API key.
        
        Args:
            api_key: Google Places API key. If None, reads from 
                     GOOGLE_PLACES_API_KEY environment variable.
        
        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        self.api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No API key provided. Set GOOGLE_PLACES_API_KEY environment "
                "variable or pass api_key parameter."
            )
        
        self.request_count = 0
        self.total_results = 0
        self.session = requests.Session()
    
    def _make_request(
        self,
        params: Dict,
        retry_count: int = 0
    ) -> Optional[Dict]:
        """
        Make a single API request with retry logic.
        
        Args:
            params: Request parameters
            retry_count: Current retry attempt number
        
        Returns:
            JSON response dict or None on failure
        """
        try:
            # Add small delay to respect rate limits
            time.sleep(REQUEST_DELAY)
            
            response = self.session.get(
                PLACES_NEARBY_URL,
                params=params,
                timeout=30
            )
            self.request_count += 1
            
            response.raise_for_status()
            data = response.json()
            
            status = data.get("status")
            
            # Handle API-level errors
            if status == "OK" or status == "ZERO_RESULTS":
                return data
            elif status == "OVER_QUERY_LIMIT":
                # Rate limited - back off and retry
                if retry_count < MAX_RETRIES:
                    wait_time = BACKOFF_FACTOR ** retry_count * 5
                    logger.warning(
                        f"Rate limited. Waiting {wait_time}s before retry "
                        f"({retry_count + 1}/{MAX_RETRIES})"
                    )
                    time.sleep(wait_time)
                    return self._make_request(params, retry_count + 1)
                else:
                    logger.error("Max retries exceeded for rate limit")
                    return None
            elif status == "REQUEST_DENIED":
                logger.error(
                    f"Request denied: {data.get('error_message', 'Unknown error')}"
                )
                return None
            elif status == "INVALID_REQUEST":
                logger.error(
                    f"Invalid request: {data.get('error_message', 'Unknown error')}"
                )
                return None
            else:
                logger.warning(f"Unexpected status: {status}")
                return data
                
        except requests.exceptions.Timeout:
            if retry_count < MAX_RETRIES:
                wait_time = BACKOFF_FACTOR ** retry_count
                logger.warning(
                    f"Request timeout. Retrying in {wait_time}s "
                    f"({retry_count + 1}/{MAX_RETRIES})"
                )
                time.sleep(wait_time)
                return self._make_request(params, retry_count + 1)
            else:
                logger.error("Max retries exceeded for timeout")
                return None
                
        except requests.exceptions.RequestException as e:
            if retry_count < MAX_RETRIES:
                wait_time = BACKOFF_FACTOR ** retry_count
                logger.warning(
                    f"Request error: {e}. Retrying in {wait_time}s "
                    f"({retry_count + 1}/{MAX_RETRIES})"
                )
                time.sleep(wait_time)
                return self._make_request(params, retry_count + 1)
            else:
                logger.error(f"Max retries exceeded. Last error: {e}")
                return None
    
    def fetch_nearby_places(
        self,
        lat: float,
        lng: float,
        radius_m: int,
        keyword: str
    ) -> List[Dict]:
        """
        Fetch places for a single location/keyword (first page only).
        
        Args:
            lat: Latitude of search center
            lng: Longitude of search center
            radius_m: Search radius in meters (max 50000)
            keyword: Search keyword (e.g., "HVAC", "plumber")
        
        Returns:
            List of place dictionaries from the API response
        """
        params = {
            "location": f"{lat},{lng}",
            "radius": min(radius_m, 50000),  # API max is 50km
            "keyword": keyword,
            "key": self.api_key
        }
        
        data = self._make_request(params)
        if data and data.get("status") == "OK":
            results = data.get("results", [])
            self.total_results += len(results)
            return results
        return []
    
    def fetch_all_pages_for_query(
        self,
        lat: float,
        lng: float,
        radius_m: int,
        keyword: str,
        max_pages: int = MAX_PAGES_PER_QUERY
    ) -> Generator[Dict, None, None]:
        """
        Fetch all pages of results for a single query.
        
        Handles pagination via next_page_token with required delays.
        
        Args:
            lat: Latitude of search center
            lng: Longitude of search center
            radius_m: Search radius in meters
            keyword: Search keyword
            max_pages: Maximum pages to fetch (1-3, default 3)
        
        Yields:
            Individual place dictionaries
        """
        params = {
            "location": f"{lat},{lng}",
            "radius": min(radius_m, 50000),
            "keyword": keyword,
            "key": self.api_key
        }
        
        pages_fetched = 0
        next_page_token = None
        
        while pages_fetched < max_pages:
            # Add page token for subsequent pages
            if next_page_token:
                # CRITICAL: Must wait before using next_page_token
                # Google requires ~2 seconds for the token to become valid
                time.sleep(PAGE_TOKEN_DELAY)
                params["pagetoken"] = next_page_token
            
            data = self._make_request(params)
            
            if not data:
                break
            
            status = data.get("status")
            if status == "ZERO_RESULTS":
                logger.debug(f"No results for keyword '{keyword}' at ({lat}, {lng})")
                break
            elif status != "OK":
                break
            
            results = data.get("results", [])
            self.total_results += len(results)
            
            for place in results:
                yield place
            
            pages_fetched += 1
            
            # Check for more pages
            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break
            
            # Remove location/radius for paginated requests (use token only)
            if "location" in params:
                del params["location"]
            if "radius" in params:
                del params["radius"]
            if "keyword" in params:
                del params["keyword"]
        
        logger.debug(
            f"Fetched {pages_fetched} page(s) for '{keyword}' at ({lat:.4f}, {lng:.4f})"
        )
    
    def get_stats(self) -> Dict:
        """Return current fetching statistics."""
        return {
            "total_requests": self.request_count,
            "total_results_fetched": self.total_results
        }


# Niche keyword expansion mappings
NICHE_KEYWORDS = {
    "hvac": [
        "HVAC",
        "heating and cooling",
        "air conditioning contractor",
        "furnace repair",
        "AC repair",
        "HVAC contractor"
    ],
    "plumber": [
        "plumber",
        "plumbing contractor",
        "plumbing service",
        "emergency plumber",
        "drain cleaning"
    ],
    "electrician": [
        "electrician",
        "electrical contractor",
        "electrical service",
        "electrical repair"
    ],
    "roofing": [
        "roofing contractor",
        "roof repair",
        "roofing company",
        "roofer"
    ],
    "landscaping": [
        "landscaping",
        "lawn care",
        "landscaper",
        "lawn service",
        "garden maintenance"
    ],
    "cleaning": [
        "cleaning service",
        "house cleaning",
        "janitorial service",
        "commercial cleaning",
        "maid service"
    ]
}


def get_keywords_for_niche(niche: str) -> List[str]:
    """
    Get expanded keyword list for a given niche.
    
    Args:
        niche: Business niche (e.g., "hvac", "plumber")
    
    Returns:
        List of search keywords. Returns [niche] if not found in mappings.
    """
    return NICHE_KEYWORDS.get(niche.lower(), [niche])
