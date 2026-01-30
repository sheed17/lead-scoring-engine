#!/usr/bin/env python3
"""
Quick test script to validate Google Places API connection.

Usage:
    export GOOGLE_PLACES_API_KEY="your-api-key"
    python test_places.py
"""

import os
import sys

# Test basic API connectivity
from pipeline.fetch import PlacesFetcher
from pipeline.normalize import normalize_place


def main():
    """Test Google Places API connection with a single query."""
    print("Testing Google Places API connection...\n")
    
    # Check API key
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_PLACES_API_KEY environment variable not set")
        print("Run: export GOOGLE_PLACES_API_KEY='your-api-key'")
        sys.exit(1)
    
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        # Initialize fetcher
        fetcher = PlacesFetcher()
        
        # Test with San Jose HVAC search
        print("\nSearching for 'HVAC' near San Jose, CA...")
        places = fetcher.fetch_nearby_places(
            lat=37.3382,
            lng=-121.8863,
            radius_m=5000,
            keyword="HVAC"
        )
        
        stats = fetcher.get_stats()
        print(f"API calls made: {stats['total_requests']}")
        print(f"Results found: {len(places)}")
        
        if places:
            print("\nFirst 3 results:")
            for i, place in enumerate(places[:3], 1):
                normalized = normalize_place(place)
                print(f"  {i}. {normalized['name']}")
                print(f"     Address: {normalized['address']}")
                print(f"     Rating: {normalized['rating']} ({normalized['user_ratings_total']} reviews)")
                print()
            print("SUCCESS: API connection working!")
        else:
            print("\nNo results found. This could mean:")
            print("  - API key is valid but Places API not enabled")
            print("  - No HVAC businesses in the search area")
            print("  - Query parameters need adjustment")
            
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
