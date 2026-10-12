import { describe, expect, it } from "vitest";
import { generateDemoData } from "@/lib/demo/data";
import { dayKey, parseUtc } from "@/lib/format";

const NOWS = [
  new Date(2026, 9, 12, 0, 5),
  new Date(2026, 9, 12, 12, 0),
  new Date(2026, 9, 12, 23, 55),
  new Date(2027, 0, 1, 0, 5), // across a year boundary
];

function daysBefore(now: Date, n: number): string {
  const d = new Date(now);
  d.setDate(d.getDate() - n);
  return dayKey(d);
}

const localDay = (iso: string) => dayKey(parseUtc(iso));

describe("ends today", () => {
  it.each(NOWS)("puts today's recovery, sleep and cycle on the local day of %s", (now) => {
    const data = generateDemoData(now);
    const today = dayKey(now);
    expect(data.recovery.some((r) => localDay(r.recordedAt) === today)).toBe(true);
    expect(data.sleep.some((s) => !s.nap && localDay(s.end ?? s.recordedAt) === today)).toBe(true);
    expect(data.cycles.some((c) => localDay(c.start ?? c.recordedAt) === today)).toBe(true);
  });

  it.each(NOWS)("has at least 30 consecutive days of recovery, sleep and cycles up to %s", (now) => {
    const data = generateDemoData(now);
    const recoveryDays = new Set(data.recovery.map((r) => localDay(r.recordedAt)));
    const sleepDays = new Set(data.sleep.map((s) => localDay(s.end ?? s.recordedAt)));
    const cycleDays = new Set(data.cycles.map((c) => localDay(c.start ?? c.recordedAt)));
    for (let i = 0; i < 30; i++) {
      const day = daysBefore(now, i);
      expect(recoveryDays.has(day)).toBe(true);
      expect(sleepDays.has(day)).toBe(true);
      expect(cycleDays.has(day)).toBe(true);
    }
  });
});

describe("plausible values", () => {
  const data = generateDemoData(NOWS[1]);

  it("keeps recovery, HRV and resting heart rate in range", () => {
    for (const r of data.recovery) {
      expect(r.score).toBeGreaterThanOrEqual(1);
      expect(r.score).toBeLessThanOrEqual(99);
      expect(r.hrvRmssdMilli).toBeGreaterThanOrEqual(20);
      expect(r.hrvRmssdMilli).toBeLessThanOrEqual(150);
      expect(r.restingHeartRate).toBeGreaterThanOrEqual(40);
      expect(r.restingHeartRate).toBeLessThanOrEqual(80);
    }
  });

  it("keeps sleep between 4 and 10 hours, with stages summing to time asleep", () => {
    const H = 3_600_000;
    for (const s of data.sleep) {
      const asleep = s.inBedMilli! - s.awakeMilli!;
      expect(asleep).toBeGreaterThanOrEqual(4 * H);
      expect(asleep).toBeLessThanOrEqual(10 * H);
      expect(s.lightSleepMilli! + s.slowWaveSleepMilli! + s.remSleepMilli!).toBe(asleep);
    }
  });

  it("keeps strain within 0–21 and energy positive", () => {
    for (const c of data.cycles) {
      expect(c.score).toBeGreaterThanOrEqual(0);
      expect(c.score).toBeLessThanOrEqual(21);
      expect(c.kilojoule).toBeGreaterThan(0);
    }
    for (const w of data.workouts) {
      expect(w.score).toBeGreaterThanOrEqual(0);
      expect(w.score).toBeLessThanOrEqual(21);
      expect(w.kilojoule).toBeGreaterThan(0);
    }
  });

  it("gives meals non-negative macros whose calories match 4·P + 4·C + 9·F within 15%", () => {
    for (const m of data.meals) {
      expect(Math.min(m.proteinG, m.carbsG, m.fatG)).toBeGreaterThanOrEqual(0);
      const fromMacros = 4 * m.proteinG + 4 * m.carbsG + 9 * m.fatG;
      expect(Math.abs(m.calories - fromMacros) / fromMacros).toBeLessThanOrEqual(0.15);
    }
  });

  it("uses stable record ids", () => {
    expect(generateDemoData(NOWS[0]).recovery.map((r) => r.id)).toEqual(
      generateDemoData(NOWS[2]).recovery.map((r) => r.id)
    );
    expect(data.recovery.some((r) => r.id === "demo-rec-0")).toBe(true);
  });
});

describe("meals and goal", () => {
  it("logs meals on at least 24 of the last 30 days and has one active goal", () => {
    const now = NOWS[1];
    const data = generateDemoData(now);
    const mealDays = new Set(data.meals.map((m) => localDay(m.loggedAt)));
    let days = 0;
    for (let i = 0; i < 30; i++) if (mealDays.has(daysBefore(now, i))) days++;
    expect(days).toBeGreaterThanOrEqual(24);
    expect(data.goal?.isActive).toBe(true);
    expect(data.goal?.targetCalories).toBeGreaterThan(0);
  });
});

describe("story", () => {
  it("has a hard block, a dip, then a green today", () => {
    const now = NOWS[1];
    const data = generateDemoData(now);
    const strainOn = (n: number) =>
      data.cycles.find((c) => localDay(c.start ?? c.recordedAt) === daysBefore(now, n))!.score!;
    const recoveryOn = (n: number) =>
      data.recovery.find((r) => localDay(r.recordedAt) === daysBefore(now, n))!.score!;
    for (const n of [6, 5, 4]) expect(strainOn(n)).toBeGreaterThanOrEqual(16);
    expect(Math.min(recoveryOn(5), recoveryOn(4), recoveryOn(3))).toBeLessThan(50);
    expect(recoveryOn(0)).toBeGreaterThanOrEqual(67);
  });
});

describe("no meals from the future", () => {
  const todaysMeals = (now: Date) =>
    generateDemoData(now).meals.filter((m) => localDay(m.loggedAt) === dayKey(now));

  it("shows nothing logged yet early in the morning", () => {
    expect(todaysMeals(new Date(2026, 9, 12, 6, 0))).toEqual([]);
  });

  it("only shows today's meals up to the current time", () => {
    const now = new Date(2026, 9, 12, 9, 0);
    const meals = todaysMeals(now);
    expect(meals.length).toBe(1);
    for (const m of meals) expect(parseUtc(m.loggedAt).getTime()).toBeLessThanOrEqual(now.getTime());
  });
});
