# Lead Scoring Engine

An intelligence platform that extracts, enriches, and analyzes business leads from Google Places—built for the dental vertical and production deployment.

We decide which businesses are worth pursuing and explain why. The system delivers **context over scores**: reasoning, dimensions, outreach angles, and evidence so sales teams can act with confidence.

---

## What We Built

### End-to-end pipeline
- **Extraction** — Geographic tiling, keyword expansion, and pagination to collect leads from Google Places Nearby Search
- **Enrichment** — Place Details, website signals, Meta Ads detection, and competitor sampling
- **Intelligence** — Objective decision layer, revenue modeling, and deterministic context for each lead

### Dental vertical
The system is specialized for dental practices. For each lead we produce:

- **Objective Intelligence** — Root constraint, primary growth vector, service gaps (high-ticket detected vs missing landing pages), competitive profile (market density, review tier, nearest competitors)
- **Revenue Intelligence Brief** — Executive diagnosis, market position, demand signals (Google Ads, Meta Ads), high-value service gaps, modeled revenue upside, strategic gap analysis, conversion infrastructure, risk flags, and intervention plan
- **Opportunity Profile** — Deterministic label (High-Leverage | Moderate | Low-Leverage) with short parenthetical reasoning

### Signals and context
- Website: SSL, mobile-friendly, contact forms, booking widgets, schema markup
- Reviews: Count, rating, recency, velocity
- Paid demand: Google Ads and Meta Ads presence (no spend estimates; factual status only)
- Service depth: High-ticket procedures detected, missing dedicated pages, schema coverage

### Outcome loop
- **Embeddings** — Structural snapshot per lead (objective state) stored in SQLite for similarity search
- **Lead outcomes** — Contacted, proposal sent, closed, close value, service sold
- **Similarity stats** — Conversion rates and top service sold across similar historical profiles (used for UI and future analytics)

---

## Architecture

| Component | Description |
|-----------|-------------|
| **Extraction** | `run_pipeline.py` — Grid-based Nearby Search with keyword expansion |
| **Enrichment** | `run_enrichment.py` — Place Details, signals, Meta Ads, competitors, embeddings |
| **Upload** | `run_upload.py` — Enrich uploaded leads (CSV/JSON) through the same pipeline |
| **Export** | `export_leads.py` — Context-first or legacy export from DB |
| **Briefs** | `render_brief.py` — Revenue Intelligence Brief HTML per lead |
| **Outcomes** | `update_outcome.py` — Create/update outcome records for the loop |
| **API** | FastAPI backend — `POST /diagnostic` for single-lead enrichment |

### Run the API server

From the project root:

```bash
uvicorn backend.main:app --reload
```

- Health check: `GET /health`
- Diagnostic: `POST /diagnostic` with body `{"business_name": "Example Dental", "city": "San Jose"}` (website optional)

### Run the frontend (Next.js)

From the project root, start the API first, then:

```bash
cd frontend
cp .env.local.example .env.local   # optional: edit NEXT_PUBLIC_API_URL if backend runs elsewhere
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The UI shows API status and a diagnostic form (business name, city, optional website) and displays the structured result.

### Database
- SQLite: runs, leads, signals, decisions, embeddings (versioned), outcomes
- Tables: `runs`, `leads`, `lead_signals`, `decisions`, `lead_embeddings_v2`, `lead_outcomes`

### Key modules
- **Objective intelligence** — Root bottleneck, growth vector, service intel, competitive profile
- **Revenue brief renderer** — Deterministic HTML and view model (no LLM in brief)
- **Embedding snapshot** — Structural text for embeddings (objective state)
- **Outcome stats** — Similarity-based conversion metrics

---

## Revenue Intelligence Brief

Each dental lead gets a Revenue Intelligence Brief that includes:

- **Executive Diagnosis** — Constraint, primary leverage, opportunity profile, modeled revenue upside
- **Market Position** — Revenue band, reviews, local avg, market density
- **Competitive Context** — Dentists sampled, lead vs market, nearest competitors
- **Demand Signals** — Google Ads status (Search campaigns detected / Not detected), Meta Ads (Active / Not detected), estimated traffic, last review, review velocity
- **Local SEO & High-Value Service Pages** — Detected services, missing pages, schema
- **Modeled Revenue Upside** — Primary service capture gap (conservative bands, 30% cap vs revenue band)
- **Strategic Gap** — Nearest competitor, capture gap narrative
- **Conversion Infrastructure** — Online booking, contact form, phone, mobile
- **Risk Flags** — Cost leakage and agency-fit risks
- **Intervention Plan** — 3-step plan; Step 3 dynamically calibrated by paid demand status

---

## Production Readiness

The core logic is complete and stable. The system:

- Uses deterministic classification (no invented numbers, no probabilities in briefs)
- Stores embeddings for similarity and outcome analytics
- Supports outcome tracking and similar-lead conversion stats
- Handles missing data gracefully (omits sections when data is absent)
- Works for dental leads; non-dental paths remain intact

Next phase: backend API, UI, and production database deployment.

---

## Project Structure

```
lead-scoring-engine/
├── pipeline/
│   ├── db.py                    # Persistence (runs, leads, signals, embeddings, outcomes)
│   ├── revenue_brief_renderer.py
│   ├── objective_intelligence.py
│   ├── objective_decision_layer.py
│   ├── revenue_intelligence.py
│   ├── embedding_snapshot.py
│   ├── competitor_sampling.py
│   ├── dentist_profile.py
│   ├── fetch.py, enrich.py, signals.py
│   └── ...
├── scripts/
│   ├── run_pipeline.py
│   ├── run_enrichment.py
│   ├── run_upload.py
│   ├── export_leads.py
│   ├── render_brief.py
│   ├── update_outcome.py
│   ├── list_runs.py
│   └── test_small.py
├── data/                        # SQLite DB
└── output/                      # Leads, enriched JSON, briefs
```

---

## License

MIT
