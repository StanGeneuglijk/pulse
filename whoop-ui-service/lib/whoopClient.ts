/**
 * The sole module that talks to whoop-service — mirrors that codebase's
 * own convention of one narrow client per external dependency
 * (services/whoop/client.py's role, one layer up).
 */
import { fetchJson } from "./apiError";
import { config } from "./config";
import type { Session } from "./session";
import type {
  AuthExchangeResponse,
  CycleRecord,
  Profile,
  RecoveryRecord,
  SleepRecord,
  SyncLogEntry,
  SyncTriggerResponse,
  WorkoutRecord,
} from "./types";

function authHeaders(session: Session): HeadersInit {
  return { Authorization: `Bearer ${session.readToken}` };
}

function getUserResource<T>(session: Session, resource: string): Promise<T> {
  return fetchJson<T>(
    "whoop-service",
    `${config.whoopServiceUrl}/users/${session.userId}/${resource}`,
    { headers: authHeaders(session) }
  );
}

export const getRecovery = (s: Session) => getUserResource<RecoveryRecord[]>(s, "recovery");
export const getSleep = (s: Session) => getUserResource<SleepRecord[]>(s, "sleep");
export const getWorkout = (s: Session) => getUserResource<WorkoutRecord[]>(s, "workout");
export const getCycles = (s: Session) => getUserResource<CycleRecord[]>(s, "cycles");
export const getProfile = (s: Session) => getUserResource<Profile>(s, "profile");

export async function getSyncs(session: Session): Promise<SyncLogEntry[]> {
  return fetchJson<SyncLogEntry[]>(
    "whoop-service",
    `${config.whoopServiceUrl}/users/${session.userId}/syncs`,
    { headers: authHeaders(session) }
  );
}

export async function triggerSync(session: Session): Promise<SyncTriggerResponse> {
  return fetchJson<SyncTriggerResponse>(
    "whoop-service",
    `${config.whoopServiceUrl}/users/${session.userId}/sync`,
    { method: "POST", headers: authHeaders(session) }
  );
}

export async function checkWhoopHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${config.whoopServiceUrl}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Redeems a one-time code from whoop-service's `/auth/callback` redirect
 * for the real `{userId, readToken}` — the one call in this app that
 * runs with no session at all, since it's what creates one. Called only
 * from app/connected/route.ts, server-side; the result is written
 * straight into the session cookie and never touches client JS.
 */
export async function exchangeCode(code: string): Promise<AuthExchangeResponse> {
  return fetchJson<AuthExchangeResponse>(
    "whoop-service",
    `${config.whoopServiceUrl}/auth/exchange`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    }
  );
}
