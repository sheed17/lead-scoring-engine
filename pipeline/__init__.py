"""
Lead Scoring Engine - Pipeline Package

This package provides a complete pipeline for extracting, normalizing,
and exporting business leads from Google Places API.

Modules:
    geo: Geographic grid generation for comprehensive coverage
    fetch: Google Places API client with rate limiting
    normalize: Data normalization and deduplication
    export: Export to JSON, CSV, and database formats
"""

from .geo import generate_geo_grid, estimate_api_calls
from .fetch import PlacesFetcher, get_keywords_for_niche
from .normalize import (
    normalize_place,
    normalize_places,
    deduplicate_places,
    filter_places,
    get_place_summary
)
from .export import export_to_json, export_to_csv, to_db_records

__all__ = [
    # geo
    "generate_geo_grid",
    "estimate_api_calls",
    # fetch
    "PlacesFetcher",
    "get_keywords_for_niche",
    # normalize
    "normalize_place",
    "normalize_places",
    "deduplicate_places",
    "filter_places",
    "get_place_summary",
    # export
    "export_to_json",
    "export_to_csv",
    "to_db_records",
]
