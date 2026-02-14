# 60-Second SEO Insight — Current State & Proposed Structure

## 1. How we capture hiring signals today

**Source:** One page only — the **website homepage** (the same URL we fetch for contact form, booking, SSL, etc.). We do **not** crawl `/careers` or `/jobs` separately.

**Location:** `pipeline/signals.py` → `analyze_website()` → `_extract_content_signals()`.

**Logic:**

| Signal | How it's set |
|--------|----------------|
| **hiring_active** | Tri-state: `true` = evidence found, `false` = page loaded and no evidence, `null` = no page / no substantial HTML. |
| **hiring_roles** | If hiring_active is true, we run role regexes on the same HTML; roles are from a fixed set: `technician`, `front_desk`, `marketing`, `sales`, `management`. |

**Evidence we use:**

- **Links:** Any `href` matching `/careers`, `/jobs`, `/hiring`, `/join-us`, `/work-with-us`, `/employment`, `/openings`, or links to indeed.com, glassdoor.com, linkedin.com/company/.../jobs.
- **Text (regex on full HTML):** “we’re hiring”, “now hiring”, “join our team”, “career opportunities”, “open positions”, “job openings”, “apply now/today/here”, “looking for a technician/installer/…”, “hiring a/an …”, “positions available”, “employment opportunities”.
- **Roles:** Regex patterns for HVAC/service technician, installer, front desk, receptionist, marketing, sales, estimator, manager, etc.

**Stored on lead:** `signal_hiring_active` (bool or null), `signal_hiring_roles` (list of strings or null). Exported in context/decision export as `hiring_active` / `hiring_roles`.

**Limitation:** If the practice only has hiring on a dedicated `/careers` page and the homepage has no link/text, we will set `hiring_active = false` (or null if homepage failed). We never fetch a second URL for hiring.

---

## 2. What 30–60 minutes of manual SEO research usually is

Rough breakdown of what a rep does by hand:

| Step | Typical manual work | Time |
|------|----------------------|-----|
| **Discover** | Find local businesses (maps, search, lists). | 5–15 min |
| **GBP + reviews** | Check rating, review count, recency, reply behavior. | 2–5 min |
| **Website** | Does it exist? SSL? Mobile? Contact form? Booking? | 3–8 min |
| **Services** | What do they offer? Implants, cosmetic, emergency? Dedicated pages or one generic page? | 5–15 min |
| **Competitors** | Who’s nearby? How do reviews/visibility compare? | 5–15 min |
| **Decision** | Worth calling? What’s the one thing to lead with? What’s the first action? | 5–10 min |
| **Prioritization** | Which leads to call first (list order). | 2–5 min |

Total: ~30–60 min per lead if done thoroughly; in practice reps shortcut and miss things.

---

## 3. What we already do (mapping to “60 seconds”)

| Manual step | Our system | Where it lives |
|-------------|------------|----------------|
| Discover | Nearby Search + Place Details | fetch, enrich |
| GBP + reviews | rating, review_count, last_review_days_ago, review summary/themes | signals, review_context |
| Website | SSL, mobile, contact form, booking, hiring (homepage only) | signals |
| Services (dental) | service_intelligence: high-ticket vs general, dedicated vs mentioned, missing_high_value_pages | service_depth |
| Competitors (dental) | competitive_snapshot: 5 nearby, avg reviews/rating, lead percentile, market_density | competitor_sampling |
| Decision | root_bottleneck, primary_sales_anchor, intervention_plan (concrete), seo_best_lever | objective_decision_layer |
| Prioritization | seo_sales_value_score (internal), lead_score | revenue_leverage, score, export sort |

So we **already produce** the ingredients for a 60-second view; the gap is **structure and surface area**, not missing data (except hiring scope and one “single glance” summary).

---

## 4. Proposed structure: “60-second insight” without new APIs

Goal: **One screen per lead** that a rep can scan in ~60 seconds, with optional drill-down. No requirement for new API calls; focus on **shaping and ordering** what we have.

### 4.1 Single-screen summary block (new)

Add one block per lead that everything else can hang off:

```text
"sixty_second_summary": {
  "call_or_defer": "call" | "defer",
  "lead_with": "One sentence: what to say first (from primary_sales_anchor / root cause).",
  "first_action": "One concrete action (from intervention_plan[0]).",
  "evidence": ["Bullet 1", "Bullet 2", "Bullet 3"],
  "competitive_one_liner": "e.g. Below median reviews vs 5 nearby; high density.",
  "seo_priority_score": 0–100
}
```

- **call_or_defer:** Derived from verdict + seo_sales_value_score + root_bottleneck (e.g. trust_limited + low score → defer; visibility_limited + high score → call).
- **lead_with:** From `objective_decision_layer.primary_sales_anchor.issue` + optional `why_this_first` in one line.
- **first_action:** From `intervention_plan[0].action` (already concrete and measurable in 60 days).
- **evidence:** From root_bottleneck evidence + 1–2 from DCM or comparative_context.
- **competitive_one_liner:** From `comparative_context` or a one-sentence version of `competitive_snapshot`.
- **seo_priority_score:** Existing `seo_sales_value_score` (or lead_score when that’s not present).

This block is **computed** from existing fields (deterministic or one LLM call we already do); no new crawl or Places calls.

### 4.2 Export / list shape: “60-second first”

- **Default list order:** Sort by `seo_sales_value_score` (or equivalent priority) descending so the best leads are at the top.
- **Default export columns (CSV) / top-level keys (JSON):**  
  `name`, `address`, `call_or_defer`, `lead_with`, `first_action`, `seo_priority_score`, `root_bottleneck`, `competitive_one_liner`, then `evidence` (or a short evidence string).  
  Full `objective_decision_layer`, `service_intelligence`, `competitive_snapshot`, `revenue_leverage_analysis` stay as nested/detail.
- **Optional:** A “summary only” export (e.g. `--summary-only`) that outputs only the 60-second block + name/address/place_id for a quick list.

### 4.3 Hiring: optional enhancement (no new URL required for MVP)

- **Current:** Homepage HTML only → good for “hiring mentioned on homepage”.
- **Option A (minimal):** When we already have homepage HTML, add one more check: if we see a **link** to `/careers` or `/jobs` but no hiring **text** on the homepage, set `hiring_active = true` with a note like `"careers_link_only"` so the rep knows to look at the careers page themselves. No extra fetch.
- **Option B (later):** Add an optional second fetch of the first “careers-like” URL found on the page; then hiring_roles and hiring_active can use that page too. (Adds one HTTP request per lead with a careers link.)

Recommendation: do **Option A** first so we don’t under-count “has a careers page” when the homepage only has a link.

---

## 5. Where this lives in the pipeline

- **Compute `sixty_second_summary`:** After `objective_decision_layer` (and optional revenue_leverage / seo_sales_value_score) are set. Either in the same place we build the objective layer or in a small post-step that runs per lead before save/export.
- **Export:** In `export_leads.py`, when building decision-first export, add the 60-second block to each lead and (optionally) add a “summary-first” CSV/JSON view that sorts by `seo_priority_score` and surfaces the new fields first.
- **Hiring:** In `signals.py`, extend hiring logic so that “careers/jobs link present but no hiring text” still sets `hiring_active = true` and optionally sets a flag like `hiring_signal_source: "careers_link_only"` for transparency.

---

## 6. What we’re not adding (to stay within “60 seconds” and avoid scope creep)

- No new APIs (no extra Places or crawl beyond what we have).
- No new LLM call for the summary (derive from existing fields).
- No generic “narrative” copy; keep **lead_with** and **first_action** to one sentence each and reuse existing anchor/intervention text.
- No UI implementation in this doc (export shape is the contract; UI can consume it later).

---

## 7. Summary table

| Piece | Purpose |
|-------|--------|
| **Hiring today** | Homepage-only regex + link patterns; tri-state + role list. |
| **60-second block** | One structured summary: call/defer, lead_with, first_action, evidence, competitive one-liner, score. |
| **Export order** | Sort by seo_sales_value_score (or priority) so best leads first. |
| **Export shape** | Summary fields at top level; full blocks nested. Optional summary-only export. |
| **Hiring tweak** | Treat “careers/jobs link but no text” as hiring_active = true (option A); optional careers-page fetch later (option B). |

This structure keeps the system focused on turning 30–60 minutes of manual SEO research into a single, scannable 60-second view per lead without adding new data sources—only better structure and one optional hiring refinement.
