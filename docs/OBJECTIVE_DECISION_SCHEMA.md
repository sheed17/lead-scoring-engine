# Objective Decision Layer — Schema & Root Logic (Dental SEO)

Schema and logic for the dental lead objective decision layer: root bottleneck, service depth, competitor snapshot, revenue leverage, and SEO sales value.

---

## Root bottleneck values

Exactly one per lead:

| Bottleneck | When chosen |
|------------|-------------|
| **trust_limited** | Trust signals Weak (rating, review volume, or trust content). Checked first. |
| **differentiation_limited** | Trust/capture Strong or Moderate; visibility Saturated or market density High; **no strong niche** (low revenue asymmetry or &lt;2 high-ticket procedures). |
| **saturation_limited** | Visibility gap Saturated, map_pack High, trust not Weak (and not differentiation_limited). |
| **visibility_limited** | Capture Weak with demand present; or capture Weak/Moderate and conversion not Weak. |
| **conversion_limited** | **Booking only primary when**: (ads or strong demand) AND conversion Weak AND not (strong capture + strong trust + niche). |
| **demand_limited** | Demand Weak after other checks. |

**Booking as primary** (conversion_limited) is used only when there are high-traffic proxies (ads or strong demand), no frictionless intake, and no established differentiation — so we do not over-index on booking.

---

## New blocks (schema)

### service_intelligence

From homepage + main nav crawl; keyword detection for high-ticket vs general services.

```json
"service_intelligence": {
  "high_ticket_procedures_detected": [
    { "procedure": "dental implants", "signal": "dedicated_page", "url_path": "/dental-implants" },
    { "procedure": "invisalign", "signal": "mentioned_only", "url_path": null }
  ],
  "general_services_detected": ["cleaning", "checkups"],
  "missing_high_value_pages": ["dental implants", "veneers"],
  "procedure_confidence": 0.75
}
```

- **high_ticket_procedures_detected**: implants, invisalign, veneers, cosmetic dentistry, sedation, emergency dentist, same day crown, sleep apnea, orthodontics — each with `signal`: `dedicated_page` (strong) or `mentioned_only` (weak).
- **missing_high_value_pages**: high-ticket services mentioned (e.g. in copy) but no dedicated page.

### competitive_snapshot

Nearby Search 1.5 mi, top 5 dentists (excluding lead).

```json
"competitive_snapshot": {
  "dentists_sampled": 5,
  "avg_review_count": 120,
  "avg_rating": 4.6,
  "percent_with_booking": null,
  "lead_review_count": 95,
  "review_positioning": "Below sample average",
  "market_density_score": "High",
  "confidence": 0.7
}
```

- **market_density_score**: "Low" | "Moderate" | "High" from local density.
- **lead_review_count**: lead’s review count.
- **review_positioning**: "Above sample average" | "Below sample average" | "In line with sample average" (derived from lead_review_count vs avg_review_count; no percentile from small samples).

### revenue_leverage_analysis

Drives `seo_best_lever` and root bottleneck context.

```json
"revenue_leverage_analysis": {
  "primary_revenue_driver_detected": "implants",
  "estimated_revenue_asymmetry": "High",
  "highest_leverage_growth_vector": "Add dedicated implant and cosmetic pages; capture high-intent local queries.",
  "confidence": 0.7
}
```

- **primary_revenue_driver_detected**: "implants" | "general" | "cosmetic" | "unknown".
- **estimated_revenue_asymmetry**: "Low" | "Moderate" | "High" (high when implants/veneers/invisalign pages exist).

### seo_sales_value_score

Internal 0–100 for **prioritization only** (not shown to dentist). Increases with: high revenue asymmetry, weak visibility, below-median review percentile, missing high-value pages, low competition. Decreases with: high saturation + strong reviews, no revenue leverage, strong booking + ads + trust.

```json
"seo_sales_value_score": 72
```

---

## Full objective_decision_layer shape (with new fields)

```json
{
  "root_bottleneck_classification": {
    "bottleneck": "differentiation_limited",
    "why_root_cause": "Reviews and visibility are solid but the market is competitive; the practice lacks clear service or niche positioning to stand out.",
    "evidence": ["Review count vs market: Above Average", "Visibility gap: Saturated"],
    "what_would_change": "Strong high-ticket or niche service positioning (e.g. dedicated implant or cosmetic pages) would shift this.",
    "confidence": 0.85
  },
  "seo_lever_assessment": {
    "is_primary_growth_lever": true,
    "confidence": 0.75,
    "reasoning": "Differentiation is the constraint; SEO (service pages, local positioning) can help the practice stand out.",
    "alternative_primary_lever": ""
  },
  "demand_capture_conversion_model": { "demand_signals": {...}, "capture_signals": {...}, "conversion_signals": {...}, "trust_signals": {...} },
  "comparative_context": "Among 5 nearby dentists, this practice has 95 reviews (avg 120); estimated review percentile 45. Market density: High.",
  "primary_sales_anchor": {
    "issue": "Build clear service or niche positioning",
    "why_this_first": "Strong reviews and visibility but no dedicated high-value procedure pages; competitors with implant/cosmetic pages capture more intent.",
    "what_happens_if_ignored": "High-intent patients will continue to choose practices with clearer service positioning.",
    "confidence": 0.8
  },
  "intervention_plan": [
    {
      "priority": 1,
      "action": "Create dedicated dental implant landing page optimized for local intent.",
      "category": "Capture",
      "expected_impact": "Capture high-intent implant queries; measurable via impressions and conversions in 60 days.",
      "time_to_signal_days": 45,
      "confidence": 0.75,
      "why_not_secondaries_yet": "Service depth is the root constraint; other levers matter after positioning is clear."
    },
    {
      "priority": 2,
      "action": "Build emergency dentist page targeting after-hours queries.",
      "category": "Capture",
      "expected_impact": "Capture urgent-intent demand.",
      "time_to_signal_days": 30,
      "confidence": 0.6
    }
  ],
  "access_request_plan": [
    { "intervention_ref": "Service page creation", "access_type": "Website Admin", "why_needed": "To add and optimize new service pages.", "risk_level": "Low", "when_to_ask": "After initial agreement" }
  ],
  "de_risking_questions": [
    { "question": "Which procedures drive most of your new patient revenue?", "ties_to_uncertainty": "Revenue driver validation" },
    { "question": "Do you have dedicated pages for implants or cosmetic work?", "ties_to_uncertainty": "Service depth" },
    { "question": "How do you compare your visibility to nearby practices?", "ties_to_uncertainty": "Competitive perception" }
  ],
  "service_intelligence": { "high_ticket_procedures_detected": [...], "general_services_detected": [...], "missing_high_value_pages": ["dental implants"], "procedure_confidence": 0.75 },
  "competitive_snapshot": { "dentists_sampled": 5, "avg_review_count": 120, "lead_review_count": 80, "review_positioning": "Below sample average", "market_density_score": "High", "confidence": 0.7 },
  "revenue_leverage_analysis": { "primary_revenue_driver_detected": "implants", "estimated_revenue_asymmetry": "High", "highest_leverage_growth_vector": "Add dedicated implant and cosmetic pages.", "confidence": 0.7 },
  "seo_sales_value_score": 72
}
```

---

## Example upgraded output (one dentist)

**Lead:** Mid-size practice, 95 reviews, 4.7 rating, website with contact form but no online booking. No dedicated implant/cosmetic pages; “implants” and “Invisalign” mentioned in copy only. Competitors (5 within 1.5 mi): avg 120 reviews, avg 4.6 rating; market density High.

**Result:**

- **Root bottleneck:** `differentiation_limited` — strong reviews and capture, saturated/high-density market, no strong niche (missing dedicated high-value pages).
- **Revenue leverage:** `estimated_revenue_asymmetry`: High (implants/Invisalign implied); `missing_high_value_pages`: ["dental implants", "invisalign"].
- **SEO best lever:** true (differentiation → SEO/service pages are the lever).
- **seo_sales_value_score:** 72 (high asymmetry, missing pages, below-median percentile in a dense market).
- **Primary sales anchor:** “Build clear service or niche positioning” — lead with missing high-value pages and competitive context.
- **First intervention:** “Create dedicated dental implant landing page optimized for local intent” (implementable, measurable in 60 days).

This cuts manual SEO research into a single structured insight: root cause, revenue context, competitive frame, and one concrete first action.
