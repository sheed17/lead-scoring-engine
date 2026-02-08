#!/usr/bin/env python3
"""
Test the Opportunity Intelligence system with sample leads.

No API calls. No pipeline. Just opportunity + scoring logic validation.

Usage:
    python scripts/test_scoring.py
"""

import os
import sys
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.score import score_lead, get_scoring_summary


# =============================================================================
# SAMPLE LEADS FOR TESTING
# =============================================================================

SAMPLE_LEADS = [
    # --- PAID TRAFFIC LEAKAGE ---
    {
        "name": "Ads Running, No Conversion",
        "description": "Running Google Ads but no contact form, no scheduling",
        "signal_has_website": True,
        "signal_website_accessible": True,
        "signal_has_phone": True,
        "signal_has_contact_form": False,
        "signal_has_email": False,
        "signal_has_automated_scheduling": False,
        "signal_has_trust_badges": False,
        "signal_runs_paid_ads": True,
        "signal_paid_ads_channels": ["google"],
        "signal_hiring_active": False,
        "signal_hiring_roles": None,
        "signal_review_count": 35,
        "signal_last_review_days_ago": 45,
        "signal_rating": 4.5,
        "signal_review_velocity_30d": 1,
        "signal_rating_delta_60d": None,
    },
    # --- OPERATIONAL SCALING PRESSURE ---
    {
        "name": "Growing HVAC Co - Hiring + Manual",
        "description": "Hiring technicians, no automation, strong reviews",
        "signal_has_website": True,
        "signal_website_accessible": True,
        "signal_has_phone": True,
        "signal_has_contact_form": True,
        "signal_has_email": True,
        "signal_has_automated_scheduling": False,
        "signal_has_trust_badges": False,
        "signal_runs_paid_ads": False,
        "signal_paid_ads_channels": None,
        "signal_hiring_active": True,
        "signal_hiring_roles": ["technician", "front_desk"],
        "signal_review_count": 65,
        "signal_last_review_days_ago": 12,
        "signal_rating": 4.7,
        "signal_review_velocity_30d": 3,
        "signal_rating_delta_60d": 0.2,
    },
    # --- REPUTATION RECOVERY ---
    {
        "name": "Stale Reviews HVAC",
        "description": "Very stale reviews, low count, declining rating",
        "signal_has_website": True,
        "signal_website_accessible": True,
        "signal_has_phone": True,
        "signal_has_contact_form": None,  # Unknown
        "signal_has_email": None,
        "signal_has_automated_scheduling": False,
        "signal_has_trust_badges": False,
        "signal_runs_paid_ads": False,
        "signal_paid_ads_channels": None,
        "signal_hiring_active": False,
        "signal_hiring_roles": None,
        "signal_review_count": 8,
        "signal_last_review_days_ago": 280,
        "signal_rating": 3.8,
        "signal_review_velocity_30d": 0,
        "signal_rating_delta_60d": -0.5,
    },
    # --- DIGITAL PRESENCE GAP ---
    {
        "name": "Phone-Only HVAC",
        "description": "Active business with no website at all",
        "signal_has_website": False,
        "signal_website_accessible": False,
        "signal_has_phone": True,
        "signal_has_contact_form": None,
        "signal_has_email": None,
        "signal_has_automated_scheduling": None,
        "signal_has_trust_badges": None,
        "signal_runs_paid_ads": None,
        "signal_paid_ads_channels": None,
        "signal_hiring_active": None,
        "signal_hiring_roles": None,
        "signal_review_count": 22,
        "signal_last_review_days_ago": 90,
        "signal_rating": 4.3,
        "signal_review_velocity_30d": None,
        "signal_rating_delta_60d": None,
    },
    # --- ALREADY OPTIMIZED ---
    {
        "name": "Fully Optimized Big Brand",
        "description": "Has everything, automated, 200+ reviews - low opportunity",
        "signal_has_website": True,
        "signal_website_accessible": True,
        "signal_has_phone": True,
        "signal_has_contact_form": True,
        "signal_has_email": True,
        "signal_has_automated_scheduling": True,
        "signal_has_trust_badges": True,
        "signal_runs_paid_ads": True,
        "signal_paid_ads_channels": ["google", "meta"],
        "signal_hiring_active": False,
        "signal_hiring_roles": None,
        "signal_review_count": 350,
        "signal_last_review_days_ago": 3,
        "signal_rating": 4.9,
        "signal_review_velocity_30d": 5,
        "signal_rating_delta_60d": 0.1,
    },
    # --- MINIMAL DATA ---
    {
        "name": "Minimal Data Lead",
        "description": "Almost everything unknown - low confidence",
        "signal_has_website": True,
        "signal_website_accessible": None,
        "signal_has_phone": True,
        "signal_has_contact_form": None,
        "signal_has_email": None,
        "signal_has_automated_scheduling": None,
        "signal_has_trust_badges": None,
        "signal_runs_paid_ads": None,
        "signal_paid_ads_channels": None,
        "signal_hiring_active": None,
        "signal_hiring_roles": None,
        "signal_review_count": None,
        "signal_last_review_days_ago": None,
        "signal_rating": None,
        "signal_review_velocity_30d": None,
        "signal_rating_delta_60d": None,
    },
    # --- UNREACHABLE ---
    {
        "name": "Unreachable Business",
        "description": "No contact methods at all - disqualified",
        "signal_has_website": False,
        "signal_website_accessible": False,
        "signal_has_phone": False,
        "signal_has_contact_form": False,
        "signal_has_email": False,
        "signal_has_automated_scheduling": False,
        "signal_has_trust_badges": False,
        "signal_runs_paid_ads": False,
        "signal_paid_ads_channels": None,
        "signal_hiring_active": False,
        "signal_hiring_roles": None,
        "signal_review_count": 3,
        "signal_last_review_days_ago": 400,
        "signal_rating": 3.5,
        "signal_review_velocity_30d": 0,
        "signal_rating_delta_60d": None,
    },
]


def main():
    print("=" * 70)
    print("OPPORTUNITY INTELLIGENCE TEST")
    print("=" * 70)
    print("\nTesting with sample leads (no API calls)\n")
    
    scored_leads = []
    
    for lead in SAMPLE_LEADS:
        result = score_lead(lead)
        
        scored_lead = lead.copy()
        scored_lead.update(result.to_dict())
        scored_leads.append(scored_lead)
        
        # Display result
        print("-" * 70)
        print(f"  {lead['name']}")
        print(f"  {lead.get('description', '')}")
        print()
        print(f"  Priority: {result.priority} | Score: {result.lead_score} | Confidence: {result.confidence}")
        print()
        
        # Opportunities (PRIMARY output)
        if result.opportunities:
            print(f"  Opportunities Detected ({len(result.opportunities)}):")
            for opp in result.opportunities:
                print(f"    [{opp['strength']}] [{opp['timing']}] {opp['type']}")
                for ev in opp["evidence"]:
                    print(f"      - {ev}")
                print(f"      (confidence: {opp['confidence']})")
            print()
        else:
            print("  No strong opportunities detected")
            print()
        
        # Review summary
        rs = result.review_summary
        print(f"  Reviews: {rs['review_count'] or 'N/A'} ({rs['volume']}) | Rating: {rs['rating'] or 'N/A'}")
        print(f"  Last Review: {rs['last_review_text']} ({rs['freshness']})")
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    summary = get_scoring_summary(scored_leads)
    
    print(f"\nPriority Breakdown:")
    print(f"  High:   {summary['priority']['high']} ({summary['priority']['high_pct']}%)")
    print(f"  Medium: {summary['priority']['medium']} ({summary['priority']['medium_pct']}%)")
    print(f"  Low:    {summary['priority']['low']} ({summary['priority']['low_pct']}%)")
    
    print(f"\nConfidence:")
    print(f"  Average: {summary['confidence']['avg']}")
    print(f"  Range: {summary['confidence']['min']} - {summary['confidence']['max']}")
    
    print(f"\nOpportunity Distribution:")
    print(f"  Avg per lead: {summary['opportunities']['avg_per_lead']}")
    for opp_type, count in summary['opportunities']['by_type'].items():
        pct = round(count / len(scored_leads) * 100, 1)
        print(f"  {opp_type}: {count} ({pct}%)")
    
    print(f"\nInternal Score (for sorting only):")
    print(f"  Average: {summary['score']['avg']}")
    print(f"  Range: {summary['score']['min']} - {summary['score']['max']}")
    
    print("\n" + "=" * 70)
    print("Done - no API calls made")
    print("=" * 70)


if __name__ == "__main__":
    main()
