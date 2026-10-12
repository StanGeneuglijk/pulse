"use client";

import { Flame, Mic, Utensils } from "lucide-react";
import { Ring } from "./ui/Ring";
import { kjToKcal } from "@/lib/format";
import { goalLabel, mealsOn, totals } from "@/lib/nutrition";
import type { CycleRecord, NutritionGoal, NutritionLogRecord } from "@/lib/types";

function MacroBar({
  label,
  grams,
  target,
  color,
}: {
  label: string;
  grams: number;
  target: number | null;
  color: string;
}) {
  const pct = target ? Math.min(grams / target, 1) : Math.min(grams / 150, 1);
  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="text-white/60">{label}</span>
        <span className="tabular-nums text-white/80">
          {Math.round(grams)}g{target ? <span className="text-white/35"> / {target}g</span> : null}
        </span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className="h-full rounded-full transition-all duration-1000"
          style={{ width: `${pct * 100}%`, background: color }}
        />
      </div>
    </div>
  );
}

interface Props {
  meals: NutritionLogRecord[];
  cycles: CycleRecord[];
  goal: NutritionGoal | null;
  /** Show the "log a meal" call to action (Overview). */
  onLogMeal?: () => void;
}

/** Today's intake against the goal — the card that makes nutrition the headline. */
export function FuelToday({ meals, cycles, goal, onLogMeal }: Props) {
  const today = totals(mealsOn(meals, new Date()));
  const target = goal?.targetCalories ?? null;
  const burned = kjToKcal(cycles[0]?.kilojoule);
  const remaining = target != null ? target - today.calories : null;

  return (
    <div className="relative overflow-hidden rounded-3xl bg-fuel-gradient p-[1.5px] shadow-fuel animate-fade-in-up">
      <div className="relative h-full rounded-[23px] bg-ink/95 p-5 sm:p-6">
        <div className="pointer-events-none absolute -right-20 -top-20 h-60 w-60 rounded-full bg-fuel/25 blur-3xl" />
        <div className="relative flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <p className="eyebrow text-fuel-amber">Fuel · today</p>
              <span className="rounded-full bg-fuel-gradient px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-black">
                New
              </span>
            </div>
            <h3 className="mt-1 font-display text-xl font-semibold">
              {today.count === 0 ? "Nothing logged yet" : `${today.count} meal${today.count > 1 ? "s" : ""} logged`}
            </h3>
            <p className="text-xs text-white/50">Goal: {goalLabel(goal)}</p>
          </div>
          <Utensils className="h-5 w-5 text-fuel" />
        </div>

        <div className="relative mt-5 flex flex-wrap items-center gap-6">
          <Ring
            value={target ? today.calories : today.calories > 0 ? today.calories : null}
            max={target ?? Math.max(today.calories, 2000)}
            size={150}
            stroke={13}
            color={["#FFB547", "#FF2E93"]}
            display={today.calories.toLocaleString()}
            unit=""
            caption={
              remaining == null ? "kcal eaten" : remaining >= 0 ? `${remaining} kcal left` : `${-remaining} kcal over`
            }
          />
          <div className="min-w-[180px] flex-1 space-y-3">
            <MacroBar label="Protein" grams={today.proteinG} target={goal?.targetProteinG ?? null} color="#FF6B3D" />
            <MacroBar label="Carbs" grams={today.carbsG} target={goal?.targetCarbsG ?? null} color="#FFB547" />
            <MacroBar label="Fat" grams={today.fatG} target={goal?.targetFatG ?? null} color="#FF2E93" />
            {burned != null && (
              <div className="flex items-center justify-between rounded-xl bg-strain/10 px-3 py-2 text-xs">
                <span className="flex items-center gap-1.5 text-white/60">
                  <Flame className="h-3.5 w-3.5 text-strain" /> Burned today (WHOOP)
                </span>
                <span className="whitespace-nowrap font-display font-semibold tabular-nums text-white">
                  {burned.toLocaleString()} kcal
                </span>
              </div>
            )}
          </div>
        </div>

        {onLogMeal && (
          <button
            onClick={onLogMeal}
            className="relative mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-fuel-gradient px-4 py-3 font-semibold text-black transition hover:brightness-110"
          >
            <Mic className="h-4 w-4" /> Log a meal — type or talk
          </button>
        )}
      </div>
    </div>
  );
}
