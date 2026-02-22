"""
Load and normalize team-uploaded leads (CSV or JSON) for enrichment.

Uploaded leads may have: name (required), website, phone, address, place_id.
- With place_id: we fetch Place Details (Google API) and get website, phone, reviews.
- Without place_id: we use the provided website/phone and set synthetic _place_details
  so the rest of the pipeline (signals, Meta Ads, scoring, context) runs unchanged.
"""

import csv
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# CSV column name variants we accept (first is canonical)
NAME_KEYS = ["name", "business_name", "company", "business name"]
WEBSITE_KEYS = ["website", "url", "website_url", "site"]
PHONE_KEYS = ["phone", "phone_number", "tel", "telephone", "formatted_phone_number"]
ADDRESS_KEYS = ["address", "formatted_address", "street", "address_line"]
PLACE_ID_KEYS = ["place_id", "place id", "google_place_id"]


def _normalize_key(row: Dict, keys: List[str]) -> Optional[str]:
    """Return value for first matching key (case-insensitive)."""
    for k in keys:
        for rk, v in row.items():
            if rk and rk.strip().lower() == k.lower():
                if v is not None and str(v).strip():
                    return str(v).strip()
                return None
    return None


def _first_line(path: str) -> List[str]:
    """Read first line of CSV to get headers."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        return next(reader, [])


def normalize_uploaded_row(row: Dict) -> Dict:
    """
    Normalize a single uploaded row to a lead-like dict.

    Expected keys (or variants): name, website, phone, address, place_id.
    Returns dict with: name, place_id (optional), website, formatted_phone_number,
    formatted_address. Name is required; others may be None.
    """
    if isinstance(row, list):
        return {}
    if not isinstance(row, dict):
        row = {"name": str(row)}

    name = _normalize_key(row, NAME_KEYS) or (row.get("name") if isinstance(row.get("name"), str) else None)
    if not name or not name.strip():
        return {}

    lead = {
        "name": name.strip(),
        "place_id": _normalize_key(row, PLACE_ID_KEYS) or row.get("place_id"),
        "website": _normalize_key(row, WEBSITE_KEYS) or row.get("website"),
        "formatted_address": _normalize_key(row, ADDRESS_KEYS) or row.get("address") or row.get("formatted_address"),
    }
    phone = _normalize_key(row, PHONE_KEYS) or row.get("phone")
    lead["formatted_phone_number"] = phone
    lead["international_phone_number"] = None  # optional later
    return lead


def build_synthetic_place_details(lead: Dict) -> Dict:
    """
    Build _place_details from uploaded lead fields when place_id is missing.

    Allows extract_signals to run: website analysis, phone, and empty reviews.
    """
    return {
        "website": lead.get("website"),
        "formatted_phone_number": lead.get("formatted_phone_number"),
        "international_phone_number": lead.get("international_phone_number"),
        "reviews": [],
        "google_maps_url": None,
    }


def load_uploaded_csv(path: str) -> List[Dict]:
    """
    Load leads from a CSV file.

    First row = headers. Columns matched case-insensitively to name, website,
    phone, address, place_id (and common variants).
    """
    leads = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lead = normalize_uploaded_row(row)
            if lead:
                leads.append(lead)
    logger.info("Loaded %d rows from CSV %s", len(leads), path)
    return leads


def load_uploaded_json(path: str) -> List[Dict]:
    """
    Load leads from a JSON file.

    Accepts: array of objects, or object with "leads" key.
    Each object normalized with normalize_uploaded_row.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict) and "leads" in data:
        rows = data["leads"]
    elif isinstance(data, dict):
        rows = [data]
    else:
        raise ValueError(f"JSON must be array or {{'leads': [...]}} in {path}")
    leads = []
    for row in rows:
        lead = normalize_uploaded_row(row)
        if lead:
            leads.append(lead)
    logger.info("Loaded %d leads from JSON %s", len(leads), path)
    return leads


def load_uploaded_leads(path: str) -> List[Dict]:
    """
    Load uploaded leads from CSV or JSON (by extension).

    Returns list of normalized lead dicts (name required; website, phone, address, place_id optional).
    """
    path_lower = path.lower()
    if path_lower.endswith(".csv"):
        return load_uploaded_csv(path)
    if path_lower.endswith(".json"):
        return load_uploaded_json(path)
    raise ValueError(f"Unsupported format: {path}. Use .csv or .json")
