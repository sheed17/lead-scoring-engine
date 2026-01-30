"""
Export module for saving leads to various formats.

Supports JSON, CSV, and prepares data for database insertion.
"""

import os
import csv
import json
from typing import List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def export_to_json(
    places: List[Dict],
    filepath: str,
    include_metadata: bool = True,
    metadata: Dict = None
) -> str:
    """
    Export places to JSON file.
    
    Args:
        places: List of place dictionaries
        filepath: Output file path
        include_metadata: Whether to wrap data with metadata
        metadata: Additional metadata to include
    
    Returns:
        Path to saved file
    """
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    
    if include_metadata:
        output_data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "total_records": len(places),
                **(metadata or {})
            },
            "leads": places
        }
    else:
        output_data = places
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Exported {len(places)} leads to JSON: {filepath}")
    return filepath


def export_to_csv(
    places: List[Dict],
    filepath: str,
    fields: List[str] = None
) -> str:
    """
    Export places to CSV file.
    
    Args:
        places: List of place dictionaries
        filepath: Output file path
        fields: List of fields to include (default: all common fields)
    
    Returns:
        Path to saved file
    """
    if not places:
        logger.warning("No places to export")
        return filepath
    
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    
    # Default fields for CSV export
    if fields is None:
        fields = [
            "place_id",
            "name",
            "address",
            "latitude",
            "longitude",
            "rating",
            "user_ratings_total",
            "business_status",
            "types",
            "fetched_at"
        ]
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        
        for place in places:
            # Convert list fields to strings
            row = place.copy()
            if 'types' in row and isinstance(row['types'], list):
                row['types'] = '|'.join(row['types'])
            writer.writerow(row)
    
    logger.info(f"Exported {len(places)} leads to CSV: {filepath}")
    return filepath


def to_db_records(places: List[Dict]) -> List[Dict]:
    """
    Transform places to database-ready records.
    
    Ensures all fields are properly typed for DB insertion.
    Flattens nested structures and handles null values.
    
    Args:
        places: List of normalized place dictionaries
    
    Returns:
        List of database-ready dictionaries
    """
    records = []
    
    for place in places:
        record = {
            "place_id": place.get("place_id"),
            "name": place.get("name"),
            "address": place.get("address"),
            "latitude": float(place["latitude"]) if place.get("latitude") else None,
            "longitude": float(place["longitude"]) if place.get("longitude") else None,
            "rating": float(place["rating"]) if place.get("rating") else None,
            "review_count": int(place.get("user_ratings_total", 0)),
            "business_status": place.get("business_status"),
            "is_open": place.get("is_open_now"),
            "price_level": place.get("price_level"),
            "types": place.get("types", []),  # Keep as list for array column or JSON
            "photo_reference": place.get("photo_reference"),
            "photo_count": int(place.get("photo_count", 0)),
            "source": place.get("source", "google_places"),
            "fetched_at": place.get("fetched_at"),
            "created_at": datetime.utcnow().isoformat()
        }
        records.append(record)
    
    return records


def generate_sql_insert(
    places: List[Dict],
    table_name: str = "leads"
) -> str:
    """
    Generate SQL INSERT statements for places.
    
    Useful for manual database imports or debugging.
    
    Args:
        places: List of normalized place dictionaries
        table_name: Target table name
    
    Returns:
        SQL INSERT statement string
    """
    if not places:
        return ""
    
    records = to_db_records(places)
    
    # Get columns from first record
    columns = list(records[0].keys())
    columns_str = ", ".join(columns)
    
    values_list = []
    for record in records:
        values = []
        for col in columns:
            val = record[col]
            if val is None:
                values.append("NULL")
            elif isinstance(val, (list, dict)):
                # JSON encode arrays/objects
                values.append(f"'{json.dumps(val)}'")
            elif isinstance(val, bool):
                values.append("TRUE" if val else "FALSE")
            elif isinstance(val, (int, float)):
                values.append(str(val))
            else:
                # Escape single quotes in strings
                escaped = str(val).replace("'", "''")
                values.append(f"'{escaped}'")
        
        values_list.append(f"({', '.join(values)})")
    
    sql = f"INSERT INTO {table_name} ({columns_str})\nVALUES\n"
    sql += ",\n".join(values_list)
    sql += ";"
    
    return sql
