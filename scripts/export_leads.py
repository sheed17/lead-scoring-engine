#!/usr/bin/env python3
"""
Export scored/enriched leads to clean, shareable formats.

Outputs:
- JSON (clean, minimal fields)
- CSV (spreadsheet-ready)

Usage:
    python scripts/export_leads.py
    python scripts/export_leads.py --format csv
    python scripts/export_leads.py --format json
"""

import os
import sys
import json
import csv
import glob
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_latest_file(input_dir: str = "output") -> str:
    """Find the most recent scored or enriched leads JSON file."""
    # Try scored first, then enriched
    for pattern_prefix in ["scored_leads_", "enriched_leads_"]:
        pattern = os.path.join(input_dir, f"{pattern_prefix}*.json")
        files = glob.glob(pattern)
        if files:
            files.sort(key=os.path.getmtime, reverse=True)
            return files[0]
    
    raise FileNotFoundError("No scored or enriched files found in output/")


def load_leads(filepath: str) -> list:
    """Load leads from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, dict) and "leads" in data:
        return data["leads"]
    return data


def clean_lead_for_export(lead: dict) -> dict:
    """
    Extract clean, shareable fields from a lead.
    
    Returns only the fields that matter for outreach.
    """
    # Format reasons as a single string for CSV compatibility
    reasons = lead.get("reasons", [])
    reasons_str = "; ".join(reasons) if reasons else None
    
    # Extract review summary
    review_summary = lead.get("review_summary", {})
    
    return {
        # Scoring (if available)
        "lead_score": lead.get("lead_score"),
        "priority": lead.get("priority"),
        "confidence": lead.get("confidence"),
        "reasons": reasons_str,
        
        # Review context (agency-friendly)
        "review_volume": review_summary.get("volume"),
        "review_freshness": review_summary.get("freshness"),
        "last_review": review_summary.get("last_review_text"),
        
        # Business Info
        "name": lead.get("name"),
        "address": lead.get("address"),
        "phone": lead.get("signal_phone_number"),
        "website": lead.get("signal_website_url"),
        "email": lead.get("signal_email_address"),
        
        # Ratings
        "rating": lead.get("signal_rating") or lead.get("rating"),
        "review_count": lead.get("signal_review_count") or lead.get("user_ratings_total"),
        "days_since_review": lead.get("signal_last_review_days_ago"),
        
        # Signals (for prioritization)
        "has_phone": lead.get("signal_has_phone"),
        "has_website": lead.get("signal_has_website"),
        "has_contact_form": lead.get("signal_has_contact_form"),
        "has_email": lead.get("signal_has_email"),
        "has_automated_scheduling": lead.get("signal_has_automated_scheduling"),
        "has_trust_badges": lead.get("signal_has_trust_badges"),
        "mobile_friendly": lead.get("signal_mobile_friendly"),
        
        # Location
        "latitude": lead.get("latitude"),
        "longitude": lead.get("longitude"),
        
        # ID (for deduplication)
        "place_id": lead.get("place_id"),
    }


def export_to_json(leads: list, output_path: str):
    """Export leads to clean JSON file."""
    clean_leads = [clean_lead_for_export(lead) for lead in leads]
    
    # Sort by score if available
    if clean_leads and clean_leads[0].get("lead_score") is not None:
        clean_leads.sort(key=lambda x: x.get("lead_score") or 0, reverse=True)
    
    output_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "total_leads": len(clean_leads),
        "leads": clean_leads
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Exported {len(clean_leads)} leads to: {output_path}")
    return output_path


def export_to_csv(leads: list, output_path: str):
    """Export leads to CSV file (spreadsheet-ready)."""
    clean_leads = [clean_lead_for_export(lead) for lead in leads]
    
    # Sort by score if available
    if clean_leads and clean_leads[0].get("lead_score") is not None:
        clean_leads.sort(key=lambda x: x.get("lead_score") or 0, reverse=True)
    
    if not clean_leads:
        print("No leads to export")
        return None
    
    # Get field names from first lead
    fieldnames = list(clean_leads[0].keys())
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_leads)
    
    print(f"✓ Exported {len(clean_leads)} leads to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Export leads to shareable formats")
    parser.add_argument(
        "--format", "-f",
        choices=["json", "csv", "both"],
        default="both",
        help="Export format (default: both)"
    )
    parser.add_argument(
        "--input", "-i",
        help="Input file (default: latest scored/enriched file)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output filename prefix (default: leads_export)"
    )
    
    args = parser.parse_args()
    
    # Find input file
    if args.input:
        input_file = args.input
    else:
        input_file = find_latest_file()
    
    print(f"Loading from: {input_file}")
    leads = load_leads(input_file)
    print(f"Found {len(leads)} leads")
    
    # Check if scored
    if leads and leads[0].get("lead_score") is not None:
        print("✓ Leads are scored - will sort by score")
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = args.output or "leads_export"
    
    os.makedirs("output", exist_ok=True)
    
    # Export
    if args.format in ["json", "both"]:
        json_path = f"output/{prefix}_{timestamp}.json"
        export_to_json(leads, json_path)
    
    if args.format in ["csv", "both"]:
        csv_path = f"output/{prefix}_{timestamp}.csv"
        export_to_csv(leads, csv_path)
    
    print("\n✓ Export complete!")


if __name__ == "__main__":
    main()
