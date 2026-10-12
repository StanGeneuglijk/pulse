/**
 * Per-user identity for this app. Replaces the old single, server-config
 * `WHOOP_USER_ID` + operator API keys — this app now serves whoever is
 * actually logged in, and every backend call is made as that specific
 * person, using the same `read_token` whoop-service already issues
 * through its own WHOOP-connect flow (see app/connected/route.ts).
 *
 * The cookie is plain base64, not signed or encrypted. That's a
 * deliberate call, not an oversight: the cookie is `httpOnly` (never
 * readable from client JS) and only ever sent same-origin, but even a
 * user who edits their own cookie via devtools gains nothing — every
 * backend call still re-validates `readToken` against `userId`
 * server-side (`require_user_access`/`require_conversation_owner`), so
 * a tampered cookie just breaks that person's own session, never
 * another user's. The cookie is a convenience carrier for a credential
 * the backend independently authorizes on every request, not the
 * authority itself.
 */
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { DEMO_SESSION_HOURS } from "./demo/data";

export interface Session {
  userId: string;
  readToken: string;
}

/**
 * Who is looking at the page. A demo visitor has no `userId` and no
 * `readToken`: the cookie only says "demo, until exp". `getSession()` and
 * `requireSession()` never return a demo, so every app/api/* route answers a
 * demo cookie with 401 before it can build a backend request.
 */
export type Caller = { kind: "user"; session: Session } | { kind: "demo" } | null;

const COOKIE_NAME = "whoop_session";
// 30 days — read_token has no separate expiry of its own (whoop-service
// issues it once, at connect time), so this cookie's own lifetime is the
// only thing bounding how long a browser stays "logged in."
const MAX_AGE_SECONDS = 60 * 60 * 24 * 30;
const DEMO_MAX_AGE_SECONDS = 60 * 60 * DEMO_SESSION_HOURS;

export class UnauthenticatedError extends Error {
  constructor() {
    super("Not authenticated");
  }
}

function encodeSession(value: Session | { kind: "demo"; exp: number }): string {
  return Buffer.from(JSON.stringify(value), "utf8").toString("base64url");
}

/** Reads the session cookie. Null if missing, malformed, corrupted or an
 * expired demo — a broken cookie is just "not logged in," never a server
 * error. A value with `kind: "demo"` is only ever a demo, whatever else it
 * carries; a value without `kind` is a real session (cookies set before demo
 * mode existed have none). */
export function getCaller(): Caller {
  const raw = cookies().get(COOKIE_NAME)?.value;
  if (!raw) return null;
  try {
    const parsed = JSON.parse(Buffer.from(raw, "base64url").toString("utf8"));
    if (parsed?.kind === "demo") {
      return typeof parsed.exp === "number" && parsed.exp > Date.now() ? { kind: "demo" } : null;
    }
    if (typeof parsed?.userId === "string" && typeof parsed?.readToken === "string") {
      return { kind: "user", session: { userId: parsed.userId, readToken: parsed.readToken } };
    }
  } catch {
    // fall through
  }
  return null;
}

/** The real session, or null — never a demo. */
export function getSession(): Session | null {
  const caller = getCaller();
  return caller?.kind === "user" ? caller.session : null;
}

/** For app/api/* route handlers: the same session, or a typed error
 * `lib/apiError.ts`'s `handleRoute` maps to a real 401. */
export function requireSession(): Session {
  const session = getSession();
  if (!session) throw new UnauthenticatedError();
  return session;
}

export function attachSessionCookie(response: NextResponse, session: Session): void {
  response.cookies.set(COOKIE_NAME, encodeSession(session), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
}

/** Starts (or restarts) a demo: no credential, just an expiry. */
export function attachDemoCookie(response: NextResponse): void {
  const value = { kind: "demo" as const, exp: Date.now() + DEMO_MAX_AGE_SECONDS * 1000 };
  response.cookies.set(COOKIE_NAME, encodeSession(value), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: DEMO_MAX_AGE_SECONDS,
  });
}

export function clearSessionCookie(response: NextResponse): void {
  response.cookies.set(COOKIE_NAME, "", { path: "/", maxAge: 0 });
}
