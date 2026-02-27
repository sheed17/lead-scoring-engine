"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createTerritoryScan } from "@/lib/api";
import Button from "@/app/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/app/components/ui/Card";
import Input from "@/app/components/ui/Input";
import EmptyState from "@/app/components/ui/EmptyState";

export default function NewTerritoryPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [city, setCity] = useState(searchParams.get("city") || "");
  const [state, setState] = useState(searchParams.get("state") || "");
  const [vertical, setVertical] = useState(searchParams.get("vertical") || "dentist");
  const [limit, setLimit] = useState(20);
  const [belowReviewAvg, setBelowReviewAvg] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setRunning(true);
    try {
      const res = await createTerritoryScan({
        city: city.trim(),
        state: state.trim() || undefined,
        vertical,
        limit,
        filters: { below_review_avg: belowReviewAvg || undefined },
      });
      router.push(`/territory/${res.scan_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run territory scan");
      setRunning(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-semibold tracking-tight">Run Territory Scan</h1>
      <p className="mt-1 text-sm text-[var(--text-muted)]">Build a ranked local market list from structured inputs.</p>

      <Card className="mt-5">
        <CardHeader title="Scan Setup" subtitle="Define market, vertical, and scan size." />
        <CardBody>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input label="City *" value={city} onChange={(e) => setCity(e.target.value)} required placeholder="Austin" />
            <Input label="State" value={state} onChange={(e) => setState(e.target.value)} placeholder="TX" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-[var(--text-secondary)]">Vertical</span>
                <select
                  value={vertical}
                  onChange={(e) => setVertical(e.target.value)}
                  className="h-10 w-full rounded-[var(--radius-md)] border border-[var(--border-default)] px-3 text-sm focus:border-[var(--accent)] focus:outline-none"
                >
                  <option value="dentist">Dentist</option>
                  <option value="dental">Dental</option>
                  <option value="orthodontist">Orthodontist</option>
                </select>
              </label>
              <Input label="Limit" type="number" min={1} max={100} value={limit} onChange={(e) => setLimit(Number(e.target.value || 20))} />
            </div>
            <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <input type="checkbox" checked={belowReviewAvg} onChange={(e) => setBelowReviewAvg(e.target.checked)} />
              Below review average
            </label>
            <p className="text-xs text-[var(--text-muted)]">For service-gap criteria, use Ask Neyma natural-language flow.</p>
            <div className="pt-1">
              <Button type="submit" variant="primary" disabled={running}>
                {running ? "Running..." : "Run scan"}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>

      {error && <div className="mt-4"><EmptyState title="Scan failed" description={error} /></div>}
    </div>
  );
}
