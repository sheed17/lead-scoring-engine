#!/usr/bin/env python3
"""
Test script for the enrichment and signal extraction pipeline.

Tests the pipeline with a single lead to verify:
- Place Details API connection
- Website signal extraction
- Phone normalization
- Review signal extraction

Usage:
    export GOOGLE_PLACES_API_KEY="your-api-key"
    python test_enrichment.py
"""

import os
import sys
import json

from pipeline.enrich import PlaceDetailsEnricher
from pipeline.signals import extract_signals


def main():
    """Test enrichment with a single lead."""
    print("Testing Lead Enrichment & Signal Extraction\n")
    print("=" * 50)
    
    # Check API key
    if not os.getenv("GOOGLE_PLACES_API_KEY"):
        print("ERROR: GOOGLE_PLACES_API_KEY not set")
        sys.exit(1)
    
    # Sample lead (use a real one from your extraction)
    sample_lead = {
        "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",  # Google Sydney office
        "name": "Test Business",
        "rating": 4.5,
        "user_ratings_total": 100,
    }
    
    # Check if we have extracted leads to test with
    try:
        import glob
        lead_files = glob.glob("output/leads_*.json")
        if lead_files:
            lead_files.sort(key=os.path.getmtime, reverse=True)
            with open(lead_files[0], 'r') as f:
                data = json.load(f)
                leads = data.get("leads", data)
                if leads:
                    sample_lead = leads[0]
                    print(f"Using real lead from: {lead_files[0]}")
    except Exception as e:
        print(f"Using default test lead: {e}")
    
    print(f"\nTest Lead: {sample_lead.get('name', 'Unknown')}")
    print(f"Place ID: {sample_lead.get('place_id', 'N/A')[:30]}...")
    
    # Step 1: Enrich with Place Details
    print("\n" + "-" * 50)
    print("Step 1: Fetching Place Details...")
    
    try:
        enricher = PlaceDetailsEnricher()
        enriched_lead = enricher.enrich_lead(sample_lead)
        
        details = enriched_lead.get("_place_details", {})
        print(f"  Website: {details.get('website', 'None')}")
        print(f"  Phone: {details.get('international_phone_number', 'None')}")
        print(f"  Reviews: {len(details.get('reviews', []))} fetched")
        
        stats = enricher.get_stats()
        print(f"\n  API calls: {stats['total_requests']}")
        print(f"  Est. cost: ${stats['estimated_cost_usd']:.4f}")
        
    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)
    
    # Step 2: Extract signals
    print("\n" + "-" * 50)
    print("Step 2: Extracting signals...")
    
    signals = extract_signals(enriched_lead)
    
    print("\nExtracted Signals:")
    print(json.dumps(signals, indent=2, default=str))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)
    
    if signals.get("has_website"):
        print("✓ Website detected and analyzed")
    else:
        print("✗ No website found")
    
    if signals.get("has_phone"):
        print(f"✓ Phone: {signals.get('phone_number')}")
    else:
        print("✗ No phone found")
    
    if signals.get("review_count", 0) > 0:
        print(f"✓ Reviews: {signals.get('review_count')} (last {signals.get('last_review_days_ago')} days ago)")
    else:
        print("✗ No reviews found")


if __name__ == "__main__":
    main()
