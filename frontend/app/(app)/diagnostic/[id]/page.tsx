"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getDiagnostic,
  deleteDiagnostic,
  submitDiagnostic,
  pollUntilDone,
  createDiagnosticShareLink,
  getDiagnosticBriefPdfUrl,
} from "@/lib/api";
import type { DiagnosticResponse } from "@/lib/types";
import Button from "@/app/components/ui/Button";
import { Card } from "@/app/components/ui/Card";

function oppProfileText(op: unknown): string {
  if (!op) return "";
  if (typeof op === "object" && op !== null && "label" in op) {
    const o = op as { label?: string; why?: string };
    return o.why ? `${o.label} (${o.why})` : o.label ?? "";
  }
  return String(op);
}

function leverageDriversText(op: unknown): string {
  if (!op || typeof op !== "object") return "";
  const drivers = (op as {
    leverage_drivers?: {
      missing_high_value_pages?: boolean;
      market_density_high?: boolean;
      schema_missing?: boolean;
      paid_active?: boolean;
      review_deficit?: boolean;
    };
  }).leverage_drivers;
  if (!drivers) return "";
  return [
    `missing high-value pages ${drivers.missing_high_value_pages ? "✓" : "✗"}`,
    `high-density market ${drivers.market_density_high ? "✓" : "✗"}`,
    `schema missing ${drivers.schema_missing ? "✓" : "✗"}`,
    `paid ads active ${drivers.paid_active ? "✓" : "✗"}`,
    `review deficit (<50% of local avg) ${drivers.review_deficit ? "✓" : "✗"}`,
  ].join(", ");
}

export default function DiagnosticDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const invalidId = !id || isNaN(id);

  const [result, setResult] = useState<DiagnosticResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);

  useEffect(() => {
    if (invalidId) {
      return;
    }
    getDiagnostic(id)
      .then(setResult)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, invalidId]);

  async function handleRerun() {
    if (!result) return;
    setRerunning(true);
    try {
      const { job_id } = await submitDiagnostic({
        business_name: result.business_name,
        city: result.city,
        state: result.state || "",
      });
      const job = await pollUntilDone(job_id);
      if (job.status === "completed" && job.diagnostic_id) {
        router.push(`/diagnostic/${job.diagnostic_id}`);
      } else {
        setError(job.error || "Re-run failed");
        setRerunning(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-run failed");
      setRerunning(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this diagnostic?")) return;
    setDeleting(true);
    try {
      await deleteDiagnostic(id);
      router.push("/dashboard");
    } catch {
      setDeleting(false);
    }
  }

  async function handleShare() {
    setSharing(true);
    try {
      const res = await createDiagnosticShareLink(id);
      const uiUrl = `${window.location.origin}/brief/s/${res.token}`;
      setShareUrl(uiUrl);
      await navigator.clipboard.writeText(uiUrl);
      alert("Share link copied to clipboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create share link");
    } finally {
      setSharing(false);
    }
  }

  if (invalidId) {
    return (
      <div className="mx-auto max-w-5xl px-2 py-10">
        <main className="text-center">
          <p className="text-red-600">Invalid diagnostic ID</p>
          <Link href="/dashboard" className="mt-4 inline-block text-sm text-zinc-600 underline">Back to dashboard</Link>
        </main>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-2 py-10">
        <main className="text-center">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-600" />
          <p className="mt-3 text-sm text-zinc-400">Loading diagnostic…</p>
        </main>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="mx-auto max-w-5xl px-2 py-10">
        <main className="text-center">
          <p className="text-red-600">{error || "Diagnostic not found"}</p>
          <Link href="/dashboard" className="mt-4 inline-block text-sm text-zinc-600 underline">Back to dashboard</Link>
        </main>
      </div>
    );
  }

  const b = result.brief;
  const ed = b?.executive_diagnosis;
  const mp = b?.market_position;
  const cc = b?.competitive_context;
  const ds = b?.demand_signals;
  const csg = b?.competitive_service_gap;
  const sg = b?.strategic_gap;
  const ht = b?.high_ticket_gaps;
  const rucg = b?.revenue_upside_capture_gap;
  const ci = b?.conversion_infrastructure;
  const cd = b?.competitive_delta as Record<string, unknown> | undefined;
  const serp = b?.serp_presence as Record<string, unknown> | undefined;
  const reviewIntel = b?.review_intelligence as Record<string, unknown> | undefined;
  const convStruct = b?.conversion_structure as Record<string, unknown> | undefined;
  const marketSat = b?.market_saturation as Record<string, unknown> | undefined;
  const geo = b?.geo_coverage as Record<string, unknown> | undefined;
  const reviewSampleSize = Number(reviewIntel?.review_sample_size || 0);
  const reviewServiceMentions = (reviewIntel?.service_mentions as Record<string, unknown>) || {};
  const reviewComplaintThemes = (reviewIntel?.complaint_themes as Record<string, unknown>) || {};

  return (
    <div className="mx-auto max-w-6xl text-[var(--text-primary)]">
      <main>
        {/* Top bar */}
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-[var(--text-muted)]">
            <Link href="/dashboard" className="app-link">Dashboard</Link> {"→"} <span className="text-[var(--text-secondary)]">{result.business_name}</span>
          </p>
          <div className="flex items-center gap-2">
            <Button
              onClick={handleShare}
              disabled={sharing}
            >
              {sharing ? "Sharing…" : "Share"}
            </Button>
            <a
              href={getDiagnosticBriefPdfUrl(id)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-card)] px-3 text-sm font-medium text-[var(--text-secondary)] hover:bg-slate-50"
            >
              Download PDF
            </a>
            <Button
              onClick={handleRerun}
              disabled={rerunning}
            >
              {rerunning ? "Re-running…" : "Re-run diagnostic"}
            </Button>
            <Button
              onClick={handleDelete}
              disabled={deleting}
              className="border-rose-200 text-rose-600 hover:bg-rose-50"
            >
              Delete
            </Button>
          </div>
        </div>

        <Card className="p-6">
          <h2 className="mb-1 text-sm font-medium uppercase tracking-wider text-zinc-500">Revenue Intelligence Brief</h2>
          <p className="mb-5 text-sm text-zinc-700">Lead #{result.lead_id} · {result.business_name} · {result.city}{result.state ? `, ${result.state}` : ""}</p>

          <div className="space-y-6 text-sm">
            {shareUrl && (
              <BriefSection title="Share Link">
                <p className="break-all text-zinc-700">{shareUrl}</p>
              </BriefSection>
            )}

            {/* 1. Executive Diagnosis */}
            <BriefSection title="Executive Diagnosis">
              <KV label="Constraint" value={ed?.constraint ?? result.constraint} />
              <KV label="Primary Leverage" value={ed?.primary_leverage ?? (result.primary_leverage !== "—" ? result.primary_leverage : undefined)} />
              {(ed?.opportunity_profile || result.opportunity_profile) && (
                <p><strong>Opportunity Profile:</strong> {oppProfileText(ed?.opportunity_profile) || result.opportunity_profile}</p>
              )}
              {leverageDriversText(ed?.opportunity_profile) && (
                <p className="text-xs text-zinc-500">
                  Based on: {leverageDriversText(ed?.opportunity_profile)}.
                </p>
              )}
              <KV label="Modeled Revenue Upside" value={ed?.modeled_revenue_upside} />
              {b?.executive_footnote && <p className="mt-2 text-xs text-zinc-500">{b.executive_footnote}</p>}
            </BriefSection>

            {/* 2. Market Position */}
            {(mp?.revenue_band || mp?.reviews || mp?.local_avg || mp?.market_density || result.review_position || result.market_density) ? (
              <BriefSection title="Market Position">
                <KV label="Revenue Band" value={mp?.revenue_band} />
                {mp?.revenue_band_method && <p className="text-xs text-zinc-500">{mp.revenue_band_method}</p>}
                <KV label="Reviews" value={mp?.reviews} />
                <KV label="Local Avg" value={mp?.local_avg} />
                <KV label="Market Density" value={mp?.market_density ?? result.market_density} />
                {!mp && result.review_position && <KV label="Review Position" value={result.review_position} />}
              </BriefSection>
            ) : null}

            {/* 3. Competitive Context */}
            {(cc?.line1 || cc?.line2 || cc?.line3) ? (
              <BriefSection title="Competitive Context">
                {cc?.line1 && <p>{cc.line1}</p>}
                {cc?.line2 && <p>{cc.line2}</p>}
                {cc?.line3 && <p>{cc.line3}</p>}
              </BriefSection>
            ) : null}

            {/* 4. Competitive Service Gap */}
            {csg && (csg.service || csg.competitor_name) ? (
              <BriefSection title="Competitive Service Gap">
                <KV label="Type" value={csg.type ?? "High-Margin Capture Gap"} />
                <KV label="Service" value={csg.service} />
                <KV label="Nearest competitor" value={csg.competitor_name} />
                {csg.competitor_reviews != null && <KV label="Competitor reviews" value={String(csg.competitor_reviews)} />}
                {csg.lead_reviews != null && <KV label="Lead reviews" value={String(csg.lead_reviews)} />}
                {csg.distance_miles != null && <KV label="Distance" value={`${csg.distance_miles} mi`} />}
                {csg.schema_missing && <KV label="Schema" value="Missing" />}
              </BriefSection>
            ) : null}

            {cd ? (
              <BriefSection title="Competitive Delta">
                <KV
                  label="Service pages"
                  value={
                    cd.competitor_avg_service_pages != null
                      ? `${cd.target_service_page_count ?? 0} pages with service-like paths (for example, /implants, /cosmetic) vs competitor avg ${Number(cd.competitor_avg_service_pages).toFixed(1)}`
                      : `Target: ${cd.target_service_page_count ?? 0} pages with service-like paths (${String(cd.competitor_crawl_note || "Competitor website metrics not run for this brief.")})`
                  }
                />
                {cd.target_pages_with_faq_schema != null && (
                  <KV
                    label="FAQ/Schema coverage"
                    value={
                      cd.competitor_avg_pages_with_schema != null
                        ? `${cd.target_pages_with_faq_schema} of ${cd.target_service_page_count ?? 0} service pages vs competitor avg ${Number(cd.competitor_avg_pages_with_schema).toFixed(1)} pages`
                        : `${cd.target_pages_with_faq_schema} of ${cd.target_service_page_count ?? 0} service pages`
                    }
                  />
                )}
                <KV
                  label="Service page depth"
                  value={
                    cd.competitor_avg_word_count != null
                      ? `Average word count across ${cd.target_service_page_count ?? 0} service pages: ~${Math.round(Number(cd.target_avg_word_count_service_pages ?? 0))} (min ${cd.target_min_word_count_service_pages ?? "N/A"}, max ${cd.target_max_word_count_service_pages ?? "N/A"}) vs competitor avg ~${Math.round(Number(cd.competitor_avg_word_count))}`
                      : cd.target_avg_word_count_service_pages != null
                        ? `Average word count across ${cd.target_service_page_count ?? 0} service pages: ~${Math.round(Number(cd.target_avg_word_count_service_pages))} (min ${cd.target_min_word_count_service_pages ?? "N/A"}, max ${cd.target_max_word_count_service_pages ?? "N/A"})`
                        : undefined
                  }
                />
                <p className="text-xs text-zinc-500">
                  {cd.competitors_sampled ? `Based on ${cd.competitors_sampled} nearby competitors.` : "Target-only snapshot for this run."}
                </p>
                {cd.competitor_site_metrics_count != null && Number(cd.competitor_site_metrics_count) > 0 && (
                  <p className="text-xs text-zinc-500">
                    Competitor averages from {String(cd.competitor_site_metrics_count)} competitor sites crawled.
                  </p>
                )}
              </BriefSection>
            ) : null}

            {/* 5. Demand Signals */}
            {(ds?.google_ads_line != null || ds?.meta_ads_line != null || ds?.organic_visibility_tier || ds?.last_review_days_ago != null || ds?.review_velocity_30d != null) || (!ds && result.paid_status) ? (
              <BriefSection title="Demand Signals">
                <KV label="Google Ads" value={ds?.google_ads_line} />
                {ds?.google_ads_source && <p className="text-xs text-zinc-500">Source: {ds.google_ads_source}</p>}
                <KV label="Meta Ads" value={ds?.meta_ads_line} />
                {ds?.meta_ads_source && <p className="text-xs text-zinc-500">Source: {ds.meta_ads_source}</p>}
                {ds?.paid_channels_detected?.length ? <KV label="Paid channels detected" value={ds.paid_channels_detected.join(", ")} /> : null}
                {ds?.organic_visibility_tier && (
                  <KV label="Organic Visibility" value={`${ds.organic_visibility_tier}${ds.organic_visibility_reason ? ` — ${ds.organic_visibility_reason}` : ''}`} />
                )}
                {ds?.last_review_days_ago != null && <KV label="Last Review" value={`~${ds.last_review_days_ago} days ago${ds.last_review_estimated ? ' (estimated)' : ''}`} />}
                {ds?.review_velocity_30d != null && <KV label="Review Velocity" value={`~${ds.review_velocity_30d} in last 30 days${ds.review_velocity_estimated ? ' (estimated)' : ''}`} />}
                {!ds && result.paid_status && <KV label="Paid Status" value={result.paid_status} />}
              </BriefSection>
            ) : null}

            {serp && Array.isArray(serp.keywords) ? (
              <BriefSection title="SERP Presence">
                <ul className="list-inside list-disc space-y-1">
                  {(serp.keywords as Array<Record<string, unknown>>).slice(0, 6).map((k, i) => (
                    <li key={i}>
                      {String(k.keyword || "keyword")}:
                      {" "}
                      {k.position == null ? "not in top 10" : `position ${k.position}`}
                    </li>
                  ))}
                </ul>
                {serp.as_of_date && <p className="text-xs text-zinc-500">As of {String(serp.as_of_date)}</p>}
              </BriefSection>
            ) : null}

            {reviewIntel ? (
              <BriefSection title="Review Intelligence">
                {reviewSampleSize > 0 && (
                  <p>
                    <strong>Directional signal from {reviewSampleSize} sampled Google reviews:</strong>{" "}
                    {String(reviewIntel.summary || "No strong qualitative pattern extracted.")}
                  </p>
                )}
                {Object.keys(reviewServiceMentions).length > 0 && (
                  <p>
                    <strong>Most-mentioned services in sample:</strong>{" "}
                    {Object.entries(reviewServiceMentions)
                      .slice(0, 6)
                      .map(([k, v]) => `${k}: ${v}/${reviewSampleSize || "N"}`)
                      .join(", ")}
                  </p>
                )}
                {Object.keys(reviewComplaintThemes).length > 0 && (
                  <p>
                    <strong>Negative/friction mentions in sample:</strong>{" "}
                    {Object.entries(reviewComplaintThemes)
                      .slice(0, 4)
                      .map(([k, v]) => `${k}: ${v}/${reviewSampleSize || "N"}`)
                      .join(", ")}
                  </p>
                )}
                {reviewSampleSize > 0 && (
                  <p className="text-xs text-zinc-500">
                    Source: Google Place Details ({reviewSampleSize} reviews max). Use this as directional voice-of-customer input, not a full review corpus.
                  </p>
                )}
              </BriefSection>
            ) : null}

            {/* 6. Local SEO & High-Value Service Pages */}
            {(() => {
              const detected = ht?.high_ticket_services_detected ?? result.service_intelligence?.detected_services ?? [];
              const missing = new Set((ht?.missing_landing_pages ?? result.service_intelligence?.missing_services ?? []).map(s => s.toLowerCase()));
              const schemaVal = ht?.schema ?? (result.service_intelligence?.schema_detected != null ? (result.service_intelligence.schema_detected ? "Detected" : "Not detected") : undefined);
              if (!detected.length && !missing.size && schemaVal == null) return null;
              return (
                <BriefSection title="Local SEO & High-Value Service Pages">
                  {detected.length > 0 && (
                    <div className="space-y-1">
                      {detected.map((s, i) => {
                        const hasPage = !missing.has(s.toLowerCase());
                        return (
                          <div key={i} className="flex items-center gap-2">
                            {hasPage ? (
                              <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 text-xs font-bold flex-shrink-0">✓</span>
                            ) : (
                              <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-red-600 text-xs font-bold flex-shrink-0">✗</span>
                            )}
                            <span className={hasPage ? "text-zinc-700" : "text-zinc-700 font-medium"}>{s}</span>
                            <span className={`text-xs ${hasPage ? "text-emerald-600" : "text-red-500"}`}>
                              {hasPage ? "Has landing page" : "Missing landing page"}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {/* Services only in missing (not in detected) — rare but possible from review mentions */}
                  {[...missing].filter(m => !detected.some(d => d.toLowerCase() === m)).length > 0 && (
                    <div className="space-y-1 mt-1">
                      {[...missing].filter(m => !detected.some(d => d.toLowerCase() === m)).map((s, i) => (
                        <div key={`m-${i}`} className="flex items-center gap-2">
                          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-red-600 text-xs font-bold flex-shrink-0">✗</span>
                          <span className="text-zinc-700 font-medium capitalize">{s}</span>
                          <span className="text-xs text-red-500">Missing landing page</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {schemaVal != null && (
                    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-zinc-100">
                      {schemaVal === "Detected" ? (
                        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 text-xs font-bold flex-shrink-0">✓</span>
                      ) : (
                        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-red-600 text-xs font-bold flex-shrink-0">✗</span>
                      )}
                      <span className="text-zinc-700">Schema Markup</span>
                      <span className={`text-xs ${schemaVal === "Detected" ? "text-emerald-600" : "text-red-500"}`}>{schemaVal}</span>
                    </div>
                  )}
                </BriefSection>
              );
            })()}

            {/* 7. Modeled Revenue Upside */}
            {rucg && rucg.primary_service ? (
              <BriefSection title={`Modeled Revenue Upside — ${rucg.primary_service} Capture Gap`}>
                <p>{rucg.consult_low}–{rucg.consult_high} additional consults/month</p>
                <p>${(rucg.case_low ?? 0).toLocaleString()}–${(rucg.case_high ?? 0).toLocaleString()} per case</p>
                <p className="font-medium">${(rucg.annual_low ?? 0).toLocaleString()}–${(rucg.annual_high ?? 0).toLocaleString()} annually</p>
                {rucg.method_note && <p className="text-xs text-zinc-500">{rucg.method_note}</p>}
                {rucg.gap_service && <KV label="Competitive gap service" value={rucg.gap_service} />}
              </BriefSection>
            ) : null}

            {/* 8. Strategic Gap Identified */}
            {sg && sg.competitor_name ? (
              <BriefSection title="Strategic Gap Identified">
                <p>Nearest competitor {sg.competitor_name} holds {sg.competitor_reviews ?? "—"} reviews within {sg.distance_miles ?? "—"} miles in a {sg.market_density ?? "High"} density market.</p>
              </BriefSection>
            ) : null}

            {/* 9. Conversion Infrastructure */}
            {(ci && (ci.online_booking != null || ci.contact_form != null || ci.phone_prominent != null || ci.mobile_optimized != null || ci.page_load_ms != null)) || (result.conversion_infrastructure && (result.conversion_infrastructure.online_booking != null || result.conversion_infrastructure.contact_form != null)) ? (() => {
              const c = ci ?? result.conversion_infrastructure;
              return (
                <BriefSection title="Conversion Infrastructure">
                  {c?.online_booking != null && <KV label="Online Booking" value={c.online_booking ? "Yes" : "No"} />}
                  {c?.contact_form != null && <KV label="Contact Form" value={c.contact_form ? "Yes" : "No"} />}
                  {c?.phone_prominent != null && <KV label="Phone Prominent" value={c.phone_prominent ? "Yes" : "No"} />}
                  {c?.mobile_optimized != null && <KV label="Mobile Optimized" value={c.mobile_optimized ? "Yes" : "No"} />}
                  {c?.page_load_ms != null && <KV label="Page Load" value={`${c.page_load_ms} ms`} />}
                </BriefSection>
              );
            })() : null}

            {convStruct ? (
              <BriefSection title="Conversion Structure">
                {convStruct.phone_clickable != null && <KV label="Phone clickable" value={convStruct.phone_clickable ? "Yes" : "No"} />}
                {convStruct.cta_count != null && <KV label="CTA count" value={String(convStruct.cta_count)} />}
                {convStruct.form_single_or_multi_step != null && <KV label="Form structure" value={String(convStruct.form_single_or_multi_step)} />}
              </BriefSection>
            ) : null}

            {marketSat ? (
              <BriefSection title="Market Saturation">
                {marketSat.top_5_avg_reviews != null && <KV label="Top 5 avg reviews" value={String(marketSat.top_5_avg_reviews)} />}
                {marketSat.competitor_median_reviews != null && marketSat.target_gap_from_median != null && (
                  <KV label="Median comparison" value={`Median ${marketSat.competitor_median_reviews}; target is ${marketSat.target_gap_from_median}`} />
                )}
              </BriefSection>
            ) : null}

            {geo ? (
              <BriefSection title="Geographic Coverage">
                {geo.city_or_near_me_page_count != null && <KV label="City/near-me pages" value={`${geo.city_or_near_me_page_count} detected`} />}
                {geo.city_or_near_me_page_count != null && (
                  <p className="text-xs text-zinc-500">(URLs with city name or &apos;near me&apos; in path/title).</p>
                )}
                {geo.has_multi_location_page != null && <KV label="Multi-location page" value={geo.has_multi_location_page ? "Detected" : "Not detected"} />}
              </BriefSection>
            ) : null}

            {/* 10. Risk Flags */}
            {(b?.risk_flags?.length || result.risk_flags?.length) ? (
              <BriefSection title="Risk Flags">
                <ul className="list-inside list-disc space-y-1">
                  {(b?.risk_flags ?? result.risk_flags ?? []).map((f, i) => <li key={i}>{f}</li>)}
                </ul>
              </BriefSection>
            ) : null}

            {/* 11. Intervention Plan */}
            {(b?.intervention_plan?.length || result.intervention_plan?.length) ? (
              <BriefSection title={`Intervention Plan${b?.intervention_plan?.length ? ` (${b.intervention_plan.length} steps)` : ""}`}>
                <ul className="space-y-2">
                  {b?.intervention_plan?.length
                    ? b.intervention_plan.map((step, i) => (
                        <li key={i} className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2">{step}</li>
                      ))
                    : result.intervention_plan.map((item) => (
                        <li key={item.step} className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2">
                          Step {item.step} — {item.category}: {item.action}
                        </li>
                      ))}
                </ul>
              </BriefSection>
            ) : null}

            {/* 12. Evidence */}
            {(b?.evidence_bullets?.length || result.evidence?.length) ? (
              <BriefSection title="Evidence">
                <ul className="list-inside list-disc space-y-1 text-zinc-700">
                  {b?.evidence_bullets?.length
                    ? b.evidence_bullets.map((e, i) => <li key={i}>{e}</li>)
                    : (result.evidence ?? []).map((e, i) => <li key={i}><strong>{e.label}:</strong> {e.value}</li>)}
                </ul>
              </BriefSection>
            ) : null}
          </div>
        </Card>
      </main>
    </div>
  );
}

function BriefSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-card)] px-4 py-3">
      <h3 className="mb-2 text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
      <div className="space-y-1.5 text-[var(--text-secondary)]">{children}</div>
    </div>
  );
}

function KV({ label, value }: { label: string; value?: string | null }) {
  if (value == null || value === "") return null;
  return <p><strong>{label}:</strong> {value}</p>;
}
