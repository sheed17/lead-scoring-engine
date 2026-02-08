# Examples & What Happens Internally

This doc shows **what you see** when each part of the system runs correctly, and **what is happening under the hood**.

---

## 1. After `run_pipeline.py` — Raw leads file

**Command:** `python scripts/run_pipeline.py`

**What you see:** A file like `output/leads_20260125_143022.json`:

```json
{
  "metadata": { "total": 45, "city": "San Jose", ... },
  "leads": [
    {
      "place_id": "ChIJVVUheWLMj4ARMsnv7MIFzRo",
      "name": "CaliforniAir Heating and Air Conditioning",
      "address": "627 N 20th St, San Jose",
      "latitude": 37.3564256,
      "longitude": -121.8803424,
      "rating": 5,
      "user_ratings_total": 31,
      "business_status": "OPERATIONAL"
    }
  ]
}
```

**What’s happening internally:**

- **Fetch:** Google Places Nearby Search runs for your city + niche (e.g. HVAC). The geo grid splits the area into tiles; each tile gets a search (with optional keyword expansion and pagination).
- **Normalize:** Each result is turned into a flat lead (name, address, place_id, rating, etc.). Duplicates are dropped by `place_id`.
- **Output:** Only the fields needed for the next step are written. No website, phone, or reviews yet — those come from Place Details in enrichment.

---

## 2. During `run_enrichment.py` — Console and DB

**Command:** `python scripts/run_enrichment.py` (or `--max-leads 5` for a short run)

**What you see in the console:**

```
============================================================
Lead Enrichment & Signal Extraction Pipeline
============================================================
Loading leads from: output/leads_20260125_143022.json
Loaded 45 leads
Step 1: Fetching Place Details (website, phone, reviews)...
Place Details API calls: 45
Step 2: Extracting signals (website analysis, phone, reviews)...
  Context + DB: 10/45 leads
  Context + DB: 20/45 leads
  ...
Run a1b2c3d4... completed; 45 leads persisted to DB
============================================================
SIGNAL EXTRACTION SUMMARY (HVAC Model + Tri-State)
============================================================
Total leads processed: 45
  Has phone: 42 (93.3%)
  Contact Form: ✓ 28  ✗ 5  ? 12
  ...
Saved enriched leads to: output/enriched_leads_20260125_144531.json
```

**What’s happening internally:**

1. **Load leads** from the latest `output/leads_*.json`.
2. **Place Details** (enrich): For each lead, one API call fetches website URL, phone, and up to 5 reviews. Results are stored in the lead as `_place_details`. Field selection is minimal to reduce cost.
3. **Extract signals:** For each lead:
   - Phone is normalized from Place Details (e.g. to E.164).
   - If there’s a website, **one HTTP GET** is done (no browser). From the HTML we derive: SSL, viewport (mobile-friendly), contact form (patterns + CTA text), email, scheduling widgets, trust badges, paid-ad patterns, hiring text, schema/microdata, social links, phone/address on page. Each signal is **tri-state**: `true`, `false`, or `null` (unknown).
   - Review stats come from Place Details (count, rating, last review date); we compute velocity and rating delta from the sample.
4. **Context (deterministic):** For each lead we run `build_context(merged_lead)`:
   - Six dimensions (Paid Growth, Hiring & Timing, Reviews & Reputation, Website & Funnel, Operational Maturity, Reachability) get a **status** (Strong/Moderate/Weak/Unknown), **evidence** list, and **confidence** from the signals.
   - We compute `reasoning_summary`, `priority_suggestion`, `priority_derivation`, `primary_themes`, `suggested_outreach_angles`, and, when applicable, `no_opportunity` + `no_opportunity_reason`.
5. **Optional RAG:** If `--llm-reasoning` is set, we embed this context text, look up similar past leads in the DB (cosine similarity), and pass those snippets into the LLM so it can refine the summary and angles.
6. **Optional LLM:** If `--llm-reasoning` is set, the LLM returns refined `reasoning_summary`, `primary_themes`, and `suggested_outreach_angles` (dimensions and evidence are not changed).
7. **Validation:** We run `check_lead_signals` and `check_context`; any warnings are stored as `validation_warnings` on the lead.
8. **DB:** For the run we insert: one row in `runs`, then per lead: `leads`, `lead_signals`, `context_dimensions` (including no_opportunity, priority_derivation, validation_warnings). If embeddings are available, we store them in `lead_embeddings` for future RAG.
9. **Run stats:** After the loop we compute counts (e.g. has_website_true, has_contact_form_unknown, signal_coverage_pct) and save them in `runs.run_stats`.
10. **Enriched JSON:** The same merged leads (with all signal_* and context fields) are written to `output/enriched_leads_*.json` for backward compatibility.

---

## 3. After `export_leads.py` — Context-first export (default from DB)

**Command:** `python scripts/export_leads.py`

**What you see:** Files like `output/context_export_20260125_150000.json` and `.csv`.

**Example JSON lead (one object from the `leads` array):**

```json
{
  "place_id": "ChIJ-6wnrZWgYIMRi5WtnYs2_2w",
  "name": "Ice Heating And Cooling",
  "address": "500 Race St, San Jose",
  "context_dimensions": [
    {
      "dimension": "Paid Growth",
      "status": "Weak",
      "evidence": ["No paid ads detected"],
      "confidence": 0.7
    },
    {
      "dimension": "Website & Funnel",
      "status": "Moderate",
      "evidence": ["Has website", "Website accessible", "No automated scheduling"],
      "confidence": 0.8
    },
    {
      "dimension": "Reachability",
      "status": "Strong",
      "evidence": ["Phone available", "Email visible", "Contact form available"],
      "confidence": 0.85
    }
  ],
  "reasoning_summary": "Website & Funnel: Moderate. Has website, Website accessible, No automated scheduling. Reachability: Strong. Phone available, Email visible.",
  "priority_suggestion": "Medium",
  "priority_derivation": "Priority Medium: Reachability, Website & Funnel",
  "primary_themes": ["Operational efficiency", "General outreach"],
  "suggested_outreach_angles": [
    "Introduce scheduling and form capture to reduce manual work",
    "Multiple contact channels — good candidate for outreach"
  ],
  "confidence": 0.85,
  "reasoning_source": "deterministic",
  "no_opportunity": false,
  "no_opportunity_reason": null,
  "validation_warnings": [],
  "raw_signals": {
    "has_website": true,
    "website_accessible": true,
    "has_contact_form": true,
    "has_phone": true,
    "has_email": true,
    "has_automated_scheduling": false,
    "review_count": 19,
    "rating": 5
  }
}
```

**What’s happening internally:**

- **Source:** The script calls `get_latest_run_id()` (latest **completed** run), then `get_leads_with_context_by_run(run_id)` to read leads joined with signals and context from SQLite.
- **Shape:** Each lead is the context-first shape: dimensions, reasoning, priority, themes, angles, confidence, optional no_opportunity/validation_warnings, and raw_signals. Failed runs are not considered “latest,” so export always reflects a completed run.
- **Sort:** Leads are ordered by confidence (highest first) in the JSON.
- **CSV:** Same data, flattened (e.g. primary_themes and suggested_outreach_angles as single columns); nested objects like `context_dimensions` and `raw_signals` are summarized or omitted for CSV.

---

## 4. Example of a “no opportunity” lead (dead-end filter)

When a lead has **enough signal coverage** but **no strong or moderate dimension** (all Weak or Unknown), we mark it as no-opportunity so you can filter it out.

**What you see in export:**

```json
{
  "place_id": "ChIJ...",
  "name": "Very Polished HVAC Co",
  "context_dimensions": [
    { "dimension": "Paid Growth", "status": "Weak", "evidence": ["No paid ads detected"], "confidence": 0.7 },
    { "dimension": "Website & Funnel", "status": "Weak", "evidence": ["Has website", "Website accessible"], "confidence": 0.8 },
    { "dimension": "Reachability", "status": "Strong", "evidence": ["Phone available", "Contact form available"], "confidence": 0.85 }
  ],
  "reasoning_summary": "...",
  "priority_suggestion": "Low",
  "priority_derivation": "Priority Low: limited strong/moderate dimensions",
  "no_opportunity": false,
  "no_opportunity_reason": null
}
```

If **all** dimensions were Weak/Unknown and confidence was e.g. 0.6:

```json
"no_opportunity": true,
"no_opportunity_reason": "No clear gap or opportunity; dimensions are Weak or Unknown despite sufficient data."
```

**What’s happening internally:** In `build_context`, after we have the six dimension statuses and overall confidence, we set `no_opportunity = (confidence >= 0.5 and every status in ("Weak", "Unknown"))`. That flag is stored in `context_dimensions` and included in export so you can filter to “only leads with an opportunity.”

---

## 5. Example of validation warnings

When signals are inconsistent (e.g. no website but “website accessible”), we don’t fail; we attach warnings.

**What you see in export:**

```json
{
  "name": "Some Business",
  "validation_warnings": [
    "has_website=false but website_accessible=true (impossible)"
  ],
  "context_dimensions": [ ... ]
}
```

**What’s happening internally:** After `build_context`, we run `check_lead_signals(signal)` and `check_context(context)`. Their return values are concatenated and stored as `validation_warnings` on the context and in the DB. Export includes them so you can review or fix upstream data.

---

## 6. `list_runs.py` — Runs and run stats

**Command:** `python scripts/list_runs.py`

**What you see:**

```
Runs (db: data/opportunity_intelligence.db)

  a1b2c3d4...  2026-01-25T14:45:31.123456  45  completed  coverage=82.2%
  f5e6d7c8...  2026-01-24T10:00:00.000000  120 completed  coverage=79.1%
```

**What’s happening internally:**

- **DB:** We open the same SQLite DB used by enrichment (`data/opportunity_intelligence.db` or `OPPORTUNITY_DB_PATH`). We query `runs` ordered by `created_at` DESC.
- **run_stats:** For completed runs, we stored a JSON blob in `runs.run_stats` with counts (e.g. has_website_true, has_contact_form_unknown) and `signal_coverage_pct`. The script prints `coverage=X%` when that key exists so you can see “how good” the run’s signal coverage was.

---

## 7. Re-enrichment with `--place-ids`

**Command:** `python scripts/run_enrichment.py --place-ids output/my_place_ids.txt`

**File `output/my_place_ids.txt` (one place_id per line):**

```
ChIJVVUheWLMj4ARMsnv7MIFzRo
ChIJ-6wnrZWgYIMRi5WtnYs2_2w
```

**What you see:**

```
Loading leads from: output/leads_20260125_143022.json
Loaded 45 leads
Filtered to 2 leads (place_ids file: output/my_place_ids.txt, had 45)
Step 1: Fetching Place Details ...
```

**What’s happening internally:** We load the full leads file, then filter to leads whose `place_id` is in the set we read from the file (one per line or a JSON array). Only those leads go through Place Details, signal extraction, context, DB write, and embeddings. So you re-run the full pipeline for a subset (e.g. to refresh data or re-run with `--llm-reasoning`).

---

## 8. Export with `--dedupe-by-place-id`

**Command:** `python scripts/export_leads.py --dedupe-by-place-id`

**What you see:**

```
Loading from DB (deduped by place_id, latest run wins)...
Found 42 unique leads (context-first export)
```

**What’s happening internally:** We call `get_leads_with_context_deduped_by_place_id(limit_runs=20)`: load the latest 20 completed runs, fetch all leads for each run (newest runs first), and keep one lead per `place_id` (first occurrence wins, so the **latest run** that contained that place_id wins). So if the same business appeared in run A and run B, you only see the version from the more recent run. Export then writes that list in the same context-first shape as usual.

---

## 9. Legacy export (from file)

**Command:** `python scripts/export_leads.py --export-legacy`

**What you see:** A file like `output/leads_export_20260125_150500.json` with the **old** shape: `opportunities`, `priority`, `lead_score`, `reasons`, `review_summary`, and signal_* fields — i.e. the format that existed before the context-first pipeline.

**What’s happening internally:** We **do not** read from the DB. We use the latest scored or enriched **file** from `output/` (e.g. `enriched_leads_*.json` or `scored_leads_*.json`), load its `leads` array, and export that as-is (or with the legacy CSV flattening). So legacy export is file-based and independent of runs/context_dimensions.

---

## 10. End-to-end flow summary

| Step | You run | You see | Internal behavior |
|------|--------|--------|--------------------|
| 1 | `run_pipeline.py` | `output/leads_*.json` | Fetch places by geo + niche, normalize, dedupe by place_id. |
| 2 | `run_enrichment.py` | Console logs + `output/enriched_leads_*.json` + DB | Place Details → one GET per site → signals (tri-state) → build_context (6 dimensions, reasoning, no_opportunity, priority_derivation) → optional RAG + LLM → validation → insert into runs/leads/lead_signals/context_dimensions/lead_embeddings, run_stats. |
| 3 | `export_leads.py` | `output/context_export_*.json` + `.csv` | Read latest completed run from DB, output context-first shape (dimensions, reasoning, themes, angles, no_opportunity, validation_warnings). |
| 4 | `list_runs.py` | List of runs + coverage % | Read runs from DB, print run_stats.signal_coverage_pct when present. |
| 5 | `export_leads.py --dedupe-by-place-id` | One lead per place_id | Load multiple runs, keep latest per place_id, same context-first export. |
| 6 | `run_enrichment.py --place-ids file` | Fewer leads processed | Filter input leads to place_ids in file, then same pipeline. |

When everything works as intended, you get: **sourced leads** (1), **analyzed and contextualized** with explainable dimensions and optional LLM/RAG (2), **persisted** with run stats and validation (2), and **exported** either context-first from DB (3) or legacy from file (9), with optional dedupe (8) and re-enrichment (7).
