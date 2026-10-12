import { describe, expect, it } from "vitest";
import { generateDemoData } from "@/lib/demo/data";
import { DEMO_CHAT_PREFILL, exampleInsight, exampleMealChat } from "@/lib/demo/script";
import { dayKey, parseUtc } from "@/lib/format";
import type { InsightPeriod } from "@/lib/types";

const NOW = new Date(2026, 9, 12, 12, 0);
const PERIODS: InsightPeriod[] = ["daily", "weekly", "monthly"];

/** Every number the example insights may quote: per-day values and their
 * averages/extremes over the last 1, 7 and 30 days, the goal, and small
 * counts. Anything else in the text is a number the data doesn't back. */
function allowedNumbers(now: Date): Set<string> {
  const data = generateDemoData(now);
  const allowed = new Set<string>();
  const add = (v: number | null | undefined, digits = 0) => {
    if (v != null) allowed.add(v.toFixed(digits));
  };
  for (let i = 0; i <= 10; i++) add(i);
  [data.goal?.targetCalories, data.goal?.targetProteinG].forEach((v) => add(v));

  const byDay = (n: number) => {
    const d = new Date(now);
    d.setDate(d.getDate() - n);
    const key = dayKey(d);
    const on = (iso: string | null) => iso != null && dayKey(parseUtc(iso)) === key;
    const rec = data.recovery.find((r) => on(r.recordedAt));
    const sleep = data.sleep.find((s) => on(s.end));
    const cycle = data.cycles.find((c) => on(c.start));
    const meals = data.meals.filter((m) => on(m.loggedAt));
    const asleepMin = sleep ? Math.round((sleep.inBedMilli! - sleep.awakeMilli!) / 60000) : null;
    return {
      recovery: rec?.score ?? null,
      hrv: rec?.hrvRmssdMilli ?? null,
      rhr: rec?.restingHeartRate ?? null,
      strain: cycle?.score ?? null,
      asleepMin,
      kcal: meals.length ? meals.reduce((t, m) => t + m.calories, 0) : null,
      protein: meals.length ? meals.reduce((t, m) => t + m.proteinG, 0) : null,
    };
  };

  const days = Array.from({ length: 30 }, (_, n) => byDay(n));
  for (const d of days) {
    add(d.recovery);
    add(d.hrv);
    add(d.rhr);
    add(d.strain, 1);
    add(d.kcal);
    add(d.protein);
    if (d.asleepMin != null) {
      add(Math.floor(d.asleepMin / 60));
      add(d.asleepMin % 60);
      add(d.asleepMin / 60, 1);
    }
  }
  for (const w of [1, 3, 7, 30]) {
    const win = days.slice(0, w);
    for (const key of ["recovery", "hrv", "rhr", "strain", "kcal", "protein", "asleepMin"] as const) {
      const vals = win.map((d) => d[key]).filter((v): v is number => v != null);
      if (!vals.length) continue;
      const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
      add(avg);
      add(avg, 1);
      add(Math.min(...vals), key === "strain" ? 1 : 0);
      add(Math.max(...vals), key === "strain" ? 1 : 0);
      if (key === "asleepMin") {
        add(avg / 60, 1);
        add(Math.floor(avg / 60));
        add(Math.round(avg) % 60);
      }
    }
  }
  return allowed;
}

describe("insight", () => {
  const allowed = allowedNumbers(NOW);

  it.each(PERIODS)("has a non-empty example %s insight", (period) => {
    const insight = exampleInsight(period, NOW);
    expect(insight.periodType).toBe(period);
    expect(insight.content.length).toBeGreaterThan(80);
    expect(insight.modelName).toBe("example (demo)");
  });

  it.each(PERIODS)("only quotes numbers the sample data backs (%s)", (period) => {
    const { content } = exampleInsight(period, NOW);
    const numbers = content.match(/\d[\d,]*(?:\.\d+)?/g) ?? [];
    expect(numbers.length).toBeGreaterThan(0);
    for (const n of numbers) {
      expect(allowed, `"${n}" in the ${period} insight`).toContain(n.replace(/,/g, ""));
    }
  });
});

describe("insight early in the morning", () => {
  const EARLY = new Date(2026, 9, 12, 6, 0);
  const allowed = allowedNumbers(EARLY);

  it.each(PERIODS)("works with nothing logged yet today and quotes only backed numbers (%s)", (period) => {
    const { content } = exampleInsight(period, EARLY);
    for (const n of content.match(/\d[\d,]*(?:\.\d+)?/g) ?? []) {
      expect(allowed, `"${n}" in the ${period} insight`).toContain(n.replace(/,/g, ""));
    }
  });
});

describe("meal chat", () => {
  it("proposes a breakdown whose totals equal the sum of its items", () => {
    const { proposal } = exampleMealChat(NOW);
    expect(proposal.items.length).toBeGreaterThanOrEqual(2);
    const sum = (k: "calories" | "proteinG" | "carbsG" | "fatG") => proposal.items.reduce((t, i) => t + i[k], 0);
    expect(proposal.totalCalories).toBe(sum("calories"));
    expect(proposal.totalProteinG).toBe(sum("proteinG"));
    expect(proposal.totalCarbsG).toBe(sum("carbsG"));
    expect(proposal.totalFatG).toBe(sum("fatG"));
  });

  it("pre-fills a described meal, the proposed breakdown and the confirmed result, marked as an example", () => {
    const { proposal, userText } = exampleMealChat(NOW);
    const entries = DEMO_CHAT_PREFILL(NOW);
    expect(entries[0]).toEqual({ role: "user", text: userText });
    expect(entries[1].role).toBe("assistant");
    for (const item of proposal.items) expect(entries[1].text).toContain(item.name);
    expect(entries[entries.length - 1].text).toBe(
      `Logged ✓ ${proposal.description} — ${proposal.totalCalories} kcal (example)`
    );
  });
});
