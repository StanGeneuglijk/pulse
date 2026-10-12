import { NextRequest } from "next/server";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const jar = vi.hoisted(() => {
  process.env.WHOOP_SERVICE_URL = "http://whoop.test";
  process.env.INSIGHT_SERVICE_URL = "http://insight.test";
  process.env.NUTRITION_SERVICE_URL = "http://nutrition.test";
  return new Map<string, string>();
});

vi.mock("next/headers", () => ({
  cookies: () => ({
    get: (name: string) => (jar.has(name) ? { name, value: jar.get(name)! } : undefined),
  }),
}));

vi.mock("next/navigation", () => ({
  redirect: (url: string) => {
    throw new Error(`REDIRECT ${url}`);
  },
}));

vi.mock("@/components/Dashboard", () => ({
  Dashboard: function Dashboard() {
    return null;
  },
}));

import { POST as logout } from "@/app/api/auth/logout/route";
import { GET as connect } from "@/app/demo/connect/route";
import { GET as start } from "@/app/demo/start/route";
import LoginPage from "@/app/login/page";
import Page from "@/app/page";

const COOKIE = "whoop_session";
const encode = (v: unknown) => Buffer.from(JSON.stringify(v), "utf8").toString("base64url");
const decode = (s: string) => JSON.parse(Buffer.from(s, "base64url").toString("utf8"));

function request(path: string) {
  return new NextRequest(`http://localhost:3000${path}`, { headers: { host: "localhost:3000" } });
}

function redirectOf(fn: () => unknown): string | null {
  try {
    fn();
  } catch (err) {
    const match = /^REDIRECT (.*)$/.exec((err as Error).message);
    if (match) return match[1];
    throw err;
  }
  return null;
}

const real = () => jar.set(COOKIE, encode({ userId: "u1", readToken: "t1" }));
const demo = () => jar.set(COOKIE, encode({ kind: "demo", exp: Date.now() + 3_600_000 }));

beforeEach(() => jar.clear());

describe("start", () => {
  it("keeps a real user on their own dashboard and leaves their cookie alone", () => {
    real();
    const res = start(request("/demo/start"));
    expect(res.status).toBe(307);
    expect(new URL(res.headers.get("location")!).pathname).toBe("/");
    expect(res.cookies.get(COOKIE)).toBeUndefined();
  });

  it.each([
    ["no session", () => undefined],
    ["a demo session", demo],
  ])("starts a fresh demo from %s, in one click", (_label, setup) => {
    setup();
    const res = start(request("/demo/start"));
    expect(res.status).toBe(307);
    const location = new URL(res.headers.get("location")!);
    expect(location.pathname + location.search).toBe("/?demo=started");
    const value = decode(res.cookies.get(COOKIE)!.value);
    expect(value.kind).toBe("demo");
    expect(value).not.toHaveProperty("readToken");
  });
});

describe("connect", () => {
  it("ends the demo and starts the real WHOOP connect flow", () => {
    demo();
    const res = connect();
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe("http://whoop.test/auth/login");
    const cookie = res.cookies.get(COOKIE)!;
    expect(cookie.value).toBe("");
    expect(cookie.maxAge).toBe(0);
  });
});

describe("pages", () => {
  it("renders the real dashboard for a real user", () => {
    real();
    const el = Page({ searchParams: {} }) as { props: { demo?: boolean } };
    expect(el.props.demo).toBeFalsy();
  });

  it("renders the dashboard in demo mode for a demo visitor", () => {
    demo();
    const el = Page({ searchParams: { demo: "started" } }) as { props: { demo?: boolean } };
    expect(el.props.demo).toBe(true);
  });

  it("sends a visitor with no session to the landing page", () => {
    expect(redirectOf(() => Page({ searchParams: {} }))).toBe("/login");
  });

  it("explains that the demo needs cookies when the cookie didn't stick", () => {
    expect(redirectOf(() => Page({ searchParams: { demo: "started" } }))).toBe(
      "/login?error=cookies_blocked"
    );
    const html = renderToStaticMarkup(LoginPage({ searchParams: { error: "cookies_blocked" } }));
    expect(html).toContain("The demo needs cookies");
  });

  it("offers Try the demo next to Connect WHOOP on the landing page", () => {
    const html = renderToStaticMarkup(LoginPage({ searchParams: {} }));
    expect(html).toContain("Try the demo");
    expect(html).toContain('href="/demo/start"');
    expect(html).toContain("Connect WHOOP");
  });

  it.each([
    ["a real user", real],
    ["a demo visitor", demo],
  ])("sends %s from the landing page to the dashboard", (_label, setup) => {
    setup();
    expect(redirectOf(() => LoginPage({ searchParams: {} }))).toBe("/");
  });
});

describe("leave", () => {
  it("clears the demo cookie, after which / goes back to the landing page", async () => {
    demo();
    const res = await logout();
    const cookie = res.cookies.get(COOKIE)!;
    expect(cookie.value).toBe("");
    expect(cookie.maxAge).toBe(0);
    jar.delete(COOKIE); // what the browser does with a maxAge=0 cookie
    expect(redirectOf(() => Page({ searchParams: {} }))).toBe("/login");
  });
});
