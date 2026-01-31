#!/usr/bin/env python3
"""
Lead Scoring Pipeline (Step 5)

Scores enriched leads and outputs prioritized results.

Usage:
    python scripts/run_scoring.py
"""

import os
import sys
import json
import glob
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.score import score_leads_batch, get_scoring_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_latest_enriched_file(input_dir: str = "output") -> str:
    """Find the most recent enriched leads JSON file."""
    pattern = os.path.join(input_dir, "enriched_leads_*.json")
    files = glob.glob(pattern)
    
    if not files:
        raise FileNotFoundError(f"No enriched files found matching {pattern}")
    
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def load_leads(filepath: str) -> list:
    """Load leads from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, dict) and "leads" in data:
        return data["leads"]
    return data


def save_scored_leads(leads: list, output_dir: str = "output") -> str:
    """Save scored leads to JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scored_leads_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Get summary
    summary = get_scoring_summary(leads)
    
    output_data = {
        "metadata": {
            "scored_at": datetime.utcnow().isoformat(),
            "total_leads": len(leads),
            "summary": summary
        },
        "leads": leads
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved scored leads to: {filepath}")
    return filepath


def main():
    """Run the scoring pipeline."""
    logger.info("=" * 60)
    logger.info("LEAD SCORING PIPELINE (V1)")
    logger.info("=" * 60)
    
    # Find input file
    try:
        input_file = find_latest_enriched_file()
    except FileNotFoundError as e:
        logger.error(str(e))
        logger.error("Run the enrichment pipeline first: python scripts/run_enrichment.py")
        sys.exit(1)
    
    logger.info(f"Loading from: {input_file}")
    leads = load_leads(input_file)
    logger.info(f"Found {len(leads)} leads to score")
    
    # Score leads
    logger.info("\nScoring leads...")
    scored_leads = score_leads_batch(leads)
    
    # Get summary
    summary = get_scoring_summary(scored_leads)
    
    # Display summary
    logger.info("\n" + "=" * 60)
    logger.info("SCORING SUMMARY")
    logger.info("=" * 60)
    
    # Score distribution buckets
    scores = [l.get("lead_score", 0) for l in scored_leads]
    elite_100 = sum(1 for s in scores if s == 100)
    very_strong = sum(1 for s in scores if 95 <= s < 100)
    strong = sum(1 for s in scores if 90 <= s < 95)
    solid = sum(1 for s in scores if 80 <= s < 90)
    below_80 = sum(1 for s in scores if s < 80)
    
    logger.info(f"\n📊 Score Distribution:")
    logger.info(f"   🏆 100 (Elite):       {elite_100} ({elite_100/len(scored_leads)*100:.1f}%)")
    logger.info(f"   ⭐ 95-99 (Very Strong): {very_strong} ({very_strong/len(scored_leads)*100:.1f}%)")
    logger.info(f"   💪 90-94 (Strong):    {strong} ({strong/len(scored_leads)*100:.1f}%)")
    logger.info(f"   ✓  80-89 (Solid):     {solid} ({solid/len(scored_leads)*100:.1f}%)")
    logger.info(f"   📉 <80:               {below_80} ({below_80/len(scored_leads)*100:.1f}%)")
    logger.info(f"\n   Average: {summary['score']['avg']} | Range: {summary['score']['min']} - {summary['score']['max']}")
    
    logger.info(f"\n🎯 Priority Breakdown:")
    logger.info(f"   🔥 High:   {summary['priority']['high']} ({summary['priority']['high_pct']}%)")
    logger.info(f"   🟡 Medium: {summary['priority']['medium']} ({summary['priority']['medium_pct']}%)")
    logger.info(f"   ⚪ Low:    {summary['priority']['low']} ({summary['priority']['low_pct']}%)")
    
    logger.info(f"\n📈 Confidence:")
    logger.info(f"   Average: {summary['confidence']['avg']}")
    logger.info(f"   Range: {summary['confidence']['min']} - {summary['confidence']['max']}")
    
    # Save results
    output_path = save_scored_leads(scored_leads)
    
    # Show top leads
    logger.info("\n" + "=" * 60)
    logger.info("TOP 5 HIGH-PRIORITY LEADS")
    logger.info("=" * 60)
    
    high_priority = [l for l in scored_leads if l.get("priority") == "High"]
    high_priority.sort(key=lambda x: x.get("lead_score", 0), reverse=True)
    
    for i, lead in enumerate(high_priority[:5], 1):
        logger.info(f"\n{i}. {lead.get('name', 'Unknown')}")
        logger.info(f"   Score: {lead.get('lead_score')} | Confidence: {lead.get('confidence')}")
        logger.info(f"   Phone: {lead.get('signal_phone_number', 'N/A')}")
        logger.info(f"   Reasons:")
        for reason in lead.get('reasons', [])[:3]:
            logger.info(f"     • {reason}")
    
    logger.info(f"\n✓ Complete! Results saved to: {output_path}")


if __name__ == "__main__":
    main()
