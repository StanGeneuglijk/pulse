import { NextResponse } from "next/server";
import { UnauthenticatedError } from "./session";

/**
 * Thrown by whoopClient/insightClient on any non-2xx response. Carries
 * the upstream status through so an API route can forward it rather
 * than flattening every failure into a generic 500 — the same "don't
 * silently swallow a domain-specific failure" principle the Python
 * services' own exception -> HTTP mapping follows.
 */
export class UpstreamApiError extends Error {
  status: number;
  body: string;

  constructor(service: string, status: number, body: string) {
    super(readableDetail(body) ?? `${service} responded ${status}`);
    this.status = status;
    this.body = body;
  }
}

// FastAPI errors are {"detail": "..."} (or a validation list); surface the
// sentence itself rather than the raw body.
function readableDetail(body: string): string | null {
  try {
    const detail = JSON.parse(body)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return detail[0].msg;
  } catch {
    // not JSON
  }
  return null;
}

export async function fetchJson<T>(
  service: string,
  url: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store" });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new UpstreamApiError(service, response.status, body);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/**
 * Every app/api/* route handler is one call to an upstream client
 * wrapped in this — the route itself stays pure routing/serialization,
 * same "no business logic here" contract api/main.py holds itself to.
 */
export async function handleRoute(fn: () => Promise<unknown>): Promise<NextResponse> {
  try {
    const result = await fn();
    return NextResponse.json(result ?? {});
  } catch (err) {
    if (err instanceof UnauthenticatedError) {
      return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
    }
    if (err instanceof UpstreamApiError) {
      return NextResponse.json({ error: err.message }, { status: err.status });
    }
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
