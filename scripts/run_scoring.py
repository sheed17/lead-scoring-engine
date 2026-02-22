#!/usr/bin/env python3
"""
Opportunity Intelligence Pipeline

Analyzes enriched leads for business opportunities and prioritizes them.

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


def save_analyzed_leads(leads: list, output_dir: str = "output") -> str:
    """Save analyzed leads to JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scored_leads_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    summary = get_scoring_summary(leads)
    
    output_data = {
        "metadata": {
            "analyzed_at": datetime.utcnow().isoformat(),
            "total_leads": len(leads),
            "summary": summary
        },
        "leads": leads
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved analyzed leads to: {filepath}")
    return filepath


def main():
    """Run the opportunity intelligence pipeline."""
    logger.info("=" * 60)
    logger.info("OPPORTUNITY INTELLIGENCE PIPELINE")
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
    logger.info(f"Found {len(leads)} leads to analyze")
    
    # Analyze leads
    logger.info("\nAnalyzing opportunities...")
    analyzed_leads = score_leads_batch(leads)
    
    # Get summary
    summary = get_scoring_summary(analyzed_leads)
    
    # Display summary
    logger.info("\n" + "=" * 60)
    logger.info("OPPORTUNITY INTELLIGENCE SUMMARY")
    logger.info("=" * 60)
    
    logger.info(f"\nPriority Breakdown:")
    logger.info(f"   High:   {summary['priority']['high']} ({summary['priority']['high_pct']}%)")
    logger.info(f"   Medium: {summary['priority']['medium']} ({summary['priority']['medium_pct']}%)")
    logger.info(f"   Low:    {summary['priority']['low']} ({summary['priority']['low_pct']}%)")
    
    logger.info(f"\nOpportunity Distribution:")
    logger.info(f"   Avg per lead: {summary['opportunities']['avg_per_lead']}")
    for opp_type, count in summary['opportunities']['by_type'].items():
        pct = round(count / len(analyzed_leads) * 100, 1)
        logger.info(f"   {opp_type}: {count} ({pct}%)")
    
    logger.info(f"\nConfidence:")
    logger.info(f"   Average: {summary['confidence']['avg']}")
    logger.info(f"   Range: {summary['confidence']['min']} - {summary['confidence']['max']}")
    
    logger.info(f"\nInternal Score (for sorting):")
    logger.info(f"   Average: {summary['score']['avg']}")
    logger.info(f"   Range: {summary['score']['min']} - {summary['score']['max']}")
    
    # Save results
    output_path = save_analyzed_leads(analyzed_leads)
    
    # Show top high-priority leads
    logger.info("\n" + "=" * 60)
    logger.info("TOP 5 HIGH-PRIORITY LEADS")
    logger.info("=" * 60)
    
    high_priority = [l for l in analyzed_leads if l.get("priority") == "High"]
    high_priority.sort(key=lambda x: x.get("lead_score", 0), reverse=True)
    
    for i, lead in enumerate(high_priority[:5], 1):
        logger.info(f"\n{i}. {lead.get('name', 'Unknown')}")
        logger.info(f"   Priority: {lead.get('priority')} | Score: {lead.get('lead_score')} | Confidence: {lead.get('confidence')}")
        logger.info(f"   Phone: {lead.get('signal_phone_number', 'N/A')}")
        
        opps = lead.get("opportunities", [])
        if opps:
            logger.info(f"   Opportunities ({len(opps)}):")
            for opp in opps:
                logger.info(f"     [{opp['strength']}] {opp['type']}")
                for ev in opp.get("evidence", [])[:2]:
                    logger.info(f"       - {ev}")
    
    logger.info(f"\nComplete! Results saved to: {output_path}")


if __name__ == "__main__":
    main()
