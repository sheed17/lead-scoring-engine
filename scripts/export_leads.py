#!/usr/bin/env python3
"""
Export analyzed leads to clean, shareable formats.

Default: read from SQLite (latest run), export decision-first shape
(verdict, reasoning, primary_risks, what_would_change, confidence, agency_type).

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

from pipeline.db import (
    get_latest_run_id,
    get_leads_with_context_by_run,
    get_leads_with_context_deduped_by_place_id,
    get_leads_with_decisions_by_run,
    get_leads_with_decisions_deduped_by_place_id,
)
from pipeline.sixty_second_summary import build_sixty_second_summary


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

def _ensure_sixty_second_summary(lead: dict) -> dict:
    """Get or compute sixty_second_summary for a lead."""
    if lead.get("sixty_second_summary"):
        return lead["sixty_second_summary"]
    return build_sixty_second_summary(lead)


def _clean_lead_decision_for_export(lead: dict, summary_only: bool = False) -> dict:
    """One row for decision-first export. summary_only=True: only name, address, sixty_second_summary."""
    summary = _ensure_sixty_second_summary(lead)
    score = summary.get("seo_priority_score", 50)

    if summary_only:
        return {
            "name": lead.get("name"),
            "address": lead.get("address"),
            "sixty_second_summary": summary,
        }
    # Ordered for 60-second usability: summary first, then verdict/confidence, then deep blocks
    out = {
        "name": lead.get("name"),
        "address": lead.get("address"),
        "sixty_second_summary": summary,
        "seo_priority_score": score,
        "verdict": lead.get("verdict"),
        "confidence": lead.get("confidence"),
        "reasoning": lead.get("reasoning", ""),
        "primary_risks": "; ".join(lead.get("primary_risks") or []),
        "what_would_change": "; ".join(lead.get("what_would_change") or []),
        "agency_type": lead.get("agency_type"),
        "prompt_version": lead.get("prompt_version"),
        "place_id": lead.get("place_id"),
        "raw_signals": lead.get("raw_signals", {}),
    }
    if lead.get("objective_decision_layer") is not None:
        out["objective_decision_layer"] = lead["objective_decision_layer"]
        out["root_bottleneck"] = (lead["objective_decision_layer"].get("root_bottleneck_classification") or {}).get("bottleneck", "")
        if lead["objective_decision_layer"].get("service_intelligence") is not None:
            out["service_intelligence"] = lead["objective_decision_layer"]["service_intelligence"]
        if lead["objective_decision_layer"].get("competitive_snapshot") is not None:
            out["competitive_snapshot"] = lead["objective_decision_layer"]["competitive_snapshot"]
    else:
        out["root_bottleneck"] = ""
    if lead.get("dentist_profile_v1") is not None:
        out["dentist_profile_v1"] = lead["dentist_profile_v1"]
    if lead.get("llm_reasoning_layer") is not None:
        out["llm_reasoning_layer"] = lead["llm_reasoning_layer"]
        out["llm_executive_summary"] = (lead["llm_reasoning_layer"].get("executive_summary") or "")[:500]
    else:
        out["llm_executive_summary"] = ""
    if lead.get("sales_intervention_intelligence") is not None:
        out["sales_intervention_intelligence"] = lead["sales_intervention_intelligence"]
        anchor = (lead["sales_intervention_intelligence"].get("primary_sales_anchor") or {}).get("issue")
        out["sales_primary_anchor"] = (anchor or "")[:200]
    else:
        out["sales_primary_anchor"] = ""
    return out


def _clean_lead_context_for_export(lead: dict) -> dict:
    """One row for context-first export (from get_leads_with_context_by_run); legacy."""
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


def export_context_to_json(leads: list, output_path: str, decision_first: bool = True, summary_only: bool = False):
    """Export leads to JSON. decision_first: verdict, reasoning, etc. summary_only: only name, address, sixty_second_summary."""
    clean = []
    for lead in leads:
        if decision_first and lead.get("verdict") is not None:
            row = _clean_lead_decision_for_export(lead, summary_only=summary_only)
            clean.append(row)
        else:
            clean.append({
                "place_id": lead.get("place_id"),
                "name": lead.get("name"),
                "address": lead.get("address"),
                "context_dimensions": lead.get("context_dimensions", []),
                "reasoning_summary": lead.get("reasoning_summary", ""),
                "priority_suggestion": lead.get("priority_suggestion"),
                "confidence": lead.get("confidence"),
                "raw_signals": lead.get("raw_signals", {}),
            })
    # Sort by sales priority (seo_priority_score) descending; fallback to confidence
    clean.sort(
        key=lambda x: (x.get("seo_priority_score") if "seo_priority_score" in x else x.get("sixty_second_summary", {}).get("seo_priority_score") if isinstance(x.get("sixty_second_summary"), dict) else x.get("confidence") or 0),
        reverse=True,
    )
    data = {"exported_at": datetime.utcnow().isoformat(), "total_leads": len(clean), "leads": clean}
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Exported {len(clean)} leads (decision-first{' summary-only' if summary_only else ''}) to: {output_path}")
    return output_path


def export_context_to_csv(leads: list, output_path: str, decision_first: bool = True, summary_only: bool = False):
    """Export leads to CSV (flattened). summary_only: name, address, sixty_second_summary (flattened)."""
    if decision_first and leads and leads[0].get("verdict") is not None:
        clean = [_clean_lead_decision_for_export(lead, summary_only=summary_only) for lead in leads]
        clean.sort(
            key=lambda x: (x.get("seo_priority_score") if "seo_priority_score" in x else x.get("sixty_second_summary", {}).get("seo_priority_score") if isinstance(x.get("sixty_second_summary"), dict) else 0),
            reverse=True,
        )
        if summary_only:
            # Flatten sixty_second_summary for CSV: prefix keys
            rows = []
            for r in clean:
                flat = {"name": r.get("name"), "address": r.get("address")}
                ss = r.get("sixty_second_summary") or {}
                for k, v in ss.items():
                    flat[f"sixty_second_summary.{k}"] = v
                rows.append(flat)
            clean = rows
            fieldnames = list(clean[0].keys()) if clean else []
        else:
            fieldnames = [k for k in clean[0].keys() if k not in ("raw_signals", "dentist_profile_v1", "llm_reasoning_layer", "sales_intervention_intelligence", "objective_decision_layer", "service_intelligence", "competitive_snapshot")]
    else:
        clean = [_clean_lead_context_for_export(lead) for lead in leads]
        fieldnames = [k for k in clean[0].keys() if k not in ("context_dimensions", "raw_signals")]
    if not clean:
        print("No leads to export")
        return None
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(clean)
    print(f"Exported {len(clean)} leads (decision-first{' summary-only' if summary_only else ''}) to: {output_path}")
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
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Export only name, address, and sixty_second_summary per lead (60-second view)"
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
        # Default: from DB, decision-first shape (verdict, reasoning, primary_risks, what_would_change)
        if args.dedupe_by_place_id:
            print("Loading from DB (deduped by place_id, latest run wins)...")
            leads = get_leads_with_decisions_deduped_by_place_id(limit_runs=20)
            print(f"Found {len(leads)} unique leads (decision-first export)")
        else:
            run_id = args.run_id or get_latest_run_id()
            if not run_id:
                print("No completed run in DB. Run enrichment first, or use --export-legacy with a file.")
                sys.exit(1)
            print(f"Loading from DB run: {run_id[:8]}...")
            leads = get_leads_with_decisions_by_run(run_id)
            print(f"Found {len(leads)} leads (decision-first export)")
        prefix = args.output or "context_export"
        decision_first = bool(leads and leads[0].get("verdict") is not None)
        summary_only = getattr(args, "summary_only", False)
        if args.format in ["json", "both"]:
            export_context_to_json(leads, f"output/{prefix}_{timestamp}.json", decision_first=decision_first, summary_only=summary_only)
        if args.format in ["csv", "both"]:
            export_context_to_csv(leads, f"output/{prefix}_{timestamp}.csv", decision_first=decision_first, summary_only=summary_only)
    
    print("\nExport complete!")


if __name__ == "__main__":
    main()
