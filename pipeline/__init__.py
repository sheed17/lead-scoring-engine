"""
Lead Scoring Engine - Pipeline Package

This package provides a complete pipeline for extracting, normalizing,
enriching, and exporting business leads from Google Places API.

Modules:
    geo: Geographic grid generation for comprehensive coverage
    fetch: Google Places Nearby Search API client with rate limiting
    normalize: Data normalization and deduplication
    enrich: Google Places Details API for additional data
    signals: Website and business signal extraction
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
from .enrich import PlaceDetailsEnricher
from .signals import (
    extract_signals,
    extract_signals_batch,
    merge_signals_into_lead,
    normalize_domain,
    normalize_phone,
    analyze_website
)
from .export import export_to_json, export_to_csv, to_db_records
from .score import score_lead, score_leads_batch, get_scoring_summary, ScoringResult

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
    # enrich
    "PlaceDetailsEnricher",
    # signals
    "extract_signals",
    "extract_signals_batch",
    "merge_signals_into_lead",
    "normalize_domain",
    "normalize_phone",
    "analyze_website",
    # export
    "export_to_json",
    "export_to_csv",
    "to_db_records",
    # score
    "score_lead",
    "score_leads_batch",
    "get_scoring_summary",
    "ScoringResult",
]
