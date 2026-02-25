"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { submitDiagnostic, pollUntilDone } from "@/lib/api";
import type { JobStatusResponse } from "@/lib/types";

export default function NewDiagnosticPage() {
  const router = useRouter();
  const [businessName, setBusinessName] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [website, setWebsite] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setStatus(null);
    setSubmitting(true);

    try {
      const { job_id } = await submitDiagnostic({
        business_name: businessName.trim(),
        city: city.trim(),
        state: state.trim(),
        ...(website.trim() ? { website: website.trim() } : {}),
      });

      setStatus("Job submitted — running pipeline…");

      const result: JobStatusResponse = await pollUntilDone(job_id, (s) => {
        if (s.status === "running") setStatus("Pipeline running — analyzing competitive landscape…");
      });

      if (result.status === "failed") {
        setError(result.error || "Diagnostic failed");
        setSubmitting(false);
        return;
      }

      if (result.diagnostic_id) {
        router.push(`/diagnostic/${result.diagnostic_id}`);
      } else {
        setError("Completed but no diagnostic ID returned");
        setSubmitting(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-8rem)] bg-zinc-50 text-zinc-900">
      <main className="mx-auto max-w-xl px-6 py-10">
        <h1 className="mb-1 text-2xl font-semibold tracking-tight">New Diagnostic</h1>
        <p className="mb-8 text-sm text-zinc-500">
          Enter a business name and city. The pipeline will resolve the practice, run competitive analysis, and generate a full Revenue Intelligence Brief.
        </p>

        <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="business_name" className="mb-1 block text-sm font-medium text-zinc-700">
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
              <label htmlFor="city" className="mb-1 block text-sm font-medium text-zinc-700">
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
              <label htmlFor="state" className="mb-1 block text-sm font-medium text-zinc-700">
                State *
              </label>
              <input
                id="state"
                type="text"
                required
                value={state}
                onChange={(e) => setState(e.target.value)}
                placeholder="e.g. CA"
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>
            <div>
              <label htmlFor="website" className="mb-1 block text-sm font-medium text-zinc-700">
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
              disabled={submitting}
              className="w-full rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50"
            >
              {submitting ? "Running…" : "Run diagnostic"}
            </button>
          </form>

          {status && !error && (
            <div className="mt-4 flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
              <svg className="h-4 w-4 animate-spin flex-shrink-0" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.4 0 0 5.4 0 12h4z" />
              </svg>
              {status}
            </div>
          )}

          {error && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {error}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
