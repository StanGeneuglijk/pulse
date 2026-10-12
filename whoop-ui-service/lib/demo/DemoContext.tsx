"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { createFakeApi, type FakeApi } from "./fakeApi";

/**
 * The one seam between the dashboard and demo mode. Components get their
 * fetch function from `useApiFetch()`: real users get the browser's own
 * `fetch`, demo visitors get this page load's fake API. Demo code is imported
 * statically on purpose (a lazily loaded chunk can vanish on a redeploy and
 * leave a demo visitor on the loading skeleton).
 */

interface DemoState {
  demo: boolean;
  fake: FakeApi | null;
}

const DemoContext = createContext<DemoState>({ demo: false, fake: null });

export function apiFetchFor(demo: boolean, fake: FakeApi | null): typeof fetch {
  return demo && fake ? fake.fetch : globalThis.fetch;
}

export function DemoProvider({ demo, children }: { demo: boolean; children: ReactNode }) {
  const [fake] = useState(() => (demo ? createFakeApi(() => new Date()) : null));
  return <DemoContext.Provider value={{ demo, fake }}>{children}</DemoContext.Provider>;
}

export function useDemo(): boolean {
  return useContext(DemoContext).demo;
}

export function useApiFetch(): typeof fetch {
  const { demo, fake } = useContext(DemoContext);
  return apiFetchFor(demo, fake);
}
