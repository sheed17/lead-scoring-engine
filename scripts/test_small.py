#!/usr/bin/env python3
"""
Small-scale test pipeline for dentist vertical (SEO agency opportunity intelligence).

Runs the FULL pipeline with minimal API calls:
1. Fetch nearby dental practices (1 search)
2. Normalize & deduplicate
3. Enrich with Place Details
4. Extract signals
5. Decision Agent (verdict + reasoning)
6. Dentist vertical: dentist_profile_v1 + LLM reasoning layer (for dental leads only)
7. Save results

Expected API calls: ~6 total (1 search + 5 Place Details)
- 1 Nearby Search call (~$0.032)
- 5 Place Details calls (~$0.04)
Total cost: ~$0.07

Usage:
    export GOOGLE_PLACES_API_KEY="your-api-key"
    export OPENAI_API_KEY="your-openai-key"   # optional, for review summary + dentist LLM
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
from pipeline.meta_ads import get_meta_access_token, augment_lead_with_meta_ads
from pipeline.semantic_signals import build_semantic_signals
from pipeline.decision_agent import DecisionAgent
from pipeline.context import build_context
from pipeline.dentist_profile import (
    is_dental_practice,
    build_dentist_profile_v1,
    fetch_website_html_for_trust,
)
from pipeline.dentist_llm_reasoning import dentist_llm_reasoning_layer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# DENTIST TEST CONFIGURATION
# ============================================================================

TEST_CONFIG = {
    # Location: San Jose city center (good dental density)
    "lat": 37.3382,
    "lng": -121.8863,
    "radius_m": 2000,  # 2km radius
    
    # Dentist-specific keyword (Google Places returns dental practices)
    "keyword": "dentist",
    
    # Limits
    "max_pages": 1,      # Only first page (20 results max)
    "max_leads": 5,     # Enrich 5 leads to get a few dental practices
    
    # Output
    "output_file": "output/test_small_results_dentist.json"
}


def run_small_test():
    """Run minimal pipeline test."""
    logger.info("=" * 60)
    logger.info("DENTIST PIPELINE TEST (small-scale)")
    logger.info("=" * 60)
    logger.info(f"Keyword: {TEST_CONFIG['keyword']} | Max leads: {TEST_CONFIG['max_leads']}")
    logger.info(f"Expected API calls: ~{1 + TEST_CONFIG['max_leads']} (1 search + {TEST_CONFIG['max_leads']} Place Details)")
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
    if get_meta_access_token():
        logger.info("  (META_ACCESS_TOKEN set — will augment with Meta Ads Library)")
    for lead in enriched_leads:
        signals = extract_signals(lead)
        merged = merge_signals_into_lead(lead, signals)
        if get_meta_access_token():
            augment_lead_with_meta_ads(merged)
        final_leads.append(merged)
        
        logger.info(f"  ✓ {lead['name'][:40]}")
        logger.info(f"    📞 Phone: {signals.get('phone_number') or 'null'}")
        logger.info(f"    📝 Contact Form: {signals.get('has_contact_form')} | Email: {signals.get('has_email')}")
        logger.info(f"    ⚙️ Auto-scheduling: {signals.get('has_automated_scheduling')} | Trust: {signals.get('has_trust_badges')}")
        logger.info(f"    ⭐ Rating: {signals.get('rating')} | Reviews: {signals.get('review_count')}")
        if get_meta_access_token():
            meta_info = merged.get("signal_meta_ads_count")
            if meta_info is not None:
                logger.info(f"    📢 Meta Ads: %s ad(s) in library", meta_info)
            elif merged.get("signal_meta_ads_source"):
                logger.info(f"    📢 Meta Ads: checked (meta_ads_library)")
            else:
                logger.info(f"    📢 Meta Ads: checked — none in library for US")
    
    # =========================================
    # Step 5: Decision Agent (verdict + reasoning; no embeddings in v1)
    # =========================================
    agency_type = os.getenv("AGENCY_TYPE", "marketing").lower() or "marketing"
    if agency_type not in ("seo", "marketing"):
        agency_type = "marketing"
    logger.info("\n[Step 5] Decision Agent (agency_type=%s)...", agency_type)
    agent = DecisionAgent(agency_type=agency_type)
    
    for lead in final_leads:
        semantic = build_semantic_signals(lead)
        decision = agent.decide(semantic, lead_name=lead.get("name") or "")
        lead["verdict"] = decision.verdict
        lead["confidence"] = decision.confidence
        lead["reasoning"] = decision.reasoning
        lead["primary_risks"] = decision.primary_risks
        lead["what_would_change"] = decision.what_would_change
        lead["agency_type"] = agency_type
        
        logger.info(f"  ✓ {lead['name'][:40]}")
        logger.info(f"    Verdict: {decision.verdict} | Confidence: {decision.confidence}")
        r = decision.reasoning
        logger.info(f"    Reasoning: %s", (r[:120] + "...") if len(r) > 120 else r)
        if decision.primary_risks:
            logger.info(f"    Risks: %s", decision.primary_risks[:2])
        if decision.what_would_change:
            logger.info(f"    Would change: %s", decision.what_would_change[:2])
    
    # =========================================
    # Step 6: Dentist vertical (profile + LLM reasoning for dental leads only)
    # =========================================
    logger.info("\n[Step 6] Dentist vertical (profile + LLM for dental leads)...")
    dentist_count = 0
    for lead in final_leads:
        if not is_dental_practice(lead):
            continue
        dentist_count += 1
        url = lead.get("signal_website_url")
        website_html = fetch_website_html_for_trust(url) if url else None
        dentist_profile_v1 = build_dentist_profile_v1(lead, website_html=website_html)
        lead["dentist_profile_v1"] = dentist_profile_v1
        llm_layer = {}
        if dentist_profile_v1:
            context = build_context(lead)
            lead_score = round((lead.get("confidence") or 0) * 100)
            llm_layer = dentist_llm_reasoning_layer(
                business_snapshot=lead,
                dentist_profile_v1=dentist_profile_v1,
                context_dimensions=context.get("context_dimensions", []),
                lead_score=lead_score,
                priority=lead.get("verdict"),
                confidence=lead.get("confidence"),
            )
        lead["llm_reasoning_layer"] = llm_layer if llm_layer else {}
        logger.info(f"  ✓ {lead['name'][:40]} (dental)")
        if dentist_profile_v1:
            af = dentist_profile_v1.get("agency_fit_reasoning", {})
            logger.info(f"    ideal_for_seo_outreach=%s | LTV=%s", af.get("ideal_for_seo_outreach"), dentist_profile_v1.get("dental_practice_profile", {}).get("estimated_ltv_class"))
        if llm_layer and llm_layer.get("executive_summary"):
            logger.info(f"    LLM summary: %s", (llm_layer["executive_summary"][:80] + "...") if len(llm_layer["executive_summary"]) > 80 else llm_layer["executive_summary"])
    logger.info(f"  Dental leads with profile: {dentist_count}/{len(final_leads)}")
    
    # =========================================
    # Step 7: Save results
    # =========================================
    logger.info("\n[Step 7] Saving results...")
    
    os.makedirs(os.path.dirname(TEST_CONFIG["output_file"]), exist_ok=True)
    
    output_data = {
        "metadata": {
            "test_run": True,
            "vertical": "dentist",
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
            ),
            "dentist_leads_with_profile": sum(1 for l in final_leads if l.get("dentist_profile_v1")),
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
    
    # Print decision summary
    if final_leads:
        verdicts = [l.get("verdict") for l in final_leads if l.get("verdict")]
        high = sum(1 for v in verdicts if v == "HIGH")
        medium = sum(1 for v in verdicts if v == "MEDIUM")
        low = sum(1 for v in verdicts if v == "LOW")
        logger.info(f"\nDecision Summary:")
        logger.info(f"  Verdicts: HIGH=%s MEDIUM=%s LOW=%s", high, medium, low)
        dentist_with_profile = sum(1 for l in final_leads if l.get("dentist_profile_v1"))
        logger.info(f"  Dentist profile: %s/%s leads", dentist_with_profile, len(final_leads))
    
    # Print one full example (decision-first; include dentist_profile_v1 / llm_reasoning_layer if present)
    if final_leads:
        logger.info("\n" + "-" * 60)
        logger.info("SAMPLE OUTPUT (first lead):")
        logger.info("-" * 60)
        sample = {k: v for k, v in final_leads[0].items()
                  if k in (
                      "place_id", "name", "address",
                      "verdict", "confidence", "reasoning",
                      "primary_risks", "what_would_change", "agency_type",
                      "dentist_profile_v1", "llm_reasoning_layer",
                  ) or k.startswith("signal_")}
        print(json.dumps(sample, indent=2, default=str))
    
    return final_leads


if __name__ == "__main__":
    run_small_test()
