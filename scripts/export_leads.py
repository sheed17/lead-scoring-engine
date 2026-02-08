#!/usr/bin/env python3
"""
Export analyzed leads to clean, shareable formats.

Default: read from SQLite (latest run), export context-first shape
(context_dimensions, reasoning_summary, themes, outreach_angles, confidence).

With --export_legacy: read from latest scored/enriched JSON file, export
legacy shape (opportunities, priority, lead_score, reasons).

Usage:
    python scripts/export_leads.py
    python scripts/export_leads.py --run-id <uuid>
    python scripts/export_leads.py --export-legacy --input output/enriched_leads_*.json
    python scripts/export_leads.py --format csv
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

from pipeline.db import get_latest_run_id, get_leads_with_context_by_run, get_leads_with_context_deduped_by_place_id


def find_latest_file(input_dir: str = "output") -> str:
    """Find the most recent scored or enriched leads JSON file."""
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


def _format_opportunities_text(opps: list) -> str:
    """Format opportunities as a readable string for CSV."""
    if not opps:
        return ""
    
    parts = []
    for opp in opps:
        strength = opp.get("strength", "")
        opp_type = opp.get("type", "")
        timing = opp.get("timing", "")
        parts.append(f"[{strength}] {opp_type} ({timing})")
    
    return "; ".join(parts)


def _format_evidence_text(opps: list) -> str:
    """Format all opportunity evidence as a readable string."""
    if not opps:
        return ""
    
    evidence = []
    for opp in opps:
        for ev in opp.get("evidence", []):
            evidence.append(ev)
    
    return "; ".join(evidence)


def clean_lead_for_export(lead: dict) -> dict:
    """
    Extract clean, shareable fields from a lead.
    
    Opportunities are surfaced FIRST. Scores exist for sorting only.
    """
    # Extract review summary
    review_summary = lead.get("review_summary", {})
    
    # Extract opportunities
    opps = lead.get("opportunities", [])
    
    # Primary opportunity info
    top_opp = opps[0] if opps else {}
    
    return {
        # --- OPPORTUNITY INTELLIGENCE (PRIMARY) ---
        "priority": lead.get("priority"),
        "top_opportunity": top_opp.get("type"),
        "top_opportunity_strength": top_opp.get("strength"),
        "top_opportunity_timing": top_opp.get("timing"),
        "opportunities_summary": _format_opportunities_text(opps),
        "evidence": _format_evidence_text(opps),
        "confidence": lead.get("confidence"),
        "num_opportunities": len(opps),
        
        # --- BUSINESS INFO ---
        "name": lead.get("name"),
        "address": lead.get("address"),
        "phone": lead.get("signal_phone_number"),
        "website": lead.get("signal_website_url"),
        "email": lead.get("signal_email_address"),
        
        # --- REVIEW CONTEXT ---
        "rating": lead.get("signal_rating") or lead.get("rating"),
        "review_count": lead.get("signal_review_count") or lead.get("user_ratings_total"),
        "review_volume": review_summary.get("volume"),
        "review_freshness": review_summary.get("freshness"),
        "last_review": review_summary.get("last_review_text"),
        
        # --- SIGNALS ---
        "has_phone": lead.get("signal_has_phone"),
        "has_website": lead.get("signal_has_website"),
        "has_contact_form": lead.get("signal_has_contact_form"),
        "has_email": lead.get("signal_has_email"),
        "has_automated_scheduling": lead.get("signal_has_automated_scheduling"),
        "runs_paid_ads": lead.get("signal_runs_paid_ads"),
        "hiring_active": lead.get("signal_hiring_active"),
        "mobile_friendly": lead.get("signal_mobile_friendly"),
        
        # --- INTERNAL (for sorting) ---
        "lead_score": lead.get("lead_score"),
        
        # --- LOCATION ---
        "latitude": lead.get("latitude"),
        "longitude": lead.get("longitude"),
        
        # --- ID ---
        "place_id": lead.get("place_id"),
    }


def clean_lead_for_json_export(lead: dict) -> dict:
    """
    Export lead for JSON - includes full opportunity objects.
    """
    review_summary = lead.get("review_summary", {})
    
    return {
        # --- OPPORTUNITY INTELLIGENCE (PRIMARY) ---
        "priority": lead.get("priority"),
        "confidence": lead.get("confidence"),
        "opportunities": lead.get("opportunities", []),
        
        # --- BUSINESS INFO ---
        "name": lead.get("name"),
        "address": lead.get("address"),
        "phone": lead.get("signal_phone_number"),
        "website": lead.get("signal_website_url"),
        "email": lead.get("signal_email_address"),
        
        # --- REVIEW CONTEXT ---
        "rating": lead.get("signal_rating") or lead.get("rating"),
        "review_count": lead.get("signal_review_count") or lead.get("user_ratings_total"),
        "review_summary": review_summary,
        
        # --- SIGNALS ---
        "has_phone": lead.get("signal_has_phone"),
        "has_website": lead.get("signal_has_website"),
        "has_contact_form": lead.get("signal_has_contact_form"),
        "has_email": lead.get("signal_has_email"),
        "has_automated_scheduling": lead.get("signal_has_automated_scheduling"),
        "runs_paid_ads": lead.get("signal_runs_paid_ads"),
        "hiring_active": lead.get("signal_hiring_active"),
        "mobile_friendly": lead.get("signal_mobile_friendly"),
        
        # --- INTERNAL (for sorting) ---
        "lead_score": lead.get("lead_score"),
        
        # --- LOCATION ---
        "latitude": lead.get("latitude"),
        "longitude": lead.get("longitude"),
        "place_id": lead.get("place_id"),
    }


def export_to_json(leads: list, output_path: str):
    """Export leads to clean JSON file (opportunities-first)."""
    clean_leads = [clean_lead_for_json_export(lead) for lead in leads]
    
    # Sort by score for ordering
    clean_leads.sort(key=lambda x: x.get("lead_score") or 0, reverse=True)
    
    output_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "total_leads": len(clean_leads),
        "leads": clean_leads
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Exported {len(clean_leads)} leads to: {output_path}")
    return output_path


def export_to_csv(leads: list, output_path: str):
    """Export leads to CSV file (spreadsheet-ready, flattened)."""
    clean_leads = [clean_lead_for_export(lead) for lead in leads]
    
    # Sort by score for ordering
    clean_leads.sort(key=lambda x: x.get("lead_score") or 0, reverse=True)
    
    if not clean_leads:
        print("No leads to export")
        return None
    
    fieldnames = list(clean_leads[0].keys())
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_leads)
    
    print(f"Exported {len(clean_leads)} leads to: {output_path}")
    return output_path


# =============================================================================
# CONTEXT-FIRST EXPORT (default, from DB)
# =============================================================================

def _clean_lead_context_for_export(lead: dict) -> dict:
    """One row for context-first export (from get_leads_with_context_by_run)."""
    dims_text = "; ".join(
        f"{d.get('dimension', '')}: {d.get('status', '')}"
        for d in lead.get("context_dimensions", [])
    )
    out = {
        "place_id": lead.get("place_id"),
        "name": lead.get("name"),
        "address": lead.get("address"),
        "reasoning_summary": lead.get("reasoning_summary", ""),
        "priority_suggestion": lead.get("priority_suggestion"),
        "priority_derivation": lead.get("priority_derivation"),
        "primary_themes": ", ".join(lead.get("primary_themes") or []),
        "suggested_outreach_angles": "; ".join(lead.get("suggested_outreach_angles") or []),
        "confidence": lead.get("confidence"),
        "reasoning_source": lead.get("reasoning_source"),
        "no_opportunity": lead.get("no_opportunity"),
        "no_opportunity_reason": lead.get("no_opportunity_reason"),
        "context_dimensions_summary": dims_text,
        "context_dimensions": lead.get("context_dimensions", []),
        "raw_signals": lead.get("raw_signals", {}),
    }
    if lead.get("validation_warnings"):
        out["validation_warnings"] = "; ".join(lead["validation_warnings"])
    return out


def export_context_to_json(leads: list, output_path: str):
    """Export context-first leads to JSON (full structure)."""
    clean = []
    for lead in leads:
        clean.append({
            "place_id": lead.get("place_id"),
            "name": lead.get("name"),
            "address": lead.get("address"),
            "context_dimensions": lead.get("context_dimensions", []),
            "reasoning_summary": lead.get("reasoning_summary", ""),
            "priority_suggestion": lead.get("priority_suggestion"),
            "priority_derivation": lead.get("priority_derivation"),
            "primary_themes": lead.get("primary_themes", []),
            "suggested_outreach_angles": lead.get("suggested_outreach_angles", []),
            "confidence": lead.get("confidence"),
            "reasoning_source": lead.get("reasoning_source"),
            "no_opportunity": lead.get("no_opportunity"),
            "no_opportunity_reason": lead.get("no_opportunity_reason"),
            "validation_warnings": lead.get("validation_warnings", []),
            "raw_signals": lead.get("raw_signals", {}),
        })
    clean.sort(key=lambda x: (x.get("confidence") or 0), reverse=True)
    data = {"exported_at": datetime.utcnow().isoformat(), "total_leads": len(clean), "leads": clean}
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Exported {len(clean)} leads (context-first) to: {output_path}")
    return output_path


def export_context_to_csv(leads: list, output_path: str):
    """Export context-first leads to CSV (flattened)."""
    clean = [_clean_lead_context_for_export(lead) for lead in leads]
    if not clean:
        print("No leads to export")
        return None
    # Drop complex nested fields for CSV
    fieldnames = [k for k in clean[0].keys() if k not in ("context_dimensions", "raw_signals")]
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(clean)
    print(f"Exported {len(clean)} leads (context-first) to: {output_path}")
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
        help="Input file (for --export_legacy: default latest scored/enriched file)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output filename prefix (default: leads_export or context_export)"
    )
    parser.add_argument(
        "--run-id",
        help="DB run ID to export (default: latest completed run)"
    )
    parser.add_argument(
        "--export-legacy",
        action="store_true",
        help="Export legacy shape from file (opportunities, priority, lead_score)"
    )
    parser.add_argument(
        "--dedupe-by-place-id",
        action="store_true",
        help="Export one lead per place_id (latest run wins); use with context-first export"
    )
    
    args = parser.parse_args()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("output", exist_ok=True)
    
    if args.export_legacy:
        # Legacy: from file, old shape
        input_file = args.input or find_latest_file()
        print(f"Loading from file: {input_file}")
        leads = load_leads(input_file)
        print(f"Found {len(leads)} leads (legacy export)")
        prefix = args.output or "leads_export"
        if args.format in ["json", "both"]:
            export_to_json(leads, f"output/{prefix}_{timestamp}.json")
        if args.format in ["csv", "both"]:
            export_to_csv(leads, f"output/{prefix}_{timestamp}.csv")
    else:
        # Default: from DB, context-first shape
        if args.dedupe_by_place_id:
            print("Loading from DB (deduped by place_id, latest run wins)...")
            leads = get_leads_with_context_deduped_by_place_id(limit_runs=20)
            print(f"Found {len(leads)} unique leads (context-first export)")
        else:
            run_id = args.run_id or get_latest_run_id()
            if not run_id:
                print("No completed run in DB. Run enrichment first, or use --export-legacy with a file.")
                sys.exit(1)
            print(f"Loading from DB run: {run_id[:8]}...")
            leads = get_leads_with_context_by_run(run_id)
            print(f"Found {len(leads)} leads (context-first export)")
        prefix = args.output or "context_export"
        if args.format in ["json", "both"]:
            export_context_to_json(leads, f"output/{prefix}_{timestamp}.json")
        if args.format in ["csv", "both"]:
            export_context_to_csv(leads, f"output/{prefix}_{timestamp}.csv")
    
    print("\nExport complete!")


if __name__ == "__main__":
    main()
