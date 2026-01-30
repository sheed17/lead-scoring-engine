#!/usr/bin/env python3
"""
Lead Enrichment & Signal Extraction Pipeline

Enriches leads from Step 3 with:
- Place Details (website, phone, reviews)
- Website signals (SSL, mobile-friendly, contact forms, booking widgets)
- Phone normalization
- Review recency analysis

Usage:
    python scripts/run_enrichment.py

Environment Variables:
    GOOGLE_PLACES_API_KEY: Required. Your Google Places API key.

Input:
    Reads from output/leads_*.json (most recent file)

Output:
    Writes to output/enriched_*.json
"""

import os
import sys
import json
import glob
import logging
from datetime import datetime
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.enrich import PlaceDetailsEnricher
from pipeline.signals import (
    extract_signals,
    extract_signals_batch,
    merge_signals_into_lead
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f'enrichment_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "input_dir": "output",
    "output_dir": "output",
    "max_leads": None,  # None = process all, or set a number for testing
    "progress_interval": 10,
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def find_latest_leads_file(input_dir: str) -> str:
    """Find the most recent leads JSON file."""
    pattern = os.path.join(input_dir, "leads_*.json")
    files = glob.glob(pattern)
    
    if not files:
        raise FileNotFoundError(f"No leads files found matching {pattern}")
    
    # Sort by modification time, newest first
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def load_leads(filepath: str) -> List[Dict]:
    """Load leads from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle both wrapped and unwrapped formats
    if isinstance(data, dict) and "leads" in data:
        return data["leads"]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError(f"Unexpected data format in {filepath}")


def save_enriched_leads(
    leads: List[Dict],
    signals: List[Dict],
    output_dir: str,
    source_file: str
) -> str:
    """Save enriched leads with signals to JSON."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Merge signals into leads
    enriched_leads = []
    for lead, signal in zip(leads, signals):
        merged = merge_signals_into_lead(lead, signal)
        enriched_leads.append(merged)
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"enriched_leads_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Build output with metadata
    output_data = {
        "metadata": {
            "source_file": os.path.basename(source_file),
            "enriched_at": datetime.utcnow().isoformat(),
            "total_leads": len(enriched_leads),
            "leads_with_website": sum(1 for s in signals if s.get("has_website")),
            "leads_with_phone": sum(1 for s in signals if s.get("has_phone")),
        },
        "leads": enriched_leads
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved enriched leads to: {filepath}")
    return filepath


def generate_signal_summary(signals: List[Dict]) -> Dict:
    """Generate summary statistics for extracted signals."""
    total = len(signals)
    if total == 0:
        return {}
    
    # Website signals
    has_website = sum(1 for s in signals if s.get("has_website"))
    website_accessible = sum(1 for s in signals if s.get("website_accessible"))
    has_ssl = sum(1 for s in signals if s.get("has_ssl"))
    mobile_friendly = sum(1 for s in signals if s.get("mobile_friendly"))
    has_contact_form = sum(1 for s in signals if s.get("has_contact_form"))
    has_booking = sum(1 for s in signals if s.get("has_booking"))
    
    # Phone signals
    has_phone = sum(1 for s in signals if s.get("has_phone"))
    
    # Review signals
    has_reviews = sum(1 for s in signals if s.get("review_count", 0) > 0)
    ratings = [s["rating"] for s in signals if s.get("rating") is not None]
    review_counts = [s["review_count"] for s in signals if s.get("review_count")]
    
    # Days since last review
    days_since_review = [
        s["last_review_days_ago"] 
        for s in signals 
        if s.get("last_review_days_ago") is not None
    ]
    
    return {
        "total_leads": total,
        "website": {
            "has_website": has_website,
            "has_website_pct": round(has_website / total * 100, 1),
            "accessible": website_accessible,
            "has_ssl": has_ssl,
            "mobile_friendly": mobile_friendly,
            "has_contact_form": has_contact_form,
            "has_booking": has_booking,
        },
        "phone": {
            "has_phone": has_phone,
            "has_phone_pct": round(has_phone / total * 100, 1),
        },
        "reviews": {
            "has_reviews": has_reviews,
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "avg_review_count": round(sum(review_counts) / len(review_counts), 1) if review_counts else None,
            "avg_days_since_review": round(sum(days_since_review) / len(days_since_review), 1) if days_since_review else None,
        }
    }


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_enrichment_pipeline(
    input_file: str = None,
    max_leads: int = None
) -> List[Dict]:
    """
    Run the complete enrichment and signal extraction pipeline.
    
    Args:
        input_file: Path to leads JSON file (default: find latest)
        max_leads: Maximum leads to process (for testing)
    
    Returns:
        List of signal dictionaries
    """
    logger.info("=" * 60)
    logger.info("Lead Enrichment & Signal Extraction Pipeline")
    logger.info("=" * 60)
    
    # Step 1: Load leads
    if input_file is None:
        input_file = find_latest_leads_file(CONFIG["input_dir"])
    
    logger.info(f"Loading leads from: {input_file}")
    leads = load_leads(input_file)
    logger.info(f"Loaded {len(leads)} leads")
    
    # Optionally limit for testing
    if max_leads:
        leads = leads[:max_leads]
        logger.info(f"Limited to {max_leads} leads for processing")
    
    # Step 2: Enrich with Place Details
    logger.info("\nStep 1: Fetching Place Details (website, phone, reviews)...")
    try:
        enricher = PlaceDetailsEnricher()
    except ValueError as e:
        logger.error(f"Cannot initialize enricher: {e}")
        return []
    
    enriched_leads = enricher.enrich_leads_batch(
        leads,
        progress_interval=CONFIG["progress_interval"]
    )
    
    enricher_stats = enricher.get_stats()
    logger.info(f"Place Details API calls: {enricher_stats['total_requests']}")
    logger.info(f"Estimated cost: ${enricher_stats['estimated_cost_usd']:.4f}")
    logger.info(f"Cost optimization: {enricher_stats['savings_vs_all_fields']}")
    
    # Step 3: Extract signals
    logger.info("\nStep 2: Extracting signals (website analysis, phone, reviews)...")
    signals = extract_signals_batch(
        enriched_leads,
        progress_interval=CONFIG["progress_interval"]
    )
    
    # Step 4: Generate summary
    summary = generate_signal_summary(signals)
    
    logger.info("\n" + "=" * 60)
    logger.info("SIGNAL EXTRACTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total leads processed: {summary['total_leads']}")
    logger.info("\nWebsite Signals:")
    logger.info(f"  Has website: {summary['website']['has_website']} ({summary['website']['has_website_pct']}%)")
    logger.info(f"  Accessible: {summary['website']['accessible']}")
    logger.info(f"  Has SSL: {summary['website']['has_ssl']}")
    logger.info(f"  Mobile friendly: {summary['website']['mobile_friendly']}")
    logger.info(f"  Has contact form: {summary['website']['has_contact_form']}")
    logger.info(f"  Has booking widget: {summary['website']['has_booking']}")
    logger.info("\nPhone Signals:")
    logger.info(f"  Has phone: {summary['phone']['has_phone']} ({summary['phone']['has_phone_pct']}%)")
    logger.info("\nReview Signals:")
    logger.info(f"  Has reviews: {summary['reviews']['has_reviews']}")
    logger.info(f"  Avg rating: {summary['reviews']['avg_rating']}")
    logger.info(f"  Avg review count: {summary['reviews']['avg_review_count']}")
    logger.info(f"  Avg days since review: {summary['reviews']['avg_days_since_review']}")
    
    # Step 5: Save results
    output_path = save_enriched_leads(
        enriched_leads,
        signals,
        CONFIG["output_dir"],
        input_file
    )
    
    # Print sample
    logger.info("\n" + "=" * 60)
    logger.info("SAMPLE SIGNALS (first 3 leads)")
    logger.info("=" * 60)
    for signal in signals[:3]:
        logger.info(f"\n{signal.get('place_id', 'N/A')[:20]}...")
        logger.info(f"  Website: {signal.get('website_url', 'None')}")
        logger.info(f"  SSL: {signal.get('has_ssl')} | Mobile: {signal.get('mobile_friendly')} | Form: {signal.get('has_contact_form')}")
        logger.info(f"  Phone: {signal.get('phone_number', 'None')}")
        logger.info(f"  Rating: {signal.get('rating')} | Reviews: {signal.get('review_count')} | Last review: {signal.get('last_review_days_ago')} days ago")
    
    return signals


def main():
    """Main entry point."""
    logger.info(f"Started at: {datetime.now().isoformat()}")
    
    # Check API key
    if not os.getenv("GOOGLE_PLACES_API_KEY"):
        logger.error(
            "GOOGLE_PLACES_API_KEY environment variable not set. "
            "Please set it before running."
        )
        sys.exit(1)
    
    # Run pipeline
    signals = run_enrichment_pipeline(
        max_leads=CONFIG["max_leads"]
    )
    
    logger.info(f"\nCompleted at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
