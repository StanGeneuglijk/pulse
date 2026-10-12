import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { apiFetchFor } from "@/lib/demo/DemoContext";
import { createFakeApi } from "@/lib/demo/fakeApi";

// Real users must keep making exactly the requests they made before demo
// mode existed; demo visitors must never reach the network.
describe("apiFetchFor", () => {
  const fake = createFakeApi(() => new Date());

  it("gives real users the browser's own fetch, unchanged", () => {
    expect(apiFetchFor(false, fake)).toBe(globalThis.fetch);
  });

  it("gives demo visitors the fake API, never the global fetch", () => {
    const demoFetch = apiFetchFor(true, fake);
    expect(demoFetch).toBe(fake.fetch);
    expect(demoFetch).not.toBe(globalThis.fetch);
  });
});

// A component that still calls `fetch('/api/…')` directly would, in the demo,
// hit the real server, get a 401 and bounce the visitor to /login. Every
// browser-side module must go through `useApiFetch()`; the one exception is
// logging out (user menu or the demo banner), which must clear the real
// cookie in both modes.
describe("no bare fetch in browser code", () => {
  const root = path.resolve(__dirname, "../..");
  const ALLOWED = [
    { file: "components/UserMenu.tsx", call: 'fetch("/api/auth/logout"' },
    { file: "components/DemoBanner.tsx", call: 'fetch("/api/auth/logout"' },
  ];

  function clientFiles(dir: string): string[] {
    return fs.readdirSync(path.join(root, dir), { withFileTypes: true }).flatMap((entry) => {
      const rel = path.join(dir, entry.name);
      if (entry.isDirectory()) return clientFiles(rel);
      if (!/\.tsx?$/.test(entry.name)) return [];
      const source = fs.readFileSync(path.join(root, rel), "utf8");
      return /^["']use client["']/.test(source) ? [rel] : [];
    });
  }

  it("finds the browser modules it is guarding", () => {
    const files = clientFiles("components").concat(clientFiles("lib"));
    expect(files).toContain(path.join("lib", "useDashboardData.ts"));
    expect(files).toContain(path.join("components", "MealChat.tsx"));
  });

  it("calls fetch only through useApiFetch, except the logout", () => {
    const offenders: string[] = [];
    for (const file of clientFiles("components").concat(clientFiles("lib"))) {
      const source = fs.readFileSync(path.join(root, file), "utf8");
      for (const match of source.matchAll(/(?<![\w.])fetch\([^)]*/g)) {
        const allowed = ALLOWED.some((a) => a.file === file && match[0].startsWith(a.call));
        if (!allowed) offenders.push(`${file}: ${match[0]}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
