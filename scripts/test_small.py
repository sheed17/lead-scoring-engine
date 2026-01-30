#!/usr/bin/env python3
"""
Small-scale test pipeline for development and testing.

Makes minimal API calls to verify the full pipeline works:
- 1 grid point (city center only)
- 1 keyword
- 1 page (no pagination)
- 3 leads enriched max

Expected API calls: ~4 total
- 1 Nearby Search call (~$0.032)
- 3 Place Details calls (~$0.024)
Total cost: ~$0.06

Usage:
    export GOOGLE_PLACES_API_KEY="your-api-key"
    python scripts/test_small.py
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.fetch import PlacesFetcher
from pipeline.normalize import normalize_place, deduplicate_places
from pipeline.enrich import PlaceDetailsEnricher
from pipeline.signals import extract_signals, merge_signals_into_lead

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# MINIMAL TEST CONFIGURATION
# ============================================================================

TEST_CONFIG = {
    # Location: San Jose city center
    "lat": 37.3382,
    "lng": -121.8863,
    "radius_m": 2000,  # 2km radius
    
    # Single keyword
    "keyword": "HVAC",
    
    # Limits
    "max_pages": 1,      # Only first page (20 results max)
    "max_leads": 3,      # Only enrich 3 leads
    
    # Output
    "output_file": "output/test_small_results.json"
}


def run_small_test():
    """Run minimal pipeline test."""
    logger.info("=" * 60)
    logger.info("SMALL-SCALE PIPELINE TEST")
    logger.info("=" * 60)
    logger.info(f"Expected API calls: ~4")
    logger.info(f"Expected cost: ~$0.06")
    logger.info("=" * 60)
    
    # Check API key
    if not os.getenv("GOOGLE_PLACES_API_KEY"):
        logger.error("GOOGLE_PLACES_API_KEY not set")
        sys.exit(1)
    
    # =========================================
    # Step 1: Fetch nearby places (1 API call)
    # =========================================
    logger.info("\n[Step 1] Fetching nearby places...")
    logger.info(f"  Location: ({TEST_CONFIG['lat']}, {TEST_CONFIG['lng']})")
    logger.info(f"  Radius: {TEST_CONFIG['radius_m']}m")
    logger.info(f"  Keyword: {TEST_CONFIG['keyword']}")
    
    fetcher = PlacesFetcher()
    
    raw_places = list(fetcher.fetch_all_pages_for_query(
        lat=TEST_CONFIG["lat"],
        lng=TEST_CONFIG["lng"],
        radius_m=TEST_CONFIG["radius_m"],
        keyword=TEST_CONFIG["keyword"],
        max_pages=TEST_CONFIG["max_pages"]
    ))
    
    fetch_stats = fetcher.get_stats()
    logger.info(f"  API calls made: {fetch_stats['total_requests']}")
    logger.info(f"  Results fetched: {len(raw_places)}")
    
    if not raw_places:
        logger.error("No places found! Check API key and location.")
        sys.exit(1)
    
    # =========================================
    # Step 2: Normalize and deduplicate
    # =========================================
    logger.info("\n[Step 2] Normalizing places...")
    
    normalized = [normalize_place(p) for p in raw_places]
    unique = deduplicate_places(normalized)
    
    logger.info(f"  Normalized: {len(normalized)}")
    logger.info(f"  After dedup: {len(unique)}")
    
    # Limit to max_leads for enrichment
    leads_to_enrich = unique[:TEST_CONFIG["max_leads"]]
    logger.info(f"  Will enrich: {len(leads_to_enrich)} leads")
    
    # =========================================
    # Step 3: Enrich with Place Details (3 API calls)
    # =========================================
    logger.info("\n[Step 3] Enriching with Place Details...")
    
    enricher = PlaceDetailsEnricher()
    enriched_leads = []
    
    for lead in leads_to_enrich:
        enriched = enricher.enrich_lead(lead)
        enriched_leads.append(enriched)
        
        details = enriched.get("_place_details", {})
        logger.info(f"  ✓ {lead['name'][:40]}")
        logger.info(f"    Website: {details.get('website', 'None')}")
        logger.info(f"    Phone: {details.get('formatted_phone_number', 'None')}")
    
    enrich_stats = enricher.get_stats()
    logger.info(f"\n  Place Details API calls: {enrich_stats['total_requests']}")
    logger.info(f"  Estimated cost: ${enrich_stats['estimated_cost_usd']:.4f}")
    
    # =========================================
    # Step 4: Extract signals
    # =========================================
    logger.info("\n[Step 4] Extracting signals...")
    
    final_leads = []
    for lead in enriched_leads:
        signals = extract_signals(lead)
        merged = merge_signals_into_lead(lead, signals)
        final_leads.append(merged)
        
        logger.info(f"  ✓ {lead['name'][:40]}")
        logger.info(f"    📞 Phone: {signals.get('phone_number') or 'null'}")
        logger.info(f"    📝 Contact Form: {signals.get('has_contact_form')} | Email: {signals.get('has_email')}")
        logger.info(f"    ⚙️ Auto-scheduling: {signals.get('has_automated_scheduling')} | Trust: {signals.get('has_trust_badges')}")
        logger.info(f"    ⭐ Rating: {signals.get('rating')} | Reviews: {signals.get('review_count')}")
    
    # =========================================
    # Step 5: Save results
    # =========================================
    logger.info("\n[Step 5] Saving results...")
    
    os.makedirs(os.path.dirname(TEST_CONFIG["output_file"]), exist_ok=True)
    
    output_data = {
        "metadata": {
            "test_run": True,
            "timestamp": datetime.utcnow().isoformat(),
            "api_calls": {
                "nearby_search": fetch_stats["total_requests"],
                "place_details": enrich_stats["total_requests"],
                "total": fetch_stats["total_requests"] + enrich_stats["total_requests"]
            },
            "estimated_cost_usd": round(
                fetch_stats["total_requests"] * 0.032 + 
                enrich_stats["total_requests"] * 0.008,
                4
            )
        },
        "leads": final_leads
    }
    
    with open(TEST_CONFIG["output_file"], 'w') as f:
        json.dump(output_data, f, indent=2, default=str)
    
    logger.info(f"  Saved to: {TEST_CONFIG['output_file']}")
    
    # =========================================
    # Summary
    # =========================================
    logger.info("\n" + "=" * 60)
    logger.info("TEST COMPLETE - SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total API calls: {output_data['metadata']['api_calls']['total']}")
    logger.info(f"Estimated cost: ${output_data['metadata']['estimated_cost_usd']:.4f}")
    logger.info(f"Leads processed: {len(final_leads)}")
    logger.info(f"Output file: {TEST_CONFIG['output_file']}")
    
    # Print one full example
    if final_leads:
        logger.info("\n" + "-" * 60)
        logger.info("SAMPLE OUTPUT (first lead):")
        logger.info("-" * 60)
        sample = {k: v for k, v in final_leads[0].items() if k.startswith('signal_') or k in ['place_id', 'name', 'address']}
        print(json.dumps(sample, indent=2, default=str))
    
    return final_leads


if __name__ == "__main__":
    run_small_test()
