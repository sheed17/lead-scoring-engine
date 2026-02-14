"""
Opportunity Intelligence Engine - Pipeline Package

This package provides a complete pipeline for extracting, normalizing,
enriching, and analyzing business leads from Google Places API.

Architecture:
    geo: Geographic grid generation for comprehensive coverage
    fetch: Google Places Nearby Search API client with rate limiting
    normalize: Data normalization and deduplication
    enrich: Google Places Details API for additional data
    signals: Business signal extraction (website, ads, hiring, reviews)
    meta_ads: Meta Ads Library API (optional, META_ACCESS_TOKEN)
    semantic_signals: Deterministic mapping from raw signals to six axes (for Decision Agent)
    decision_agent: Decision Agent (single owner of judgment; verdict, reasoning, risks)
    context: Context-first deterministic interpreter (dimensions, reasoning); legacy
    db: SQLite persistence (runs, leads, signals, context_dimensions, decisions)
    opportunities: Opportunity intelligence builder (CORE, legacy)
    score: Prioritization helper (backward-compatible scoring)
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
from .meta_ads import get_meta_access_token, check_meta_ads, augment_lead_with_meta_ads
from .semantic_signals import build_semantic_signals
from .decision_agent import Decision, DecisionAgent
from .context import build_context, calculate_confidence
from .opportunities import (
    analyze_opportunities,
    analyze_opportunities_batch,
    get_opportunity_summary,
    Opportunity,
    OpportunityReport,
)
from .export import export_to_json, export_to_csv, to_db_records
from .score import score_lead, score_leads_batch, get_scoring_summary, ScoringResult
from .dentist_profile import is_dental_practice, build_dentist_profile_v1, fetch_website_html_for_trust
from .dentist_llm_reasoning import dentist_llm_reasoning_layer
from .sales_intervention import build_sales_intervention_intelligence
from .objective_decision_layer import compute_objective_decision_layer
from .revenue_intelligence import build_revenue_intelligence

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
    # meta_ads
    "get_meta_access_token",
    "check_meta_ads",
    "augment_lead_with_meta_ads",
    # semantic_signals (deterministic, for Decision Agent)
    "build_semantic_signals",
    # decision_agent (single owner of judgment; v1: no embeddings/RAG)
    "Decision",
    "DecisionAgent",
    # context (deterministic evidence summarizer; legacy)
    "build_context",
    "calculate_confidence",
    # opportunities (CORE)
    "analyze_opportunities",
    "analyze_opportunities_batch",
    "get_opportunity_summary",
    "Opportunity",
    "OpportunityReport",
    # score (backward-compatible prioritization)
    "score_lead",
    "score_leads_batch",
    "get_scoring_summary",
    "ScoringResult",
    # export
    "export_to_json",
    "export_to_csv",
    "to_db_records",
    # dentist vertical (dentist_profile_v1 + LLM reasoning layer)
    "is_dental_practice",
    "build_dentist_profile_v1",
    "fetch_website_html_for_trust",
    "dentist_llm_reasoning_layer",
    "build_sales_intervention_intelligence",
    "compute_objective_decision_layer",
    "build_revenue_intelligence",
]
