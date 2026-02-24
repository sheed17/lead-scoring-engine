"use client";

import { useState, useEffect } from "react";
import { checkHealth, runDiagnostic } from "@/lib/api";
import type { DiagnosticResponse } from "@/lib/types";

export default function Home() {
  const [apiStatus, setApiStatus] = useState<"checking" | "up" | "down">("checking");
  const [businessName, setBusinessName] = useState("");
  const [city, setCity] = useState("");
  const [website, setWebsite] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnosticResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    checkHealth()
      .then(() => setApiStatus("up"))
      .catch(() => setApiStatus("down"));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const data = await runDiagnostic({
        business_name: businessName.trim(),
        city: city.trim(),
        ...(website.trim() ? { website: website.trim() } : {}),
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <h1 className="text-lg font-semibold tracking-tight">
            Lead Scoring Engine
          </h1>
          <div className="flex items-center gap-2 text-sm">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                apiStatus === "up"
                  ? "bg-emerald-500"
                  : apiStatus === "down"
                    ? "bg-red-500"
                    : "animate-pulse bg-amber-500"
              }`}
            />
            <span className="text-zinc-500">
              {apiStatus === "up"
                ? "API connected"
                : apiStatus === "down"
                  ? "API offline"
                  : "Checking…"}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-10">
        <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-zinc-500">
            Diagnostic
          </h2>
          <p className="mb-6 text-sm text-zinc-600">
            Run enrichment for a business. Resolves by name + city, then returns
            opportunity profile, constraint, and intervention plan.
          </p>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="business_name"
                className="mb-1 block text-sm font-medium text-zinc-700"
              >
                Business name *
              </label>
              <input
                id="business_name"
                type="text"
                required
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="e.g. Japantown Dental"
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>
            <div>
              <label
                htmlFor="city"
                className="mb-1 block text-sm font-medium text-zinc-700"
              >
                City *
              </label>
              <input
                id="city"
                type="text"
                required
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="e.g. San Jose"
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>
            <div>
              <label
                htmlFor="website"
                className="mb-1 block text-sm font-medium text-zinc-700"
              >
                Website <span className="text-zinc-400">(optional)</span>
              </label>
              <input
                id="website"
                type="text"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="e.g. japantowndental.com"
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading || apiStatus !== "up"}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50"
            >
              {loading ? "Running…" : "Run diagnostic"}
            </button>
          </form>
          {error && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {error}
            </div>
          )}
        </section>

        {result && (
          <section className="mt-8 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-zinc-500">
              Result
            </h2>
            <div className="space-y-4">
              <div className="grid gap-3 text-sm sm:grid-cols-2">
                <ResultRow label="Lead ID" value={String(result.lead_id)} />
                <ResultRow label="Business" value={result.business_name} />
                <ResultRow label="City" value={result.city} />
                <ResultRow
                  label="Opportunity profile"
                  value={result.opportunity_profile}
                />
                <ResultRow label="Constraint" value={result.constraint} />
                <ResultRow
                  label="Primary leverage"
                  value={result.primary_leverage}
                />
                <ResultRow
                  label="Market density"
                  value={result.market_density}
                />
                <ResultRow
                  label="Review position"
                  value={result.review_position}
                />
                <ResultRow label="Paid status" value={result.paid_status} />
              </div>
              {result.intervention_plan.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-medium text-zinc-700">
                    Intervention plan
                  </h3>
                  <ul className="space-y-2">
                    {result.intervention_plan.map((item) => (
                      <li
                        key={item.step}
                        className="flex gap-2 rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2 text-sm"
                      >
                        <span className="shrink-0 font-medium text-zinc-500">
                          {item.step}.
                        </span>
                        <span className="shrink-0 rounded bg-zinc-200 px-1.5 py-0.5 text-xs">
                          {item.category}
                        </span>
                        <span className="text-zinc-700">{item.action}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </section>
        )}
      </main>

      <footer className="mt-16 border-t border-zinc-200 px-6 py-4 text-center text-xs text-zinc-500">
        Lead Scoring Engine · Diagnostic API
      </footer>
    </div>
  );
}

function ResultRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <span className="block text-zinc-500">{label}</span>
      <span className="block font-medium text-zinc-800">{value || "—"}</span>
    </div>
  );
}
