import fs from "node:fs";
import path from "node:path";
import { NextRequest } from "next/server";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

// A demo session must never reach a backend: every app/api data route has to
// answer a demo cookie with 401 before it builds a request. The demo UI never
// calls these routes (it uses lib/demo/fakeApi.ts); this guards a visitor
// calling them by hand, e.g. with a real user's id in mind.
const demoCookie = vi.hoisted(() => {
  process.env.WHOOP_SERVICE_URL = "http://whoop.test";
  process.env.INSIGHT_SERVICE_URL = "http://insight.test";
  process.env.NUTRITION_SERVICE_URL = "http://nutrition.test";
  const value = { kind: "demo", exp: Date.now() + 3_600_000 };
  return Buffer.from(JSON.stringify(value), "utf8").toString("base64url");
});

vi.mock("next/headers", () => ({
  cookies: () => ({
    get: (name: string) => (name === "whoop_session" ? { name, value: demoCookie } : undefined),
  }),
}));

const apiDir = path.resolve(__dirname, "../../app/api");
const EXCLUDED = new Set(["health", "auth/logout"]);

function routeFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return routeFiles(full);
    return entry.name === "route.ts" ? [full] : [];
  });
}

const routes = routeFiles(apiDir)
  .map((file) => ({ file, name: path.relative(apiDir, path.dirname(file)).split(path.sep).join("/") }))
  .filter((r) => !EXCLUDED.has(r.name));

function requestFor(name: string, method: string): NextRequest {
  const url = `http://localhost:3000/api/${name}?period=weekly&days=30`;
  if (method === "GET") return new NextRequest(url);
  if (name === "nutrition/chat/audio") {
    // This route reads the form before checking the session.
    const form = new FormData();
    form.append("audio", new Blob(["x"], { type: "audio/webm" }), "recording.webm");
    return new NextRequest(url, { method, body: form });
  }
  return new NextRequest(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ period: "weekly", conversationId: "someone-elses-conversation", message: "hi" }),
  });
}

describe("every /api data route refuses a demo session", () => {
  const realFetch = globalThis.fetch;
  const fetchSpy = vi.fn(() => {
    throw new Error("a demo request reached the network");
  });
  beforeAll(() => {
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
  });
  afterAll(() => {
    globalThis.fetch = realFetch;
  });

  it("covers the real route list", () => {
    expect(routes.length).toBeGreaterThanOrEqual(17);
  });

  it.each(routes)("$name", async ({ file, name }) => {
    const mod = (await import(file)) as Record<string, (req: NextRequest) => Promise<Response> | Response>;
    const methods = ["GET", "POST", "PUT", "PATCH", "DELETE"].filter((m) => typeof mod[m] === "function");
    expect(methods.length).toBeGreaterThan(0);
    for (const method of methods) {
      const res = await mod[method](requestFor(name, method));
      expect(res.status, `${method} /api/${name}`).toBe(401);
      expect(await res.json()).toEqual({ error: "Not authenticated" });
    }
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
