# Lead Scoring Engine

A Python-based Google Places lead extraction and enrichment system that reliably collects and analyzes hundreds to thousands of business leads for a given niche and city.

## Pipeline Overview

| Step | Script | Description |
|------|--------|-------------|
| 1–3 | `run_pipeline.py` | Extract leads via Nearby Search (grid + keyword expansion) |
| 4 | `run_enrichment.py` | Enrich with Place Details, signals, Meta Ads (optional), scoring & context; writes to SQLite |
| 5 | `export_leads.py` | Export context-first (from DB) or legacy (from file) |
| — | `list_runs.py` | List runs, prune by retention |
| — | `test_small.py` | Quick end-to-end test (3 leads, ~$0.06; optional Meta Ads when token set) |
| — | `run_upload.py` | Enrich **uploaded** leads (CSV/JSON): same signals, Meta Ads, scoring, DB; teams can run their existing lists through the pipeline |

## Features

### Lead Extraction (Steps 1-3)
- **Geographic Tiling**: Grid-based search for complete city coverage
- **Keyword Expansion**: Multiple search terms per niche
- **Pagination**: Up to 60 results per query
- **Deduplication**: Removes duplicates using `place_id`

### Signal Extraction & Scoring (Step 4)
- **Place Details Enrichment**: Website, phone, reviews
- **Website Signals**: SSL, mobile-friendly, contact forms, booking widgets, LinkedIn company URL
- **Phone Normalization**: International format standardization
- **Review Analysis**: Recency, count, rating; optional review summary and themes (LLM or keyword fallback)
- **Meta Ads Library** (optional): When `META_ACCESS_TOKEN` is set, checks whether the business runs Meta ads; augments `signal_runs_paid_ads` / `signal_paid_ads_channels`
- **Scoring & Context**: Six dimensions, priority, confidence, opportunities; optional LLM refinement and RAG (`--llm-reasoning`)

### Cost Optimization
- **Field Selection**: Only request needed Place Details fields (53% savings)
- **Rate Limiting**: Prevents wasted failed calls
- **Batch Processing**: Efficient API usage

For **concrete examples** of what you see at each step (raw leads, enrichment console/DB, context-first export, list_runs, re-enrichment, dedupe) and **what happens internally**, see **[docs/EXAMPLES_AND_INTERNALS.md](docs/EXAMPLES_AND_INTERNALS.md)**.

## MVP Checklist

**On your end**
- [ ] Set `GOOGLE_PLACES_API_KEY` (required for fetch + enrich).
- [ ] (Optional) Set `OPENAI_API_KEY` for LLM refinement and RAG; set `META_ACCESS_TOKEN` for Meta Ads Library (regenerate at developers.facebook.com if you see "Invalid OAuth access token").
- [ ] Run in order: **run_pipeline** → **run_enrichment** → **export_leads**. Export reads from DB by default.

**Already done (codebase)**
- Context-first pipeline (6 dimensions, reasoning, optional LLM + RAG).
- SQLite persistence (runs, leads, signals, context, embeddings).
- Export: context-first (default from DB) or legacy (from file with `--export-legacy`).
- DB maintenance: `list_runs.py` to list runs and prune by retention.
- Run failure handling: failed runs are marked in DB so they don’t appear as “latest” for export.

## Quick Start

### 1. Set up environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_PLACES_API_KEY="your-api-key"
# Optional: for Meta Ads Library augmentation
export META_ACCESS_TOKEN="your-meta-token"
# Optional: for LLM refinement and RAG (run_enrichment.py --llm-reasoning)
export OPENAI_API_KEY="your-openai-key"
```

### 2. (Optional) Run a quick test

```bash
python scripts/test_small.py
```

Runs the full pipeline on 3 leads (~$0.06). Uses Meta Ads when `META_ACCESS_TOKEN` is set. Output: `output/test_small_results.json`.

### 3. Extract leads

```bash
python scripts/run_pipeline.py
```

### 4. Enrich with signals (writes to DB + optional enriched JSON)

```bash
python scripts/run_enrichment.py
# Optional: --llm-reasoning (needs OPENAI_API_KEY), --max-leads N, --input path/to/leads.json
```

Enrichment includes Place Details, website signals, review context, optional Meta Ads check, scoring, and context (6 dimensions). Results are stored in SQLite; optional enriched JSON in `output/`.

### 5. Export leads (default: context-first from DB)

```bash
python scripts/export_leads.py
# Legacy shape from file: python scripts/export_leads.py --export-legacy
# Dedupe by place_id: python scripts/export_leads.py --dedupe-by-place-id
```

### 6. (Optional) Upload existing leads

Teams can run the same enrichment (signals, Meta Ads, scoring, context) on their own lists:

```bash
python scripts/run_upload.py --upload path/to/leads.csv
# Or JSON: python scripts/run_upload.py --upload path/to/leads.json
# Limit and LLM: python scripts/run_upload.py --upload leads.csv --max-leads 100 --llm-reasoning
# No Google API: python scripts/run_upload.py --upload leads.csv --no-place-details
```

**Upload format:** CSV or JSON. Required column: **name**. Optional: **website**, **phone**, **address**, **place_id** (and common variants like `business_name`, `url`, `phone_number`). Rows with a Google **place_id** get Place Details (website, phone, reviews) from the API; rows without use the website/phone you provide and skip reviews. Results go to the same DB and appear in `export_leads` and `list_runs` (runs tagged `source: upload`).

## Cost Analysis

### Nearby Search (Steps 1-3)
| Metric | Value |
|--------|-------|
| Cost per 1,000 calls | $32.00 |
| Results per call | Up to 60 (with pagination) |
| Effective cost per lead | ~$0.06 |

### Place Details (Step 4)
| Approach | Cost per 1,000 |
|----------|----------------|
| All fields | $17.00 |
| **Our approach** (selected fields) | **$8.00** |
| Savings | **53%** |

### Total Pipeline Cost Example
For 200 leads in San Jose:
- Nearby Search: ~$12.80
- Place Details: ~$1.60
- **Total: ~$14.40** ($0.07 per enriched lead)

## Configuration

### Lead Extraction (`scripts/run_pipeline.py`)

```python
CITY_CONFIG = {
    "name": "San Jose, CA",
    "center_lat": 37.3382,
    "center_lng": -121.8863,
    "radius_km": 15.0
}

SEARCH_CONFIG = {
    "niche": "hvac",
    "search_radius_km": 2.0,
    "max_pages_per_query": 3,
    "use_keyword_expansion": True
}

OUTPUT_CONFIG = {
    "output_dir": "output",
    "filename_prefix": "leads"
}
```

### Enrichment (`scripts/run_enrichment.py`)

```python
CONFIG = {
    "input_dir": "output",
    "output_dir": "output",
    "max_leads": None,   # None = all leads, or set a number for testing
    "progress_interval": 10,
    "llm_reasoning": False,  # Set via --llm-reasoning for LLM refinement + RAG
}
```

## Supported Niches

Built-in keyword expansion:
- `hvac` - HVAC, heating and cooling, AC repair, etc.
- `plumber` - Plumber, plumbing contractor, drain cleaning
- `electrician` - Electrician, electrical contractor
- `roofing` - Roofing contractor, roof repair
- `landscaping` - Landscaping, lawn care
- `cleaning` - Cleaning service, house cleaning

## Project Structure

```
lead-scoring-engine/
├── main.py
├── requirements.txt
├── test_places.py               # Test Nearby Search API
├── test_enrichment.py           # Test Place Details API
├── test_website_signals.py      # Test website signal extraction
├── docs/
│   └── EXAMPLES_AND_INTERNALS.md
├── pipeline/
│   ├── __init__.py
│   ├── geo.py                   # Geographic grid generation
│   ├── fetch.py                 # Nearby Search API client
│   ├── normalize.py             # Normalization & deduplication
│   ├── enrich.py                # Place Details API client
│   ├── signals.py               # Website & business signal extraction
│   ├── review_context.py        # Review summary & themes (LLM or keyword)
│   ├── meta_ads.py              # Meta Ads Library (optional, META_ACCESS_TOKEN)
│   ├── upload.py                # Load & normalize uploaded leads (CSV/JSON)
│   ├── context.py              # Context-first interpreter (6 dimensions)
│   ├── opportunities.py        # Opportunity intelligence
│   ├── score.py                 # Lead scoring & priority
│   ├── llm_reasoning.py         # Optional LLM refinement (--llm-reasoning)
│   ├── embeddings.py            # Embeddings for RAG
│   ├── db.py                    # SQLite persistence (runs, leads, context)
│   ├── validation.py            # Validation warnings
│   └── export.py                # Export utilities
├── scripts/
│   ├── run_pipeline.py          # Steps 1–3: Extraction
│   ├── run_enrichment.py        # Step 4: Enrichment (signals, Meta Ads, scoring, DB)
│   ├── export_leads.py          # Step 5: Context-first or legacy export
│   ├── list_runs.py             # List runs, prune by retention
│   ├── run_upload.py            # Enrich uploaded leads (CSV/JSON)
│   ├── test_small.py            # Quick E2E test (3 leads)
│   ├── run_scoring.py           # Standalone scoring
│   └── test_scoring.py          # Scoring tests
└── output/
    ├── leads_*.json             # Raw extracted leads
    ├── enriched_leads_*.json    # Enriched leads (optional from run_enrichment)
    └── test_small_results.json  # Output from test_small.py
```

## Output Schemas

### Raw Lead (Steps 1-3)

| Field | Type | Description |
|-------|------|-------------|
| `place_id` | string | Google Places unique ID |
| `name` | string | Business name |
| `address` | string | Street address |
| `latitude` | float | Location |
| `longitude` | float | Location |
| `rating` | float | Google rating (1-5) |
| `user_ratings_total` | int | Review count |
| `business_status` | string | OPERATIONAL, CLOSED_*, etc. |

### Enriched Lead Signals (Step 4)

**HVAC Signal Model:** Phone is the PRIMARY booking mechanism. Automated scheduling indicates operational maturity, not booking capability.

| Signal | Type | Description |
|--------|------|-------------|
| `signal_has_phone` | bool | **PRIMARY booking signal** |
| `signal_phone_number` | string | International format |
| `signal_has_website` | bool | Has a website |
| `signal_website_url` | string | Full URL |
| `signal_domain` | string | Normalized domain |
| `signal_has_ssl` | bool | Uses HTTPS |
| `signal_mobile_friendly` | bool | Has viewport meta tag |
| `signal_has_contact_form` | bool | Inbound lead readiness |
| `signal_has_automated_scheduling` | bool | Ops maturity (see below) |
| `signal_page_load_time_ms` | int | Response time |
| `signal_rating` | float | Google rating |
| `signal_review_count` | int | Total reviews |
| `signal_last_review_days_ago` | int | Days since last review |
| `signal_has_schema_microdata` | bool | Organization/LocalBusiness in ld+json or microdata |
| `signal_schema_types` | list | e.g. `["Organization", "LocalBusiness"]` |
| `signal_has_social_links` | bool | Social profile links on website (Phase 0.1) |
| `signal_social_platforms` | list | e.g. `["facebook", "instagram", "yelp"]` |
| `signal_has_phone_in_html` | bool | Phone number or tel: link on page |
| `signal_has_address_in_html` | bool | Street address or schema on page |
| `signal_linkedin_company_url` | string | LinkedIn company page URL (when found on website) |
| `signal_review_summary_text` | string | Summary of review text (LLM or keyword fallback) |
| `signal_review_themes` | list | Themes from reviews (e.g. quality, service, timeliness) |
| `signal_review_sample_snippets` | list | Short snippets from first few reviews |
| `signal_runs_paid_ads` | bool | True when Meta Ads Library returns ads (optional; requires `META_ACCESS_TOKEN`) |
| `signal_paid_ads_channels` | list | e.g. `["meta"]` when Meta ads found; from website pixel or Meta Ads Library |
| `signal_meta_ads_source` | string | `"meta_ads_library"` when augmented via Meta Ads API |
| `signal_meta_ads_count` | int | Number of ads returned by Meta Ads Library for this business |

### Phase 2: RAG (similar past summaries)
With `--llm-reasoning`, the pipeline embeds each lead’s context (reasoning + dimensions) and stores it in SQLite. On later runs, the LLM step retrieves similar past summaries and uses them to refine reasoning and outreach angles. Requires `OPENAI_API_KEY`; optional `OPENAI_EMBEDDING_MODEL` (default `text-embedding-3-small`).

### Additions (logic & data)
- **Configurable dimension weights** – `context.DIMENSION_PRIORITY_WEIGHTS` controls how each dimension contributes to priority (defaults in code).
- **No-opportunity flag** – When all dimensions are Weak/Unknown and confidence ≥ 0.5, context includes `no_opportunity: true` and `no_opportunity_reason` (filter dead ends in export).
- **Priority derivation** – Context includes `priority_derivation` (e.g. "Priority High: Paid Growth, Website & Funnel") for debuggability.
- **Run stats** – Each completed run stores `run_stats` (e.g. has_website_true, signal_coverage_pct); visible in `list_runs.py` and `get_run()`.
- **Validation warnings** – Signals and context are checked for impossible combos; warnings stored per lead and in export (`validation_warnings`).
- **Re-enrichment** – `run_enrichment.py --place-ids path/to/ids.txt` only enriches leads whose `place_id` is in the file (one per line or JSON array).
- **Export dedupe** – `export_leads.py --dedupe-by-place-id` exports one lead per place_id (latest run wins) for context-first export.

### DB maintenance (list & prune runs)
```bash
python scripts/list_runs.py                    # list recent runs
python scripts/list_runs.py --prune-keep 5     # keep last 5 completed runs, delete rest
python scripts/list_runs.py --prune-older-than 30   # delete runs older than 30 days
python scripts/list_runs.py --prune-keep 3 --dry-run # show what would be deleted
```

## HVAC Signal Interpretation

```
IF has_phone AND review_count > 5:
    lead_status = "Active HVAC business"

IF has_contact_form:
    inbound_ready = true

IF has_automated_scheduling:
    ops_type = "Automated"      # Mature ops, possibly agency-saturated
ELSE:
    ops_type = "Manual"         # Higher optimization opportunity
```

**Key Insight:** Lack of automated scheduling ≠ weak lead. It indicates manual operations and higher opportunity for optimization services.

## Automated Scheduling Systems Detected

Field Service Management (HVAC-specific):
- ServiceTitan
- HouseCall Pro
- Jobber
- FieldEdge
- SuccessWare

General Scheduling:
- Calendly
- Acuity Scheduling
- Square Appointments
- Setmore
- Schedulicity

## API Usage Estimation

```python
from pipeline.geo import estimate_api_calls

# Estimate extraction cost
estimate = estimate_api_calls(
    city_radius_km=15.0,
    search_radius_km=2.0,
    keywords_count=6,
    max_pages=3
)
print(f"Max API calls: {estimate['max_api_calls']}")

# Enrichment cost = leads × $0.008
enrichment_cost = 200 * 0.008  # $1.60 for 200 leads
```

## Next steps & roadmap to production

### 1. Enable OpenAI (one key for everything)

A single **`OPENAI_API_KEY`** is used for:

| Use | When | Optional env |
|-----|------|---------------|
| **Embeddings** | Stored when you run enrichment with `--llm-reasoning`; used for RAG (similar past leads) | `OPENAI_EMBEDDING_MODEL` (default: `text-embedding-3-small`) |
| **LLM reasoning** | Refines reasoning summary, themes, and outreach angles | `OPENAI_MODEL` (default: `gpt-4o-mini`) |
| **Review context** | LLM-generated review summary and themes (when key is set) | Same `OPENAI_MODEL` in `review_context` |

**Do this:**

1. Create an API key at [platform.openai.com](https://platform.openai.com/api-keys).
2. Set it in your environment: `export OPENAI_API_KEY="sk-..."`.
3. Run enrichment with LLM and RAG:  
   `python scripts/run_enrichment.py --llm-reasoning`  
   Embeddings are stored in SQLite automatically; future runs will use them for similar-lead retrieval.

No code changes required; the pipeline already checks for the key and falls back to deterministic output when it’s missing.

### 2. Roadmap to production

| Step | What to do |
|------|------------|
| **Secrets** | Never commit keys. Use env vars in production (e.g. your host’s “environment” or “secrets”). Optionally use a `.env` file loaded by your process (keep `.env` in `.gitignore`). |
| **Run strategy** | Run **run_pipeline** periodically (e.g. cron weekly) to refresh leads; then **run_enrichment** (with or without `--llm-reasoning`) to fill the DB. **export_leads** (or your own consumer) reads from the DB. |
| **Database** | SQLite file lives in `output/` by default. For production: (1) Put the DB path on a durable volume, (2) Back it up regularly (e.g. cron copy or snapshot), (3) Use `list_runs.py --prune-*` to control retention. |
| **Scale** | For large lead counts, use `--max-leads` in batches or split input files. Rate limiting and field selection are already in place to reduce API cost. |
| **Monitoring** | Logs go to stdout; capture them in your host/container. Optionally add health checks (e.g. “DB exists and is writable”, “last run completed”). |
| **Deployment** | Run on a VM, container (Docker), or serverless (e.g. scheduled Lambda/Cloud Run) that runs the three scripts in order. No built-in HTTP API; export outputs (JSON/CSV) or point your app at the SQLite DB. |

**Minimal production loop:**

1. **run_pipeline.py** → produces `output/leads_*.json`
2. **run_enrichment.py** (optionally `--llm-reasoning`) → reads latest leads, writes to SQLite
3. **export_leads.py** or your own code → reads from DB for downstream use (CRM, sheets, API, etc.)

## License

MIT
