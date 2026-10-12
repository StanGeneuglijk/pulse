/**
 * The demo's sample person: one fixed, fictional user every demo visitor
 * sees. Nothing here is ever stored or sent to a backend; see
 * specs/001-demo-mode/data-model.md.
 *
 * The numbers are a fixed day-by-day table, not random: the same values every
 * day, only the dates move, so the example insights in ./script.ts can quote
 * them. Day 0 is always the visitor's local today.
 */
import type { DashboardData } from "../useDashboardData";
import type {
  CycleRecord,
  NutritionGoal,
  NutritionLogRecord,
  Profile,
  RecoveryRecord,
  SleepRecord,
  SyncLogEntry,
  WorkoutRecord,
} from "../types";

// How long a demo session lasts before the visitor lands back on /login.
export const DEMO_SESSION_HOURS = 24;
// Days of sample data, ending today.
export const DEMO_DAYS = 35;
// Pretend latency for scripted actions, so they feel like the real thing.
export const DEMO_INSIGHT_DELAY_MS = 1400;
export const DEMO_CHAT_DELAY_MS = 900;
export const DEMO_SYNC_DELAY_MS = 600;

export const DEMO_USER_ID = "demo";
export const DEMO_MODEL_NAME = "example (demo)";

export const DEMO_PROFILE: Profile = {
  firstName: "Alex",
  lastName: "Rivera",
  heightMeter: 1.78,
  weightKilogram: 76.4,
  maxHeartRate: 192,
};

export const DEMO_GOAL: NutritionGoal = {
  id: "demo-goal",
  goalType: "muscle_gain",
  targetCalories: 2600,
  targetProteinG: 160,
  targetCarbsG: 300,
  targetFatG: 80,
  notes: "Lean bulk while training five days a week.",
  isActive: true,
  createdAt: "2026-09-01T08:00:00Z",
};

// One value per day, oldest (34 days ago) first, today last. The story: a
// steady month, a hard three-day block 6–4 days ago, recovery dipping into
// the red right after it, then rebounding to green today.
// prettier-ignore
const RECOVERY = [
  72, 65, 58, 81, 77, 62, 54,
  69, 74, 80, 66, 59, 71, 84,
  63, 57, 70, 76, 68, 61, 79,
  73, 66, 55, 62, 78, 82, 75,
  71, 46, 38, 44, 61, 70, 78,
];
// prettier-ignore
const STRAIN = [
  11.2, 14.5, 9.8, 8.4, 13.1, 15.6, 10.2,
  12.4, 9.1, 7.9, 14.8, 16.2, 11.5, 8.8,
  13.7, 15.1, 10.6, 9.4, 12.9, 14.2, 8.6,
  11.8, 13.4, 15.9, 10.1, 9.3, 12.2, 13.8,
  17.4, 18.6, 16.8, 9.2, 7.6, 11.4, 6.8,
];
const SPORTS = ["running", "cycling", "functional-fitness", "weightlifting"];

interface Food {
  description: string;
  proteinG: number;
  carbsG: number;
  fatG: number;
}

const BREAKFASTS: Food[] = [
  { description: "Greek yogurt, granola and berries", proteinG: 28, carbsG: 62, fatG: 14 },
  { description: "Two eggs, sourdough toast and a flat white", proteinG: 26, carbsG: 38, fatG: 22 },
  { description: "Overnight oats with peanut butter and banana", proteinG: 22, carbsG: 78, fatG: 18 },
  { description: "Protein smoothie with oats and blueberries", proteinG: 38, carbsG: 55, fatG: 9 },
];
const LUNCHES: Food[] = [
  { description: "Chicken burrito bowl with rice and guac", proteinG: 48, carbsG: 86, fatG: 24 },
  { description: "Tuna salad wrap and an apple", proteinG: 38, carbsG: 58, fatG: 16 },
  { description: "Salmon poke bowl", proteinG: 40, carbsG: 72, fatG: 20 },
  { description: "Turkey and avocado sandwich", proteinG: 36, carbsG: 52, fatG: 22 },
];
const DINNERS: Food[] = [
  { description: "Steak, sweet potato and broccoli", proteinG: 52, carbsG: 58, fatG: 26 },
  { description: "Pasta bolognese with parmesan", proteinG: 42, carbsG: 92, fatG: 24 },
  { description: "Chicken stir-fry with jasmine rice", proteinG: 46, carbsG: 84, fatG: 18 },
  { description: "Baked cod, quinoa and roasted vegetables", proteinG: 44, carbsG: 60, fatG: 16 },
];
const SNACKS: Food[] = [
  { description: "Protein shake with a banana after training", proteinG: 30, carbsG: 32, fatG: 4 },
  { description: "Cottage cheese with honey", proteinG: 24, carbsG: 22, fatG: 6 },
  { description: "Handful of almonds and a pear", proteinG: 8, carbsG: 28, fatG: 18 },
];
// Days (counted back from today) with nothing logged: real people forget.
const NO_MEALS_DAYS = new Set([27, 19, 12, 8]);

const MIN = 60_000;

export function kcalOf(food: Food): number {
  return 4 * food.proteinG + 4 * food.carbsG + 9 * food.fatG;
}

/** Local midnight of the day `daysAgo` days before `now`. */
function dayStart(now: Date, daysAgo: number): Date {
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() - daysAgo);
}

function at(base: Date, minutes: number): Date {
  return new Date(base.getTime() + minutes * MIN);
}

export function mealRecord(id: string, food: Food, loggedAt: Date): NutritionLogRecord {
  return {
    id,
    userId: DEMO_USER_ID,
    conversationId: null,
    description: food.description,
    loggedAt: loggedAt.toISOString(),
    calories: kcalOf(food),
    proteinG: food.proteinG,
    carbsG: food.carbsG,
    fatG: food.fatG,
    fiberG: Math.round(food.carbsG / 10),
    sugarG: Math.round(food.carbsG / 5),
    sodiumMg: 650,
    modelName: DEMO_MODEL_NAME,
    createdAt: loggedAt.toISOString(),
  };
}

function mealsFor(daysAgo: number, i: number, base: Date, trained: boolean, now: Date): NutritionLogRecord[] {
  if (NO_MEALS_DAYS.has(daysAgo)) return [];
  const id = (slot: string) => `demo-meal-${daysAgo}-${slot}`;
  const meals = [
    mealRecord(id("b"), BREAKFASTS[i % BREAKFASTS.length], at(base, 7 * 60 + 40)),
    mealRecord(id("l"), LUNCHES[(i + 1) % LUNCHES.length], at(base, 12 * 60 + 45)),
  ];
  // Today is still in progress: breakfast and lunch at most, and nothing
  // later than the current time.
  if (daysAgo === 0) return meals.filter((m) => new Date(m.loggedAt).getTime() <= now.getTime());
  if (trained || i % 2 === 0) {
    meals.push(mealRecord(id("s"), SNACKS[i % SNACKS.length], at(base, 16 * 60)));
  }
  meals.push(mealRecord(id("d"), DINNERS[(i + 2) % DINNERS.length], at(base, 19 * 60 + 15)));
  return meals;
}

/** The sample person's month, with day 0 on `now`'s local calendar day. */
export function generateDemoData(now: Date): DashboardData {
  const recovery: RecoveryRecord[] = [];
  const sleep: SleepRecord[] = [];
  const workouts: WorkoutRecord[] = [];
  const cycles: CycleRecord[] = [];
  const meals: NutritionLogRecord[] = [];
  const wakeTimes: Date[] = [];

  for (let i = 0; i < DEMO_DAYS; i++) {
    const daysAgo = DEMO_DAYS - 1 - i;
    const base = dayStart(now, daysAgo);
    const rec = RECOVERY[i];
    const strain = STRAIN[i];

    // Last night's sleep: in bed between ~22:15 and ~23:05.
    const asleepMin = 400 + ((i * 53) % 110);
    const awakeMin = 25 + ((i * 7) % 25);
    const inBedMin = asleepMin + awakeMin;
    const sleepStart = at(base, -(55 + ((i * 37) % 50)));
    const sleepEnd = at(sleepStart, inBedMin);
    wakeTimes.push(sleepEnd);
    const remMin = Math.round(asleepMin * 0.23);
    const swsMin = Math.round(asleepMin * 0.21);
    sleep.push({
      id: `demo-sleep-${daysAgo}`,
      whoopRecordId: `demo-sleep-${daysAgo}`,
      score: Math.min(100, Math.round((asleepMin / 480) * 100)),
      recordedAt: sleepEnd.toISOString(),
      scoreState: "SCORED",
      cycleId: `demo-cyc-${daysAgo}`,
      start: sleepStart.toISOString(),
      end: sleepEnd.toISOString(),
      nap: false,
      inBedMilli: inBedMin * MIN,
      awakeMilli: awakeMin * MIN,
      lightSleepMilli: (asleepMin - remMin - swsMin) * MIN,
      slowWaveSleepMilli: swsMin * MIN,
      remSleepMilli: remMin * MIN,
      sleepCycleCount: Math.round(asleepMin / 90),
      disturbanceCount: 3 + (i % 6),
      sleepNeededMilli: 480 * MIN,
      respiratoryRate: Math.round((14.5 + (i % 5) * 0.3) * 10) / 10,
      sleepConsistencyPercentage: 70 + ((i * 11) % 25),
      sleepEfficiencyPercentage: Math.round((asleepMin / inBedMin) * 1000) / 10,
    });

    recovery.push({
      id: `demo-rec-${daysAgo}`,
      whoopRecordId: `demo-rec-${daysAgo}`,
      score: rec,
      recordedAt: at(sleepEnd, 4).toISOString(),
      scoreState: "SCORED",
      sleepId: `demo-sleep-${daysAgo}`,
      userCalibrating: false,
      restingHeartRate: Math.round(64 - rec * 0.14),
      hrvRmssdMilli: Math.round(28 + rec * 0.55),
      spo2Percentage: Math.round((95.2 + (i % 5) * 0.4) * 10) / 10,
      // Slightly warmer skin on the days the body was struggling.
      skinTempCelsius: Math.round((33.6 + (i % 4) * 0.15 + (rec < 50 ? 0.6 : 0)) * 100) / 100,
    });

    const trained = strain >= 12;
    if (trained) {
      const durationMin = Math.round(45 + (strain - 12) * 8);
      const start = at(base, 17 * 60 + 30);
      const avgHr = Math.round(128 + (strain - 12) * 4);
      const zones = [5, 15, 30, 30, 15, 5].map((pct) => Math.round((durationMin * MIN * pct) / 100));
      workouts.push({
        id: `demo-wo-${daysAgo}`,
        whoopRecordId: `demo-wo-${daysAgo}`,
        score: Math.round((strain - 2.5) * 10) / 10,
        recordedAt: start.toISOString(),
        scoreState: "SCORED",
        start: start.toISOString(),
        end: at(start, durationMin).toISOString(),
        sportName: SPORTS[i % SPORTS.length],
        averageHeartRate: avgHr,
        maxHeartRate: avgHr + 28,
        kilojoule: durationMin * 45,
        percentRecorded: 100,
        distanceMeter: SPORTS[i % SPORTS.length] === "running" ? durationMin * 170 : null,
        altitudeGainMeter: null,
        zoneDurationsMilli: zones,
      });
    }

    meals.push(...mealsFor(daysAgo, i, base, trained, now));
  }

  // Each day's cycle runs from waking up to the next wake; today's is open.
  for (let i = 0; i < DEMO_DAYS; i++) {
    const daysAgo = DEMO_DAYS - 1 - i;
    cycles.push({
      id: `demo-cyc-${daysAgo}`,
      whoopRecordId: `demo-cyc-${daysAgo}`,
      score: STRAIN[i],
      recordedAt: wakeTimes[i].toISOString(),
      scoreState: "SCORED",
      start: wakeTimes[i].toISOString(),
      end: i + 1 < DEMO_DAYS ? wakeTimes[i + 1].toISOString() : null,
      kilojoule: Math.round(8400 + STRAIN[i] * 330),
      averageHeartRate: Math.round(62 + STRAIN[i] * 1.5),
      maxHeartRate: Math.round(120 + STRAIN[i] * 3.5),
    });
  }

  const syncs: SyncLogEntry[] = [
    {
      status: "success",
      triggerSource: "scheduled",
      recoveriesSynced: 1,
      sleepSynced: 1,
      workoutsSynced: 0,
      cyclesSynced: 1,
      durationMs: 2140,
      errorMessage: null,
      createdAt: at(now, -4).toISOString(),
    },
  ];

  return {
    recovery,
    sleep,
    naps: [],
    workouts,
    cycles,
    profile: DEMO_PROFILE,
    syncs,
    meals,
    goal: DEMO_GOAL,
  };
}
