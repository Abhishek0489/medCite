// MedCite frontend API client.
// Talks to the FastAPI backend defined in PROJECT_SPEC.md §6.
// Both endpoints return the same response shape; only `tier` differs.

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

async function postQuery(path, query, { signal } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
    signal,
  });

  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.detail || JSON.stringify(body);
    } catch {
      detail = await res.text().catch(() => "");
    }
    const err = new Error(
      `Backend ${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`
    );
    err.status = res.status;
    throw err;
  }

  return res.json();
}

export function queryLocal(query, opts) {
  return postQuery("/query/local", query, opts);
}

export function queryLive(query, opts) {
  return postQuery("/query/live", query, opts);
}

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed (${res.status})`);
  return res.json();
}

export const apiBase = API_BASE;
