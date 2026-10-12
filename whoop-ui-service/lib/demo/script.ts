/**
 * The demo's pre-written AI output. No model is ever called for a demo
 * visitor: these texts were written once about the sample person in
 * ./data.ts, and their numbers are filled in from that same table, so they
 * always match what the charts show (tests/demo/script.test.ts checks it).
 */
import { dayKey, parseUtc } from "../format";
import type { InsightPeriod, InsightRecord, MealItem, MealProposal } from "../types";
import { DEMO_GOAL, DEMO_MODEL_NAME, DEMO_USER_ID, generateDemoData } from "./data";

interface Day {
  recovery: number | null;
  hrv: number | null;
  rhr: number | null;
  strain: number | null;
  asleepMin: number | null;
  kcal: number | null;
  protein: number | null;
}

function daysOf(now: Date, count: number): Day[] {
  const data = generateDemoData(now);
  return Array.from({ length: count }, (_, n) => {
    const d = new Date(now);
    d.setDate(d.getDate() - n);
    const key = dayKey(d);
    const on = (iso: string | null) => iso != null && dayKey(parseUtc(iso)) === key;
    const rec = data.recovery.find((r) => on(r.recordedAt));
    const sleep = data.sleep.find((s) => on(s.end));
    const cycle = data.cycles.find((c) => on(c.start));
    const meals = data.meals.filter((m) => on(m.loggedAt));
    return {
      recovery: rec?.score ?? null,
      hrv: rec?.hrvRmssdMilli ?? null,
      rhr: rec?.restingHeartRate ?? null,
      strain: cycle?.score ?? null,
      asleepMin: sleep ? Math.round((sleep.inBedMilli! - sleep.awakeMilli!) / 60000) : null,
      kcal: meals.length ? meals.reduce((t, m) => t + m.calories, 0) : null,
      protein: meals.length ? meals.reduce((t, m) => t + m.proteinG, 0) : null,
    };
  });
}

function values(days: Day[], key: keyof Day): number[] {
  return days.map((d) => d[key]).filter((v): v is number => v != null);
}
const avg = (vs: number[]) => vs.reduce((a, b) => a + b, 0) / vs.length;
const n0 = (v: number) => Number(v.toFixed(0)).toLocaleString("en-US");
const n1 = (v: number) => v.toFixed(1);
const hm = (min: number) => `${Math.floor(min / 60)}h ${min % 60}m`;

function dailyText(days: Day[]): string {
  const [today, , , threeAgo, fourAgo, fiveAgo, sixAgo] = days;
  return [
    `You're green today: recovery ${today.recovery}%, HRV ${today.hrv} ms and a resting heart rate of ${today.rhr} bpm, your best numbers since the hard training block.`,
    `You slept ${hm(today.asleepMin!)} last night. Recovery bottomed out at ${fourAgo.recovery}% four days ago, in the middle of three straight days of ${sixAgo.strain!.toFixed(1)}, ${fiveAgo.strain!.toFixed(1)} and ${fourAgo.strain!.toFixed(1)} strain, and has climbed every day since, from ${threeAgo.recovery}% to ${today.recovery}%.`,
    today.kcal == null
      ? `Nothing logged yet today; your target is ${n0(DEMO_GOAL.targetCalories!)} kcal and ${DEMO_GOAL.targetProteinG} g of protein.`
      : `So far today you've logged ${n0(today.kcal)} kcal and ${today.protein} g of protein against a ${n0(DEMO_GOAL.targetCalories!)} kcal / ${DEMO_GOAL.targetProteinG} g target.`,
    `One thing to do: use the green day for a quality session, then make dinner protein-heavy to close the gap.`,
  ].join(" ");
}

function weeklyText(days: Day[]): string {
  const week = days.slice(0, 7);
  const strain = values(week, "strain");
  const recovery = values(week, "recovery");
  const hrv = values(week, "hrv");
  return [
    `Your week in one line: three hard days, a dip, then a rebound.`,
    `Strain peaked at ${Math.max(...strain).toFixed(1)} and averaged ${n1(avg(strain))}; recovery averaged ${n0(avg(recovery))}% and fell as low as ${Math.min(...recovery)}% during the block.`,
    `HRV followed the same curve, from ${Math.min(...hrv)} ms at the low to ${week[0].hrv} ms today, and you slept ${n1(avg(values(week, "asleepMin")) / 60)} hours a night on average.`,
    `On the days you logged food you averaged ${n0(avg(values(week, "kcal")))} kcal and ${n0(avg(values(week, "protein")))} g of protein, under your ${n0(DEMO_GOAL.targetCalories!)} kcal / ${DEMO_GOAL.targetProteinG} g target, which made the hard days harder to bounce back from.`,
    `Next week: follow every hard day with an easy one, and add a protein shake on training days.`,
  ].join(" ");
}

function monthlyText(days: Day[]): string {
  const month = days.slice(0, 30);
  const recovery = values(month, "recovery");
  return [
    `Over the past month your recovery averaged ${n0(avg(recovery))}%, ranging from ${Math.min(...recovery)}% to ${Math.max(...recovery)}%.`,
    `Average day strain was ${n1(avg(values(month, "strain")))} and you slept ${n1(avg(values(month, "asleepMin")) / 60)} hours a night.`,
    `The pattern is clear: your lowest recoveries came straight after back-to-back high-strain days, not after single hard sessions.`,
    `Nutrition is the gap: on logged days you averaged ${n0(avg(values(month, "kcal")))} kcal and ${n0(avg(values(month, "protein")))} g of protein, against ${n0(DEMO_GOAL.targetCalories!)} kcal and ${DEMO_GOAL.targetProteinG} g for your muscle-gain goal.`,
    `The one thing to change next month: eat to your target on training days, starting with protein at every meal.`,
  ].join(" ");
}

const PERIOD_DAYS: Record<InsightPeriod, number> = { daily: 1, weekly: 7, monthly: 30 };
const TEXT: Record<InsightPeriod, (days: Day[]) => string> = {
  daily: dailyText,
  weekly: weeklyText,
  monthly: monthlyText,
};

/** The example insight for `period`, dated so it covers the period ending today. */
export function exampleInsight(period: InsightPeriod, now: Date): InsightRecord {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (PERIOD_DAYS[period] - 1));
  return {
    id: `demo-insight-${period}`,
    userId: DEMO_USER_ID,
    periodType: period,
    periodStart: start.toISOString(),
    periodEnd: now.toISOString(),
    promptVersion: "demo",
    modelName: DEMO_MODEL_NAME,
    content: TEXT[period](daysOf(now, 30)),
    createdAt: new Date(now.getTime() - 20 * 60_000).toISOString(),
  };
}

// The example meal chat: one described meal, the assistant's breakdown, and
// (pre-filled) its confirmation. In the demo every meal message, typed or
// spoken, replays this exchange.
const MEAL_ITEMS: MealItem[] = [
  { name: "Grilled salmon fillet", quantity: "150 g", calories: 310, proteinG: 34, carbsG: 0, fatG: 19 },
  { name: "Jasmine rice", quantity: "1 cup cooked", calories: 205, proteinG: 4, carbsG: 45, fatG: 0 },
  { name: "Side salad with vinaigrette", quantity: "1 bowl", calories: 120, proteinG: 2, carbsG: 7, fatG: 10 },
];

export interface ExampleMealChat {
  userText: string;
  transcript: string;
  reply: string;
  proposal: MealProposal;
}

export function exampleMealChat(now: Date): ExampleMealChat {
  const total = (k: "calories" | "proteinG" | "carbsG" | "fatG") => MEAL_ITEMS.reduce((t, i) => t + i[k], 0);
  const proposal: MealProposal = {
    description: "Grilled salmon, jasmine rice and a side salad",
    loggedAt: now.toISOString(),
    items: MEAL_ITEMS,
    totalCalories: total("calories"),
    totalProteinG: total("proteinG"),
    totalCarbsG: total("carbsG"),
    totalFatG: total("fatG"),
    fiberG: 4,
    sugarG: 5,
    sodiumMg: 540,
  };
  const items = MEAL_ITEMS.map((i) => `${i.name} (${i.quantity}) ${i.calories} kcal`).join(", ");
  return {
    userText: "Grilled salmon with rice and a side salad",
    transcript: "I had grilled salmon with a cup of rice and a side salad for dinner",
    reply:
      `Here's my estimate: ${items}. Total ${proposal.totalCalories} kcal · ${proposal.totalProteinG} g protein · ` +
      `${proposal.totalCarbsG} g carbs · ${proposal.totalFatG} g fat. Confirm to log it.`,
    proposal,
  };
}

export interface DemoChatEntry {
  role: "user" | "assistant";
  text: string;
}

/** What the Fuel chat shows before the visitor types anything. */
export function DEMO_CHAT_PREFILL(now: Date): DemoChatEntry[] {
  const { userText, reply, proposal } = exampleMealChat(now);
  return [
    { role: "user", text: userText },
    { role: "assistant", text: reply },
    // Marked as an example: this meal is not in the sample day's totals.
    { role: "assistant", text: `Logged ✓ ${proposal.description} — ${proposal.totalCalories} kcal (example)` },
  ];
}

/** Prefix for replies to anything the visitor actually types or says. */
export const DEMO_REPLAY_NOTE = "In the demo, every meal message plays this example. ";
