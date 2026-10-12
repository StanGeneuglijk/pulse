import fs from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeApi } from "@/lib/demo/fakeApi";
import { dayKey, parseUtc } from "@/lib/format";
import type {
  ChatResponse,
  CycleRecord,
  InsightRecord,
  InsightUsage,
  NutritionGoal,
  NutritionLogRecord,
  Profile,
  RecoveryRecord,
  SleepRecord,
  SyncLogEntry,
  SyncTriggerResponse,
  WorkoutRecord,
} from "@/lib/types";

const NOW = new Date(2026, 9, 12, 12, 0);

async function get<T>(api: ReturnType<typeof createFakeApi>, path: string): Promise<T> {
  const res = await api.fetch(path);
  expect(res.status).toBe(200);
  return (await res.json()) as T;
}

afterEach(() => vi.restoreAllMocks());

describe("reads", () => {
  const api = createFakeApi(() => NOW);

  it("serves every WHOOP list the dashboard loads", async () => {
    expect((await get<RecoveryRecord[]>(api, "/api/whoop/recovery")).length).toBeGreaterThanOrEqual(30);
    expect((await get<SleepRecord[]>(api, "/api/whoop/sleep")).length).toBeGreaterThanOrEqual(30);
    expect((await get<WorkoutRecord[]>(api, "/api/whoop/workout")).length).toBeGreaterThan(0);
    expect((await get<CycleRecord[]>(api, "/api/whoop/cycles")).length).toBeGreaterThanOrEqual(30);
    expect((await get<Profile>(api, "/api/whoop/profile")).firstName).toBeTruthy();
    expect((await get<SyncLogEntry[]>(api, "/api/whoop/syncs"))[0].status).toBe("success");
  });

  it("serves meals and the goal for the Fuel tab", async () => {
    expect((await get<NutritionLogRecord[]>(api, "/api/nutrition/meals/list?days=30")).length).toBeGreaterThan(30);
    expect((await get<NutritionGoal>(api, "/api/nutrition/goal")).goalType).toBeTruthy();
  });

  it.each(["daily", "weekly", "monthly"])("serves a %s example insight, so Insights is never empty", async (period) => {
    const latest = await get<InsightRecord>(api, `/api/insight/latest?period=${period}`);
    expect(latest.periodType).toBe(period);
    expect(latest.content).toBeTruthy();
    const list = await get<InsightRecord[]>(api, `/api/insight/list?period=${period}`);
    expect(list[0].content).toBe(latest.content);
  });

  it("reports no AI spend", async () => {
    expect((await get<InsightUsage>(api, "/api/insight/usage")).spendUsd).toBe(0);
  });
});

describe("no network", () => {
  it("answers every read without calling the real fetch", async () => {
    const spy = vi.spyOn(globalThis, "fetch");
    const api = createFakeApi(() => NOW);
    for (const path of [
      "/api/whoop/recovery",
      "/api/whoop/sleep",
      "/api/whoop/workout",
      "/api/whoop/cycles",
      "/api/whoop/profile",
      "/api/whoop/syncs",
      "/api/nutrition/meals/list?days=30",
      "/api/nutrition/goal",
      "/api/insight/latest?period=weekly",
      "/api/insight/list?period=weekly",
      "/api/insight/usage",
    ]) {
      await get(api, path);
    }
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("midnight", () => {
  it("moves today's data to the new day on the next read after midnight", async () => {
    let now = new Date(2026, 9, 12, 23, 59);
    const api = createFakeApi(() => now);
    const newest = async () => {
      const recs = await get<RecoveryRecord[]>(api, "/api/whoop/recovery");
      return recs.map((r) => parseUtc(r.recordedAt)).sort((a, b) => b.getTime() - a.getTime())[0];
    };
    expect(dayKey(await newest())).toBe(dayKey(now));
    now = new Date(2026, 9, 13, 0, 1);
    expect(dayKey(await newest())).toBe(dayKey(now));
  });
});

describe("state", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  async function call<T>(
    api: ReturnType<typeof createFakeApi>,
    path: string,
    init?: RequestInit
  ): Promise<{ status: number; body: T }> {
    const pending = api.fetch(path, init);
    await vi.advanceTimersByTimeAsync(10_000); // past every replay delay
    const res = await pending;
    return { status: res.status, body: (await res.json()) as T };
  }
  const post = (body: unknown): RequestInit => ({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  it("generates that period's example insight", async () => {
    const api = createFakeApi(() => NOW);
    for (const period of ["daily", "weekly", "monthly"]) {
      const { status, body } = await call<InsightRecord>(api, "/api/insight/generate", post({ period }));
      expect(status).toBe(200);
      expect(body.periodType).toBe(period);
      expect(body.content).toBeTruthy();
    }
  });

  it("answers any meal message with the example proposal", async () => {
    const api = createFakeApi(() => NOW);
    const { status, body } = await call<ChatResponse>(
      api,
      "/api/nutrition/chat",
      post({ conversationId: null, message: "a whole pizza" })
    );
    expect(status).toBe(200);
    expect(body.conversationId).toBeTruthy();
    expect(body.reply).toBeTruthy();
    expect(body.pendingMeal?.items.length).toBeGreaterThan(0);
  });

  it("answers the mic with the example's spoken transcript", async () => {
    const api = createFakeApi(() => NOW);
    const form = new FormData();
    form.append("audio", new Blob([]), "recording.webm");
    const { status, body } = await call<ChatResponse>(api, "/api/nutrition/chat/audio", {
      method: "POST",
      body: form,
    });
    expect(status).toBe(200);
    expect(body.transcript).toBeTruthy();
    expect(body.pendingMeal).toBeTruthy();
  });

  it("shows a confirmed meal in today's list, and a discarded one nowhere", async () => {
    const api = createFakeApi(() => NOW);
    const before = (await call<NutritionLogRecord[]>(api, "/api/nutrition/meals/list?days=30")).body.length;
    const chat = (await call<ChatResponse>(api, "/api/nutrition/chat", post({ conversationId: null, message: "x" }))).body;
    const logged = await call<NutritionLogRecord>(api, "/api/nutrition/meals/confirm", post({ conversationId: chat.conversationId }));
    expect(logged.status).toBe(200);
    expect(logged.body.description).toBe(chat.pendingMeal!.description);
    const after = (await call<NutritionLogRecord[]>(api, "/api/nutrition/meals/list?days=30")).body;
    expect(after.length).toBe(before + 1);
    expect(after.some((m) => m.id === logged.body.id && dayKey(parseUtc(m.loggedAt)) === dayKey(NOW))).toBe(true);

    const chat2 = (await call<ChatResponse>(api, "/api/nutrition/chat", post({ conversationId: null, message: "y" }))).body;
    const discarded = await call(api, "/api/nutrition/meals/discard", post({ conversationId: chat2.conversationId }));
    expect(discarded.status).toBe(200);
    expect((await call<NutritionLogRecord[]>(api, "/api/nutrition/meals/list?days=30")).body.length).toBe(before + 1);
  });

  it("keeps a goal edit until reload", async () => {
    const api = createFakeApi(() => NOW);
    const goal = { goalType: "weight_loss", targetCalories: 2100, targetProteinG: 150, targetCarbsG: null, targetFatG: null, notes: null };
    const put = await call<NutritionGoal>(api, "/api/nutrition/goal", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(goal),
    });
    expect(put.status).toBe(200);
    const got = (await call<NutritionGoal>(api, "/api/nutrition/goal")).body;
    expect(got.goalType).toBe("weight_loss");
    expect(got.targetCalories).toBe(2100);
    expect((await call<NutritionGoal>(createFakeApi(() => NOW), "/api/nutrition/goal")).body.goalType).toBe("muscle_gain");
  });

  it("pretends to sync: queued, then the sync log says just now", async () => {
    let now = NOW;
    const api = createFakeApi(() => now);
    now = new Date(NOW.getTime() + 60 * 60_000);
    const sync = await call<SyncTriggerResponse>(api, "/api/whoop/sync", { method: "POST" });
    expect(sync.body.queued).toBe(true);
    const syncs = (await call<SyncLogEntry[]>(api, "/api/whoop/syncs")).body;
    expect(parseUtc(syncs[0].createdAt).getTime()).toBe(now.getTime());
  });

  it("keeps a confirmed meal across midnight", async () => {
    let now = new Date(2026, 9, 12, 23, 50);
    const api = createFakeApi(() => now);
    const chat = (await call<ChatResponse>(api, "/api/nutrition/chat", post({ conversationId: null, message: "x" }))).body;
    const logged = (await call<NutritionLogRecord>(api, "/api/nutrition/meals/confirm", post({ conversationId: chat.conversationId }))).body;
    now = new Date(2026, 9, 13, 0, 10);
    const meals = (await call<NutritionLogRecord[]>(api, "/api/nutrition/meals/list?days=30")).body;
    expect(meals.some((m) => m.id === logged.id)).toBe(true);
  });

  it("starts every new instance (a reload) from the original state", async () => {
    const api = createFakeApi(() => NOW);
    const base = (await call<NutritionLogRecord[]>(api, "/api/nutrition/meals/list?days=30")).body.length;
    const chat = (await call<ChatResponse>(api, "/api/nutrition/chat", post({ conversationId: null, message: "x" }))).body;
    await call(api, "/api/nutrition/meals/confirm", post({ conversationId: chat.conversationId }));
    const fresh = createFakeApi(() => NOW);
    expect((await call<NutritionLogRecord[]>(fresh, "/api/nutrition/meals/list?days=30")).body.length).toBe(base);
  });
});

// Every real /api data route needs a demo counterpart, or a visitor clicking
// it in the demo gets an error. Health has no user data; logout must stay real.
describe("parity", () => {
  const apiDir = path.resolve(__dirname, "../../app/api");
  const EXCLUDED = new Set(["/api/health", "/api/auth/logout"]);

  function routes(dir: string): { path: string; methods: string[] }[] {
    return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) return routes(full);
      if (entry.name !== "route.ts") return [];
      const source = fs.readFileSync(full, "utf8");
      const methods = [...source.matchAll(/export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\b/g)].map(
        (m) => m[1]
      );
      const urlPath = "/api/" + path.relative(apiDir, path.dirname(full)).split(path.sep).join("/");
      return [{ path: urlPath, methods }];
    });
  }

  it("finds the real routes it is guarding", () => {
    expect(routes(apiDir).length).toBeGreaterThanOrEqual(17);
  });

  it("has a demo handler for every method of every data route", () => {
    const api = createFakeApi(() => NOW);
    const missing = routes(apiDir)
      .filter((r) => !EXCLUDED.has(r.path))
      .flatMap((r) => r.methods.filter((m) => !api.handles(m, r.path)).map((m) => `${m} ${r.path}`));
    expect(missing).toEqual([]);
  });

  it("throws on a path the demo doesn't know", async () => {
    await expect(createFakeApi(() => NOW).fetch("/api/not-a-route")).rejects.toThrow(/no handler/);
  });
});

describe("isolated", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  async function run(api: ReturnType<typeof createFakeApi>, path: string, init?: RequestInit) {
    const pending = api.fetch(path, init);
    await vi.advanceTimersByTimeAsync(10_000);
    return (await pending).json();
  }
  const json = (method: string, body: unknown): RequestInit => ({
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const snapshot = async (api: ReturnType<typeof createFakeApi>) => ({
    meals: await run(api, "/api/nutrition/meals/list?days=30"),
    goal: await run(api, "/api/nutrition/goal"),
    syncs: await run(api, "/api/whoop/syncs"),
    usage: await run(api, "/api/insight/usage"),
  });

  it("keeps one visitor's actions out of another visitor's demo", async () => {
    const alice = createFakeApi(() => NOW);
    const bob = createFakeApi(() => NOW);
    const bobBefore = await snapshot(bob);

    const chat = (await run(alice, "/api/nutrition/chat", json("POST", { conversationId: null, message: "x" }))) as ChatResponse;
    await run(alice, "/api/nutrition/meals/confirm", json("POST", { conversationId: chat.conversationId }));
    await run(alice, "/api/nutrition/goal", json("PUT", { goalType: "weight_loss", targetCalories: 1800, targetProteinG: null, targetCarbsG: null, targetFatG: null, notes: null }));
    await run(alice, "/api/whoop/sync", { method: "POST" });
    await run(alice, "/api/insight/generate", json("POST", { period: "daily" }));

    expect(await snapshot(bob)).toEqual(bobBefore);
    expect(await snapshot(alice)).not.toEqual(bobBefore);
  });
});
