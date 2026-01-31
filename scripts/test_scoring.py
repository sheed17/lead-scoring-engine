#!/usr/bin/env python3
"""
Test the scoring model with sample leads.

No API calls. No pipeline. Just scoring logic validation.

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
    # --- ELITE CANDIDATE (should score 100) ---
    {
        "name": "🏆 Elite HVAC Lead",
        "description": "Perfect: manual, stale reviews, all contact paths, high confidence",
        "signal_has_website": True,
        "signal_website_accessible": True,
        "signal_has_phone": True,
        "signal_has_contact_form": True,
        "signal_has_email": True,
        "signal_has_automated_scheduling": False,
        "signal_has_trust_badges": False,
        "signal_review_count": 25,
        "signal_last_review_days_ago": 200,
        "signal_rating": 4.5,
    },
    # --- HIGH BUT NOT ELITE ---
    {
        "name": "Strong Lead - Fresh Reviews",
        "description": "Great signals but fresh reviews = not elite",
        "signal_has_website": True,
        "signal_website_accessible": True,
        "signal_has_phone": True,
        "signal_has_contact_form": True,
        "signal_has_email": True,
        "signal_has_automated_scheduling": False,
        "signal_has_trust_badges": False,
        "signal_review_count": 40,
        "signal_last_review_days_ago": 15,  # Fresh = can't be 100
        "signal_rating": 4.8,
    },
    {
        "name": "Strong Lead - Low Confidence",
        "description": "Good signals but missing data = capped",
        "signal_has_website": True,
        "signal_website_accessible": True,
        "signal_has_phone": True,
        "signal_has_contact_form": True,
        "signal_has_email": None,  # Unknown
        "signal_has_automated_scheduling": None,  # Unknown
        "signal_has_trust_badges": None,
        "signal_review_count": 30,
        "signal_last_review_days_ago": 120,
        "signal_rating": 4.6,
    },
    # --- ALREADY OPTIMIZED ---
    {
        "name": "Automated Business",
        "description": "Uses ServiceTitan - already optimized, penalties apply",
        "signal_has_website": True,
        "signal_website_accessible": True,
        "signal_has_phone": True,
        "signal_has_contact_form": True,
        "signal_has_email": True,
        "signal_has_automated_scheduling": True,  # -5 penalty
        "signal_has_trust_badges": True,  # -3 penalty
        "signal_review_count": 85,
        "signal_last_review_days_ago": 10,  # Fresh
        "signal_rating": 4.9,
    },
    # --- LARGE BRAND (CAPPED) ---
    {
        "name": "Big Brand HVAC",
        "description": "200+ reviews = capped at 92",
        "signal_has_website": True,
        "signal_website_accessible": True,
        "signal_has_phone": True,
        "signal_has_contact_form": True,
        "signal_has_email": True,
        "signal_has_automated_scheduling": False,
        "signal_has_trust_badges": True,
        "signal_review_count": 350,
        "signal_last_review_days_ago": 5,
        "signal_rating": 4.7,
    },
    {
        "name": "Medium Brand HVAC",
        "description": "100+ reviews = capped at 95",
        "signal_has_website": True,
        "signal_website_accessible": True,
        "signal_has_phone": True,
        "signal_has_contact_form": True,
        "signal_has_email": True,
        "signal_has_automated_scheduling": False,
        "signal_has_trust_badges": False,
        "signal_review_count": 150,
        "signal_last_review_days_ago": 45,
        "signal_rating": 4.6,
    },
    # --- SMALL/UNDERSERVED ---
    {
        "name": "Phone Only Business",
        "description": "No website, just phone - common for small HVAC",
        "signal_has_website": False,
        "signal_website_accessible": False,
        "signal_has_phone": True,
        "signal_has_contact_form": False,
        "signal_has_email": False,
        "signal_has_automated_scheduling": False,
        "signal_has_trust_badges": False,
        "signal_review_count": 8,
        "signal_last_review_days_ago": 300,
        "signal_rating": 4.2,
    },
    # --- LOW CONFIDENCE ---
    {
        "name": "Minimal Data Lead",
        "description": "Most signals unknown - confidence dampens score",
        "signal_has_website": True,
        "signal_website_accessible": None,
        "signal_has_phone": True,
        "signal_has_contact_form": None,
        "signal_has_email": None,
        "signal_has_automated_scheduling": None,
        "signal_has_trust_badges": None,
        "signal_review_count": None,
        "signal_last_review_days_ago": None,
        "signal_rating": None,
    },
    # --- DISQUALIFIED ---
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
        "signal_review_count": 3,
        "signal_last_review_days_ago": 400,
        "signal_rating": 3.5,
    },
]


def main():
    print("=" * 70)
    print("SCORING MODEL TEST")
    print("=" * 70)
    print("\nTesting with sample leads (no API calls)\n")
    
    scored_leads = []
    
    for lead in SAMPLE_LEADS:
        result = score_lead(lead)
        
        # Store for summary
        scored_lead = lead.copy()
        scored_lead.update(result.to_dict())
        scored_leads.append(scored_lead)
        
        # Display result
        print("-" * 70)
        print(f"📍 {lead['name']}")
        print(f"   {lead.get('description', '')}")
        print()
        print(f"   Score: {result.lead_score} | Priority: {result.priority} | Confidence: {result.confidence}")
        print()
        
        # Review summary
        rs = result.review_summary
        print(f"   📊 Reviews: {rs['review_count'] or 'N/A'} ({rs['volume']}) | Rating: {rs['rating'] or 'N/A'}")
        print(f"   📅 Last Review: {rs['last_review_text']} ({rs['freshness']})")
        print()
        
        print("   Reasons:")
        for reason in result.reasons:
            print(f"     • {reason}")
        print()
        
        # Show input signals for debugging
        print("   Input Signals:")
        for key, value in lead.items():
            if key.startswith("signal_"):
                signal_name = key[7:]
                print(f"     {signal_name}: {json.dumps(value)}")
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    summary = get_scoring_summary(scored_leads)
    
    # Score distribution buckets
    scores = [l.get("lead_score", 0) for l in scored_leads]
    elite_100 = sum(1 for s in scores if s == 100)
    very_strong = sum(1 for s in scores if 95 <= s < 100)
    strong = sum(1 for s in scores if 90 <= s < 95)
    solid = sum(1 for s in scores if 80 <= s < 90)
    below_80 = sum(1 for s in scores if s < 80)
    
    print(f"\n📊 Score Distribution:")
    print(f"  🏆 100 (Elite):      {elite_100}")
    print(f"  ⭐ 95-99 (Very Strong): {very_strong}")
    print(f"  💪 90-94 (Strong):   {strong}")
    print(f"  ✓  80-89 (Solid):    {solid}")
    print(f"  📉 <80:              {below_80}")
    print(f"\n  Average: {summary['score']['avg']} | Range: {summary['score']['min']} - {summary['score']['max']}")
    
    print(f"\n🎯 Priority Breakdown:")
    print(f"  🔥 High:   {summary['priority']['high']} ({summary['priority']['high_pct']}%)")
    print(f"  🟡 Medium: {summary['priority']['medium']} ({summary['priority']['medium_pct']}%)")
    print(f"  ⚪ Low:    {summary['priority']['low']} ({summary['priority']['low_pct']}%)")
    
    print(f"\n📈 Confidence:")
    print(f"  Average: {summary['confidence']['avg']}")
    print(f"  Range: {summary['confidence']['min']} - {summary['confidence']['max']}")
    
    # Elite check
    print(f"\n✅ Elite (100) leads: {elite_100} out of {len(scored_leads)}")
    if elite_100 == 0:
        print("   (100 is reserved for elite leads meeting ALL criteria)")
    
    print("\n" + "=" * 70)
    print("✓ Test complete - no API calls made")
    print("=" * 70)


if __name__ == "__main__":
    main()
