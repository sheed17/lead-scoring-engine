# Lead Scoring Engine

A Python-based Google Places lead extraction agent that reliably collects hundreds to thousands of business leads for a given niche and city.

## Features

- **Geographic Tiling**: Grid-based search using lat/lng + radius for complete city coverage
- **Keyword Expansion**: Multiple search terms per niche for comprehensive results
- **Pagination**: Fetches all available pages per query (up to 60 results each)
- **Deduplication**: Removes duplicates using `place_id`
- **Rate Limiting**: Respects Google API limits with built-in delays and backoff
- **Error Handling**: Graceful retry/backoff on API errors
- **Multiple Export Formats**: JSON, CSV, and database-ready schemas

## Quick Start

### 1. Set up virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set your API key

```bash
export GOOGLE_PLACES_API_KEY="your-google-places-api-key"
```

### 3. Test API connection

```bash
python test_places.py
```

### 4. Run the full pipeline

```bash
python scripts/run_pipeline.py
```

## Configuration

Edit `scripts/run_pipeline.py` to customize:

```python
# City to search
CITY_CONFIG = {
    "name": "San Jose, CA",
    "center_lat": 37.3382,
    "center_lng": -121.8863,
    "radius_km": 15.0
}

# Search parameters
SEARCH_CONFIG = {
    "niche": "hvac",              # Business niche
    "search_radius_km": 2.0,      # Grid cell radius
    "max_pages_per_query": 3,     # Pagination depth (1-3)
    "use_keyword_expansion": True # Use multiple keywords
}
```

## Supported Niches

Built-in keyword expansion for:
- `hvac` - HVAC, heating and cooling, AC repair, etc.
- `plumber` - Plumber, plumbing contractor, drain cleaning, etc.
- `electrician` - Electrician, electrical contractor, etc.
- `roofing` - Roofing contractor, roof repair, etc.
- `landscaping` - Landscaping, lawn care, etc.
- `cleaning` - Cleaning service, house cleaning, etc.

## Project Structure

```
lead-scoring-engine/
├── main.py                    # Entry point
├── test_places.py             # API connection test
├── requirements.txt           # Dependencies
├── pipeline/
│   ├── __init__.py           # Package exports
│   ├── geo.py                # Geographic grid generation
│   ├── fetch.py              # Google Places API client
│   ├── normalize.py          # Data normalization
│   ├── export.py             # Export utilities
│   └── score.py              # Lead scoring (TBD)
├── scripts/
│   └── run_pipeline.py       # Main orchestration
└── output/                   # Generated lead files
```

## Output Schema

Each lead includes:

| Field | Type | Description |
|-------|------|-------------|
| `place_id` | string | Google Places unique ID |
| `name` | string | Business name |
| `address` | string | Street address |
| `latitude` | float | Location latitude |
| `longitude` | float | Location longitude |
| `rating` | float | Google rating (1-5) |
| `user_ratings_total` | int | Number of reviews |
| `business_status` | string | OPERATIONAL, CLOSED_*, etc. |
| `types` | array | Business type categories |
| `photo_reference` | string | Photo ID for retrieval |
| `fetched_at` | string | ISO timestamp |

## API Usage Estimation

Before running, estimate your API usage:

```python
from pipeline.geo import estimate_api_calls

estimate = estimate_api_calls(
    city_radius_km=15.0,
    search_radius_km=2.0,
    keywords_count=6,
    max_pages=3
)
print(estimate)
# {'grid_points': 177, 'keywords': 6, 'base_queries': 1062, 'max_api_calls': 3186, ...}
```

## License

MIT
