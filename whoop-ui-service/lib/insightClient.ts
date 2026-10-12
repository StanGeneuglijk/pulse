/**
 * The sole module that talks to whoop-insight-service.
 */
import { fetchJson } from "./apiError";
import { config } from "./config";
import type { Session } from "./session";
import type { InsightPeriod, InsightRecord, InsightUsage } from "./types";

function authHeaders(session: Session): HeadersInit {
  return { Authorization: `Bearer ${session.readToken}` };
}

export async function generateInsight(
  session: Session,
  period: InsightPeriod
): Promise<InsightRecord> {
  return fetchJson<InsightRecord>(
    "whoop-insight-service",
    `${config.insightServiceUrl}/insights/generate/${session.userId}?period=${period}`,
    { method: "POST", headers: authHeaders(session) }
  );
}

export async function getLatestInsight(
  session: Session,
  period: InsightPeriod
): Promise<InsightRecord | null> {
  try {
    return await fetchJson<InsightRecord>(
      "whoop-insight-service",
      `${config.insightServiceUrl}/insights/${session.userId}/latest?period=${period}`,
      { headers: authHeaders(session) }
    );
  } catch (err) {
    if (err instanceof Error && "status" in err && (err as { status: number }).status === 404) {
      return null;
    }
    throw err;
  }
}

export async function listInsights(
  session: Session,
  period: InsightPeriod
): Promise<InsightRecord[]> {
  return fetchJson<InsightRecord[]>(
    "whoop-insight-service",
    `${config.insightServiceUrl}/insights/${session.userId}?period=${period}`,
    { headers: authHeaders(session) }
  );
}

// A user's own read_token can never call the operator-only
// GET /insights/spend (platform-wide total) — their own usage,
// including their own share of spend, is the per-user equivalent.
export async function getUsage(session: Session): Promise<InsightUsage> {
  return fetchJson<InsightUsage>(
    "whoop-insight-service",
    `${config.insightServiceUrl}/insights/${session.userId}/usage`,
    { headers: authHeaders(session) }
  );
}

export async function checkInsightHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${config.insightServiceUrl}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}
