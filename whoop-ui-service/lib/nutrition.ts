import { dayKey, kjToKcal, parseUtc } from "./format";
import type { CycleRecord, GoalType, NutritionGoal, NutritionLogRecord } from "./types";

export interface Totals {
  calories: number;
  proteinG: number;
  carbsG: number;
  fatG: number;
  count: number;
}

export function totals(meals: NutritionLogRecord[]): Totals {
  return meals.reduce(
    (t, m) => ({
      calories: t.calories + m.calories,
      proteinG: t.proteinG + m.proteinG,
      carbsG: t.carbsG + m.carbsG,
      fatG: t.fatG + m.fatG,
      count: t.count + 1,
    }),
    { calories: 0, proteinG: 0, carbsG: 0, fatG: 0, count: 0 }
  );
}

export function mealsOn(meals: NutritionLogRecord[], day: Date): NutritionLogRecord[] {
  const key = dayKey(day);
  return meals.filter((m) => dayKey(parseUtc(m.loggedAt)) === key);
}

export interface EnergyDay {
  label: string;
  eaten: number | null;
  burned: number | null;
}

/** Calories eaten (confirmed meals) vs. burned (WHOOP cycle energy), per
 * local day, oldest first. */
export function energyBalance(
  meals: NutritionLogRecord[],
  cycles: CycleRecord[],
  days: number
): EnergyDay[] {
  const burnedByDay = new Map<string, number>();
  for (const c of cycles) {
    const kcal = kjToKcal(c.kilojoule);
    if (kcal != null) burnedByDay.set(dayKey(parseUtc(c.start ?? c.recordedAt)), kcal);
  }
  const out: EnergyDay[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const day = new Date();
    day.setDate(day.getDate() - i);
    const eaten = totals(mealsOn(meals, day));
    out.push({
      label: day.toLocaleDateString(undefined, { weekday: "short" }),
      eaten: eaten.count ? eaten.calories : null,
      burned: burnedByDay.get(dayKey(day)) ?? null,
    });
  }
  return out;
}

export const GOAL_LABELS: Record<GoalType, string> = {
  weight_loss: "Lose weight",
  maintenance: "Maintain",
  weight_gain: "Gain weight",
  muscle_gain: "Build muscle",
};

export function goalLabel(goal: NutritionGoal | null): string {
  return goal ? (GOAL_LABELS[goal.goalType] ?? goal.goalType) : "No goal set";
}
