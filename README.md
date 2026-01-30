# Lead Scoring Engine

A Python-based Google Places lead extraction and enrichment system that reliably collects and analyzes hundreds to thousands of business leads for a given niche and city.

## Pipeline Overview

| Step | Script | Description |
|------|--------|-------------|
| 1-3 | `run_pipeline.py` | Extract leads via Nearby Search |
| 4 | `run_enrichment.py` | Enrich with Place Details + signals |
| 5 | TBD | Score and rank leads |

## Features

### Lead Extraction (Steps 1-3)
- **Geographic Tiling**: Grid-based search for complete city coverage
- **Keyword Expansion**: Multiple search terms per niche
- **Pagination**: Up to 60 results per query
- **Deduplication**: Removes duplicates using `place_id`

### Signal Extraction (Step 4)
- **Place Details Enrichment**: Website, phone, reviews
- **Website Signals**: SSL, mobile-friendly, contact forms, booking widgets
- **Phone Normalization**: International format standardization
- **Review Analysis**: Recency, count, rating

### Cost Optimization
- **Field Selection**: Only request needed Place Details fields (53% savings)
- **Rate Limiting**: Prevents wasted failed calls
- **Batch Processing**: Efficient API usage

## Quick Start

### 1. Set up environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_PLACES_API_KEY="your-api-key"
```

### 2. Extract leads

```bash
python scripts/run_pipeline.py
```

### 3. Enrich with signals

```bash
python scripts/run_enrichment.py
```

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
```

### Enrichment (`scripts/run_enrichment.py`)

```python
CONFIG = {
    "input_dir": "output",
    "output_dir": "output", 
    "max_leads": None,  # Set number for testing
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
├── main.py                      # Entry point
├── test_places.py               # Test Nearby Search API
├── test_enrichment.py           # Test Place Details API
├── requirements.txt
├── pipeline/
│   ├── __init__.py
│   ├── geo.py                   # Geographic grid generation
│   ├── fetch.py                 # Nearby Search API client
│   ├── normalize.py             # Data normalization
│   ├── enrich.py                # Place Details API client
│   ├── signals.py               # Signal extraction
│   ├── export.py                # Export utilities
│   └── score.py                 # Lead scoring (Step 5)
├── scripts/
│   ├── run_pipeline.py          # Steps 1-3: Extraction
│   └── run_enrichment.py        # Step 4: Enrichment
└── output/
    ├── leads_*.json             # Raw extracted leads
    └── enriched_leads_*.json    # Leads with signals
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

| Signal | Type | Description |
|--------|------|-------------|
| `signal_has_website` | bool | Has a website |
| `signal_website_url` | string | Full URL |
| `signal_domain` | string | Normalized domain |
| `signal_has_ssl` | bool | Uses HTTPS |
| `signal_mobile_friendly` | bool | Has viewport meta tag |
| `signal_has_contact_form` | bool | Form detected |
| `signal_has_booking` | bool | Booking widget detected |
| `signal_page_load_time_ms` | int | Response time |
| `signal_has_phone` | bool | Has phone number |
| `signal_phone_number` | string | International format |
| `signal_rating` | float | Google rating |
| `signal_review_count` | int | Total reviews |
| `signal_last_review_days_ago` | int | Days since last review |

## Booking Widgets Detected

- Calendly
- Setmore
- Square Appointments
- Acuity Scheduling
- Booksy
- Vagaro
- Schedulicity
- HouseCall Pro
- Jobber
- ServiceTitan

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

## License

MIT
