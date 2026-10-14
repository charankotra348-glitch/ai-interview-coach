/** Browser-side helper for calling our own Next.js API routes. */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public retryable = false,
  ) {
    super(message);
  }
}

type ValidationIssue = { loc?: (string | number)[]; msg?: string };

/** Turns any backend error shape into one ApiError with a readable message. */
export function toApiError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc: ["body", "password"], msg: "..."}]
    const message = (detail as ValidationIssue[])
      .map((issue) => `${issue.loc?.at(-1) ?? "input"}: ${issue.msg ?? "invalid"}`)
      .join("; ");
    return new ApiError(status, "invalid_input", message);
  }
  if (detail && typeof detail === "object") {
    const d = detail as { code?: string; message?: string; retryable?: boolean };
    return new ApiError(status, d.code ?? "error", d.message ?? "Something went wrong.", Boolean(d.retryable));
  }
  return new ApiError(status, "error", "Something went wrong. Please try again.");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, init);
  const body = await response.json().catch(() => null);
  if (response.status === 401 && path.startsWith("/api/backend/")) {
    // The session expired: go to login and come back here afterwards. A full page load is
    // deliberate here: it clears everything the page held in memory for the old session.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
  }
  if (!response.ok) throw toApiError(response.status, body);
  return body as T;
}

export function postJson<T>(path: string, data: unknown): Promise<T> {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

/** Only allow redirects to our own pages, never to another site (an "open redirect"). */
export function safeNext(next: string | null, fallback = "/dashboard"): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : fallback;
}