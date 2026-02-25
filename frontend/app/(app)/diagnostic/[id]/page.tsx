"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getDiagnostic, deleteDiagnostic, submitDiagnostic, pollUntilDone } from "@/lib/api";
import type { DiagnosticResponse } from "@/lib/types";

function oppProfileText(op: unknown): string {
  if (!op) return "";
  if (typeof op === "object" && op !== null && "label" in op) {
    const o = op as { label?: string; why?: string };
    return o.why ? `${o.label} (${o.why})` : o.label ?? "";
  }
  return String(op);
}

export default function DiagnosticDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);

  const [result, setResult] = useState<DiagnosticResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [rerunning, setRerunning] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!id || isNaN(id)) {
      setError("Invalid diagnostic ID");
      setLoading(false);
      return;
    }
    getDiagnostic(id)
      .then(setResult)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

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

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-8rem)] bg-zinc-50">
        <main className="mx-auto max-w-3xl px-6 py-20 text-center">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-600" />
          <p className="mt-3 text-sm text-zinc-400">Loading diagnostic…</p>
        </main>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-[calc(100vh-8rem)] bg-zinc-50">
        <main className="mx-auto max-w-3xl px-6 py-20 text-center">
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

  return (
    <div className="min-h-[calc(100vh-8rem)] bg-zinc-50 text-zinc-900">
      <main className="mx-auto max-w-3xl px-6 py-10">
        {/* Top bar */}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Link href="/dashboard" className="text-sm text-zinc-500 hover:text-zinc-700">&larr; Dashboard</Link>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRerun}
              disabled={rerunning}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-50"
            >
              {rerunning ? "Re-running…" : "Re-run diagnostic"}
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition hover:bg-red-50 disabled:opacity-50"
            >
              Delete
            </button>
          </div>
        </div>

        <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="mb-1 text-sm font-medium uppercase tracking-wider text-zinc-500">Revenue Intelligence Brief</h2>
          <p className="mb-5 text-sm text-zinc-700">Lead #{result.lead_id} · {result.business_name} · {result.city}{result.state ? `, ${result.state}` : ""}</p>

          <div className="space-y-6 text-sm">
            {/* 1. Executive Diagnosis */}
            <BriefSection title="Executive Diagnosis">
              <KV label="Constraint" value={ed?.constraint ?? result.constraint} />
              <KV label="Primary Leverage" value={ed?.primary_leverage ?? (result.primary_leverage !== "—" ? result.primary_leverage : undefined)} />
              {(ed?.opportunity_profile || result.opportunity_profile) && (
                <p><strong>Opportunity Profile:</strong> {oppProfileText(ed?.opportunity_profile) || result.opportunity_profile}</p>
              )}
              <KV label="Modeled Revenue Upside" value={ed?.modeled_revenue_upside} />
              {b?.executive_footnote && <p className="mt-2 text-xs text-zinc-500">{b.executive_footnote}</p>}
            </BriefSection>

            {/* 2. Market Position */}
            {(mp?.revenue_band || mp?.reviews || mp?.local_avg || mp?.market_density || result.review_position || result.market_density) ? (
              <BriefSection title="Market Position">
                <KV label="Revenue Band" value={mp?.revenue_band} />
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

            {/* 5. Demand Signals */}
            {(ds?.google_ads_line != null || ds?.meta_ads_line != null || ds?.paid_spend_estimate || ds?.organic_visibility_tier || ds?.last_review_days_ago != null || ds?.review_velocity_30d != null) || (!ds && result.paid_status) ? (
              <BriefSection title="Demand Signals">
                <KV label="Google Ads" value={ds?.google_ads_line} />
                {ds?.paid_spend_estimate && <KV label="Paid Spend Estimate" value={ds.paid_spend_estimate} />}
                <KV label="Meta Ads" value={ds?.meta_ads_line} />
                {ds?.organic_visibility_tier && (
                  <KV label="Organic Visibility" value={`${ds.organic_visibility_tier}${ds.organic_visibility_reason ? ` — ${ds.organic_visibility_reason}` : ''}`} />
                )}
                {ds?.last_review_days_ago != null && <KV label="Last Review" value={`~${ds.last_review_days_ago} days ago${ds.last_review_estimated ? ' (estimated)' : ''}`} />}
                {ds?.review_velocity_30d != null && <KV label="Review Velocity" value={`~${ds.review_velocity_30d} in last 30 days${ds.review_velocity_estimated ? ' (estimated)' : ''}`} />}
                {!ds && result.paid_status && <KV label="Paid Status" value={result.paid_status} />}
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
                <p className="mt-1 text-xs text-zinc-500">Modeled from public proxy signals; not GA4 or Ads platform data.</p>
              </BriefSection>
            ) : null}

            {/* 8. Strategic Gap Identified */}
            {sg && sg.competitor_name ? (
              <BriefSection title="Strategic Gap Identified">
                <p>Nearest competitor {sg.competitor_name} holds {sg.competitor_reviews ?? "—"} reviews within {sg.distance_miles ?? "—"} miles.</p>
                <p>This practice offers high-ticket services but lacks dedicated service pages and/or schema support.</p>
                <p>Capture gap identified in a high-margin service category within a {sg.market_density ?? "High"} density market.</p>
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

            {/* 12. Evidence (collapsible) */}
            {(b?.evidence_bullets?.length || result.evidence?.length) ? (
              <div className="border-t border-zinc-100 pt-4">
                <button
                  type="button"
                  className="flex items-center gap-1 font-medium text-zinc-800 hover:text-zinc-600"
                  onClick={() => setEvidenceOpen(!evidenceOpen)}
                >
                  <span className="text-xs">{evidenceOpen ? "▼" : "▶"}</span>
                  Evidence (click to expand)
                </button>
                {evidenceOpen && (
                  <ul className="mt-2 list-inside list-disc space-y-1 text-zinc-700">
                    {b?.evidence_bullets?.length
                      ? b.evidence_bullets.map((e, i) => <li key={i}>{e}</li>)
                      : (result.evidence ?? []).map((e, i) => <li key={i}><strong>{e.label}:</strong> {e.value}</li>)}
                  </ul>
                )}
              </div>
            ) : null}
          </div>
        </section>
      </main>
    </div>
  );
}

function BriefSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-zinc-100 pt-4 first:border-t-0 first:pt-0">
      <h3 className="mb-2 font-medium text-zinc-800">{title}</h3>
      <div className="space-y-1.5 text-zinc-700">{children}</div>
    </div>
  );
}

function KV({ label, value }: { label: string; value?: string | null }) {
  if (value == null || value === "") return null;
  return <p><strong>{label}:</strong> {value}</p>;
}
