import { NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const jar = vi.hoisted(() => new Map<string, string>());

vi.mock("next/headers", () => ({
  cookies: () => ({
    get: (name: string) => (jar.has(name) ? { name, value: jar.get(name)! } : undefined),
  }),
}));

import {
  UnauthenticatedError,
  attachDemoCookie,
  getCaller,
  getSession,
  requireSession,
} from "@/lib/session";

const COOKIE = "whoop_session";
const HOUR = 60 * 60 * 1000;

function setCookie(value: unknown) {
  jar.set(COOKIE, Buffer.from(JSON.stringify(value), "utf8").toString("base64url"));
}

beforeEach(() => jar.clear());

describe("real session unchanged", () => {
  it("reads a legacy cookie without kind as a real user", () => {
    setCookie({ userId: "u1", readToken: "t1" });
    expect(getSession()).toEqual({ userId: "u1", readToken: "t1" });
    expect(getCaller()).toEqual({ kind: "user", session: { userId: "u1", readToken: "t1" } });
  });

  it("treats no cookie as no caller", () => {
    expect(getCaller()).toBeNull();
    expect(getSession()).toBeNull();
  });
});

describe("demo session", () => {
  it("reads a live demo cookie as a demo caller, never as a real session", () => {
    setCookie({ kind: "demo", exp: Date.now() + HOUR });
    expect(getCaller()).toEqual({ kind: "demo" });
    expect(getSession()).toBeNull();
    expect(() => requireSession()).toThrow(UnauthenticatedError);
  });

  it("never treats a demo value as real, even if it carries credentials", () => {
    setCookie({ kind: "demo", exp: Date.now() + HOUR, userId: "u1", readToken: "t1" });
    expect(getSession()).toBeNull();
    expect(getCaller()).toEqual({ kind: "demo" });
  });

  it("reads an expired demo cookie as no session", () => {
    setCookie({ kind: "demo", exp: Date.now() - 1 });
    expect(getCaller()).toBeNull();
  });

  it("reads malformed cookies as no session", () => {
    jar.set(COOKIE, "not-base64-json");
    expect(getCaller()).toBeNull();
    setCookie({ kind: "demo" });
    expect(getCaller()).toBeNull();
  });

  it("attaches a 24-hour httpOnly demo cookie with no credential in it", () => {
    const now = Date.now();
    const response = NextResponse.json({});
    attachDemoCookie(response);
    const cookie = response.cookies.get(COOKIE)!;
    expect(cookie.httpOnly).toBe(true);
    expect(cookie.sameSite).toBe("lax");
    expect(cookie.path).toBe("/");
    expect(cookie.maxAge).toBe(24 * 60 * 60);
    const value = JSON.parse(Buffer.from(cookie.value, "base64url").toString("utf8"));
    expect(value.kind).toBe("demo");
    expect(value.exp).toBeGreaterThanOrEqual(now + 24 * HOUR - 1000);
    expect(value.exp).toBeLessThanOrEqual(Date.now() + 24 * HOUR);
    expect(value).not.toHaveProperty("userId");
    expect(value).not.toHaveProperty("readToken");
  });
});
