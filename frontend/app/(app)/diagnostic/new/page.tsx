"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { pollUntilDone, submitDiagnostic } from "@/lib/api";
import type { JobStatusResponse } from "@/lib/types";
import Button from "@/app/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/app/components/ui/Card";
import Input from "@/app/components/ui/Input";

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
      setStatus("Pipeline running...");
      const result: JobStatusResponse = await pollUntilDone(job_id, (s) => {
        if (s.status === "running") setStatus("Analyzing market and service signals...");
      });
      if (result.status === "failed") throw new Error(result.error || "Diagnostic failed");
      if (!result.diagnostic_id) throw new Error("No diagnostic ID returned");
      router.push(`/diagnostic/${result.diagnostic_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight">New Diagnostic</h1>
      <p className="mt-1 text-sm text-[var(--text-muted)]">Run a full single-business brief from structured inputs.</p>

      <Card className="mt-5">
        <CardHeader title="Diagnostic Input" />
        <CardBody>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input label="Business name *" required value={businessName} onChange={(e) => setBusinessName(e.target.value)} placeholder="Japantown Dental" />
            <Input label="City *" required value={city} onChange={(e) => setCity(e.target.value)} placeholder="San Jose" />
            <Input label="State *" required value={state} onChange={(e) => setState(e.target.value)} placeholder="CA" />
            <Input label="Website (optional)" value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="japantowndental.com" />
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? "Running..." : "Run diagnostic"}
            </Button>
          </form>
          {status && !error && <p className="mt-3 text-sm text-[var(--text-secondary)]">{status}</p>}
          {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
        </CardBody>
      </Card>
    </div>
  );
}
