/**
 * A browser-side fake of this app's own /api routes, used only in the demo.
 * Components call it through `useApiFetch()` exactly as they would call
 * `fetch`, so the dashboard renders the sample person through the same code
 * paths as real data, and a demo visit never touches the network.
 *
 * One instance per page load: its state (confirmed meals, a goal edit, the
 * last pretend sync) lives in memory and is gone on reload. Unknown paths
 * throw, so a real /api route without a demo counterpart fails loudly in
 * tests/demo/fakeApi.test.ts instead of quietly in front of a visitor.
 */
import type {
  ChatResponse,
  InsightPeriod,
  InsightUsage,
  MealProposal,
  NutritionGoal,
  NutritionLogRecord,
  SetGoalBody,
} from "../types";
import {
  DEMO_CHAT_DELAY_MS,
  DEMO_INSIGHT_DELAY_MS,
  DEMO_MODEL_NAME,
  DEMO_SYNC_DELAY_MS,
  DEMO_USER_ID,
  generateDemoData,
} from "./data";
import { DEMO_REPLAY_NOTE, exampleInsight, exampleMealChat } from "./script";

export interface FakeRequest {
  url: URL;
  body: unknown;
  now: Date;
}

type Handler = (request: FakeRequest) => unknown | Promise<unknown>;

export interface FakeApi {
  fetch: typeof fetch;
  /** True when the fake answers this method + pathname (e.g. "GET", "/api/whoop/recovery"). */
  handles: (method: string, path: string) => boolean;
}

function readBody(init: RequestInit | undefined): unknown {
  const body = init?.body;
  if (typeof body === "string") {
    try {
      return JSON.parse(body);
    } catch {
      return body;
    }
  }
  return body ?? null;
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

function field(body: unknown, key: string): string | null {
  if (body instanceof FormData) {
    const v = body.get(key);
    return typeof v === "string" ? v : null;
  }
  if (body && typeof body === "object" && key in body) {
    const v = (body as Record<string, unknown>)[key];
    return typeof v === "string" ? v : null;
  }
  return null;
}

function logRecord(id: string, conversationId: string, meal: MealProposal, at: Date): NutritionLogRecord {
  return {
    id,
    userId: DEMO_USER_ID,
    conversationId,
    description: meal.description,
    loggedAt: at.toISOString(),
    calories: meal.totalCalories,
    proteinG: meal.totalProteinG,
    carbsG: meal.totalCarbsG,
    fatG: meal.totalFatG,
    fiberG: meal.fiberG,
    sugarG: meal.sugarG,
    sodiumMg: meal.sodiumMg,
    modelName: DEMO_MODEL_NAME,
    createdAt: at.toISOString(),
  };
}

function periodOf(url: URL): InsightPeriod {
  const p = url.searchParams.get("period");
  return p === "daily" || p === "monthly" ? p : "weekly";
}

export function createFakeApi(clock: () => Date): FakeApi {
  // What the visitor did this page load. Confirmed meals keep the moment they
  // were confirmed, so after midnight they stay on the day they were logged.
  const pending = new Map<string, MealProposal>();
  const confirmed: NutritionLogRecord[] = [];
  let goalOverride: NutritionGoal | null = null;
  let lastSync: Date | null = null;
  let generated = 0;
  let nextId = 0;

  // Rebuilt on every read, so a tab left open past midnight moves to the new
  // day on its next refresh; this page load's changes are applied on top.
  const view = (at: Date) => {
    const data = generateDemoData(at);
    return {
      ...data,
      meals: [...data.meals, ...confirmed],
      goal: goalOverride ?? data.goal,
      syncs: lastSync
        ? [{ ...data.syncs[0], triggerSource: "manual", createdAt: lastSync.toISOString() }]
        : data.syncs,
    };
  };

  async function chat(body: unknown, now: Date, spoken: boolean): Promise<ChatResponse> {
    await wait(DEMO_CHAT_DELAY_MS);
    const example = exampleMealChat(now);
    const conversationId = field(body, "conversationId") ?? `demo-conv-${++nextId}`;
    pending.set(conversationId, example.proposal);
    return {
      conversationId,
      reply: DEMO_REPLAY_NOTE + example.reply,
      pendingMeal: example.proposal,
      ...(spoken ? { transcript: example.transcript } : {}),
    };
  }

  const routes: Record<string, Handler> = {
    "GET /api/whoop/recovery": ({ now }) => view(now).recovery,
    "GET /api/whoop/sleep": ({ now }) => view(now).sleep,
    "GET /api/whoop/workout": ({ now }) => view(now).workouts,
    "GET /api/whoop/cycles": ({ now }) => view(now).cycles,
    "GET /api/whoop/profile": ({ now }) => view(now).profile,
    "GET /api/whoop/syncs": ({ now }) => view(now).syncs,
    "GET /api/nutrition/meals/list": ({ url, now }) => {
      const days = Number(url.searchParams.get("days") ?? 30);
      const since = now.getTime() - days * 24 * 3_600_000;
      return view(now).meals.filter((m) => new Date(m.loggedAt).getTime() >= since);
    },
    "GET /api/nutrition/goal": ({ now }) => view(now).goal,
    "GET /api/insight/latest": ({ url, now }) => exampleInsight(periodOf(url), now),
    "GET /api/insight/list": ({ url, now }) => [exampleInsight(periodOf(url), now)],
    "GET /api/insight/usage": ({ now }): InsightUsage => ({
      generatedByPeriod: { daily: 1, weekly: 1, monthly: 1 },
      activityCount: 0,
      spendUsd: 0,
      totalGenerated: 3 + generated,
      lastGeneratedAt: exampleInsight("daily", now).createdAt,
    }),
    "POST /api/insight/generate": async ({ body, now }) => {
      await wait(DEMO_INSIGHT_DELAY_MS);
      generated++;
      const p = field(body, "period");
      return exampleInsight(p === "daily" || p === "monthly" ? p : "weekly", now);
    },
    "POST /api/nutrition/chat": ({ body, now }) => chat(body, now, false),
    "POST /api/nutrition/chat/audio": ({ body, now }) => chat(body, now, true),
    "POST /api/nutrition/meals/confirm": ({ body, now }) => {
      const conversationId = field(body, "conversationId") ?? `demo-conv-${++nextId}`;
      const meal = pending.get(conversationId) ?? exampleMealChat(now).proposal;
      pending.delete(conversationId);
      const record = logRecord(`demo-logged-${++nextId}`, conversationId, meal, now);
      confirmed.push(record);
      return record;
    },
    "POST /api/nutrition/meals/discard": ({ body }) => {
      const conversationId = field(body, "conversationId");
      if (conversationId) pending.delete(conversationId);
      return {};
    },
    "PUT /api/nutrition/goal": ({ body, now }): NutritionGoal => {
      const goal = view(now).goal!;
      const edit = (body ?? {}) as Partial<SetGoalBody>;
      goalOverride = { ...goal, ...edit, id: goal.id, isActive: true, createdAt: now.toISOString() };
      return goalOverride;
    },
    "POST /api/whoop/sync": async ({ now }) => {
      await wait(DEMO_SYNC_DELAY_MS);
      lastSync = now;
      return { queued: true };
    },
  };

  async function fakeFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    const raw = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(raw, "http://demo.local");
    const method = (init?.method ?? "GET").toUpperCase();
    const handler = routes[`${method} ${url.pathname}`];
    if (!handler) {
      throw new Error(`demo: no handler for ${method} ${url.pathname}`);
    }
    const result = await handler({ url, body: readBody(init), now: clock() });
    return new Response(JSON.stringify(result ?? {}), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  return {
    fetch: fakeFetch as typeof fetch,
    handles: (method, path) => `${method.toUpperCase()} ${path}` in routes,
  };
}
