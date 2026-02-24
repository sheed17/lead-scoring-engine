const getBaseUrl = () =>
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function checkHealth(): Promise<{ status: string }> {
  const res = await fetch(`${getBaseUrl()}/health`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function runDiagnostic(
  body: { business_name: string; city: string; website?: string }
): Promise<import("./types").DiagnosticResponse> {
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
