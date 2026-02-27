"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ensureAskProspectBrief, getAskResults, getJobStatus, runAskQuery } from "@/lib/api";
import Button from "@/app/components/ui/Button";
import { Card, CardBody } from "@/app/components/ui/Card";
import Textarea from "@/app/components/ui/Textarea";
import { Table, THead, TH, TR, TD } from "@/app/components/ui/Table";
import EmptyState from "@/app/components/ui/EmptyState";

type AskProspect = {
  diagnostic_id?: number | null;
  place_id?: string | null;
  business_name?: string;
  city?: string;
  state?: string;
  website?: string | null;
  rating?: number;
  user_ratings_total?: number;
  opportunity_profile?: string;
  primary_leverage?: string;
};

export default function AskPage() {
  const router = useRouter();
  const [query, setQuery] = useState("Find 10 dentists in San Jose that have missing implants page");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<AskProspect[]>([]);
  const [headline, setHeadline] = useState<string | null>(null);
  const [ensuringKey, setEnsuringKey] = useState<string | null>(null);
  const [verifiedMode, setVerifiedMode] = useState(true);

  async function handleRun(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResults([]);
    setHeadline(null);
    setLoading(true);
    try {
      const start = await runAskQuery(query, verifiedMode ? "verified" : "fast");
      setMessage(start.message);

      let completed = false;
      const maxLoops = verifiedMode ? 720 : 180;
      const sleepMs = verifiedMode ? 2500 : 1500;
      for (let i = 0; i < maxLoops; i++) {
        const st = await getJobStatus(start.job_id);
        const progress = (st.progress || {}) as Record<string, unknown>;
        const phase = String(progress.phase || "running");
        const p = (progress.progress || {}) as Record<string, unknown>;
        const candidates = Number(p.candidates_found || 0);
        const scored = Number(p.scored || 0);
        const listed = Number(p.list_count || 0);
        const verifying = Number(p.verifying || 0);
        const verifiedProcessed = Number(p.processed || p.verified_processed || 0);
        if (verifiedMode && (phase === "verified_diagnostic" || verifying > 0)) {
          setMessage(`Verifying accuracy · ${verifiedProcessed}/${verifying || "?"} checked, ${listed} confirmed matches`);
        } else {
          setMessage(`${phase.replaceAll("_", " ")} · Found ${candidates}, scored ${scored}, listed ${listed}`);
        }

        const partial = Array.isArray(progress.partial_results) ? (progress.partial_results as AskProspect[]) : [];
        if (partial.length > 0) {
          setResults(partial);
        }

        if (st.status === "completed") {
          completed = true;
          break;
        }
        if (st.status === "failed") throw new Error(st.error || "Request failed");
        await new Promise((r) => setTimeout(r, sleepMs));
      }

      if (!completed) throw new Error("Ask query timed out");

      const out = await getAskResults(start.job_id);
      const result = out.result || {};
      const prospects = Array.isArray((result as Record<string, unknown>).prospects)
        ? ((result as Record<string, unknown>).prospects as AskProspect[])
        : [];
      setResults(prospects);
      const total = Number((result as Record<string, unknown>).total_matches || prospects.length);
      const intent = (result as Record<string, unknown>).intent as Record<string, unknown> | undefined;
      setHeadline(
        `Found ${total} matches${intent?.city ? ` in ${String(intent.city)}${intent?.state ? `, ${String(intent.state)}` : ""}` : ""}.`,
      );
      setMessage(verifiedMode ? "Done. Verified matches only." : "Done.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run request");
    } finally {
      setLoading(false);
    }
  }

  async function onViewBrief(row: AskProspect) {
    if (row.diagnostic_id) {
      router.push(`/diagnostic/${row.diagnostic_id}`);
      return;
    }

    const key = `${row.place_id || ""}-${row.business_name || ""}`;
    setEnsuringKey(key);
    setError(null);
    try {
      const ensure = await ensureAskProspectBrief({
        place_id: row.place_id,
        business_name: row.business_name || "",
        city: row.city || "",
        state: row.state || "",
        website: row.website,
      });
      if (ensure.status === "ready" && ensure.diagnostic_id) {
        router.push(`/diagnostic/${ensure.diagnostic_id}`);
        return;
      }
      if (!ensure.job_id) throw new Error("Failed to start brief build");

      setMessage("Building your brief...");
      for (let i = 0; i < 240; i++) {
        const st = await getJobStatus(ensure.job_id);
        if (st.status === "completed" && st.diagnostic_id) {
          router.push(`/diagnostic/${st.diagnostic_id}`);
          return;
        }
        if (st.status === "failed") throw new Error(st.error || "Brief build failed");
        await new Promise((r) => setTimeout(r, 2000));
      }
      throw new Error("Brief build timed out");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to build brief");
    } finally {
      setEnsuringKey(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="display-title text-3xl font-black tracking-tight">Ask Neyma</h1>
      <p className="mt-1 text-sm text-[var(--text-muted)]">Describe exactly what you want and Neyma will return a shortlist. Use verified mode for service-page accuracy.</p>

      <Card className="mt-5">
        <CardBody>
          <form onSubmit={handleRun} className="space-y-3">
            <Textarea
              label="Request"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={3}
              placeholder="Find 10 dentists in San Jose that have missing implants page"
            />
            <div className="flex items-center gap-3">
              <Button
                type="submit"
                disabled={loading}
                variant="primary"
              >
                {loading ? "Finding prospects..." : "Run query"}
              </Button>
              <Link href="/territory/new" className="text-sm app-link">
                Or run a structured territory scan
              </Link>
            </div>
            <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={verifiedMode}
                onChange={(e) => setVerifiedMode(e.target.checked)}
                className="h-4 w-4 rounded border-[var(--border-default)]"
              />
              Extreme accuracy (verified mode, slower)
            </label>
            {verifiedMode && (
              <p className="text-xs text-[var(--text-muted)]">
                For queries like “no implants page,” Neyma validates with deep diagnostics and may take 10-25 minutes.
              </p>
            )}
            {message && <p className="text-sm text-[var(--text-secondary)]">{message}</p>}
            {error && <p className="text-sm text-red-600">{error}</p>}
          </form>
        </CardBody>
      </Card>

      {headline && <p className="mt-5 text-sm text-[var(--text-secondary)]">{headline}</p>}

      {results.length > 0 ? (
        <Card className="mt-3">
          <Table>
            <THead>
              <tr>
                <TH>Business</TH>
                <TH>City</TH>
                <TH>Rating</TH>
                <TH>Reviews</TH>
                <TH>Signal</TH>
                <TH className="text-right">Action</TH>
              </tr>
            </THead>
            <tbody>
              {results.map((r, i) => {
                const key = `${r.place_id || ""}-${r.business_name || ""}`;
                return (
                  <TR key={`${r.diagnostic_id || i}-${r.business_name || ""}`}>
                    <TD className="font-medium text-[var(--text-primary)]">{r.business_name || "—"}</TD>
                    <TD>{r.city || "—"}{r.state ? `, ${r.state}` : ""}</TD>
                    <TD>{r.rating ?? "—"}</TD>
                    <TD>{r.user_ratings_total ?? "—"}</TD>
                    <TD>{r.primary_leverage || r.opportunity_profile || "—"}</TD>
                    <TD className="text-right">
                      {r.diagnostic_id ? (
                        <Link href={`/diagnostic/${r.diagnostic_id}`} className="app-link font-medium">
                          View brief
                        </Link>
                      ) : (
                        <button
                          onClick={() => void onViewBrief(r)}
                          className="app-link font-medium disabled:opacity-60"
                          disabled={ensuringKey === key}
                        >
                          {ensuringKey === key ? "Building brief..." : "View brief"}
                        </button>
                      )}
                    </TD>
                  </TR>
                );
              })}
            </tbody>
          </Table>
        </Card>
      ) : (
        !loading && !error && <div className="mt-4"><EmptyState title="No results yet" description="Run a query above to find prospects matching your criteria." /></div>
      )}
    </div>
  );
}
