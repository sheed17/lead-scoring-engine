import type {
  DiagnosticResponse,
  JobSubmitResponse,
  JobStatusResponse,
  DiagnosticListResponse,
} from "./types";

const getBaseUrl = () =>
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function checkHealth(): Promise<{ status: string }> {
  const res = await fetch(`${getBaseUrl()}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function submitDiagnostic(body: {
  business_name: string;
  city: string;
  state: string;
  website?: string;
}): Promise<JobSubmitResponse> {
  const res = await fetch(`${getBaseUrl()}/diagnostic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(`${getBaseUrl()}/jobs/${jobId}`, { cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export async function pollUntilDone(
  jobId: string,
  onStatus?: (s: JobStatusResponse) => void,
  intervalMs = 2000,
  maxAttempts = 150,
): Promise<JobStatusResponse> {
  for (let i = 0; i < maxAttempts; i++) {
    const status = await getJobStatus(jobId);
    onStatus?.(status);
    if (status.status === "completed" || status.status === "failed") return status;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Job timed out");
}

export async function listDiagnostics(
  limit = 50,
  offset = 0,
): Promise<DiagnosticListResponse> {
  const res = await fetch(
    `${getBaseUrl()}/diagnostics?limit=${limit}&offset=${offset}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error("Failed to load diagnostics");
  return res.json();
}

export async function getDiagnostic(id: number): Promise<DiagnosticResponse> {
  const res = await fetch(`${getBaseUrl()}/diagnostics/${id}`, { cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export async function deleteDiagnostic(id: number): Promise<void> {
  const res = await fetch(`${getBaseUrl()}/diagnostics/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete diagnostic");
}

export async function recordOutcome(body: {
  diagnostic_id: number;
  outcome_type: string;
  outcome_data: Record<string, unknown>;
}): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${getBaseUrl()}/outcomes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export async function getCalibrationStats(): Promise<Record<string, unknown>> {
  const res = await fetch(`${getBaseUrl()}/outcomes/calibration`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch calibration stats");
  return res.json();
}

export async function getOutcomes(diagnosticId: number): Promise<Array<Record<string, unknown>>> {
  const res = await fetch(`${getBaseUrl()}/outcomes/${diagnosticId}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch outcomes");
  return res.json();
}
