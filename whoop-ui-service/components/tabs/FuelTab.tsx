"use client";

import { Loader2, Sparkles, Target } from "lucide-react";
import { useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { FuelToday } from "../FuelToday";
import { MealChat } from "../MealChat";
import { Card } from "../ui/Card";
import { AXIS, ChartTooltip, GRID } from "../ui/ChartTooltip";
import { useApiFetch } from "@/lib/demo/DemoContext";
import { formatTime, parseUtc } from "@/lib/format";
import { GOAL_LABELS, energyBalance, mealsOn, totals } from "@/lib/nutrition";
import type { DashboardData } from "@/lib/useDashboardData";
import type { GoalType, NutritionGoal } from "@/lib/types";

function GoalEditor({ goal, onSaved }: { goal: NutritionGoal | null; onSaved: () => void }) {
  const apiFetch = useApiFetch();
  const [goalType, setGoalType] = useState<GoalType>(goal?.goalType ?? "maintenance");
  const [calories, setCalories] = useState(goal?.targetCalories?.toString() ?? "");
  const [protein, setProtein] = useState(goal?.targetProteinG?.toString() ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setError(null);
    const num = (v: string) => (v.trim() === "" ? null : Number(v));
    const res = await apiFetch("/api/nutrition/goal", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        goalType,
        targetCalories: num(calories),
        targetProteinG: num(protein),
        targetCarbsG: goal?.targetCarbsG ?? null,
        targetFatG: goal?.targetFatG ?? null,
        notes: goal?.notes ?? null,
      }),
    });
    setSaving(false);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setError(data.error ?? "Couldn't save the goal");
      return;
    }
    onSaved();
  }

  return (
    <Card eyebrow="Your goal" title="What are you fueling for?">
      <div className="grid grid-cols-2 gap-2">
        {(Object.keys(GOAL_LABELS) as GoalType[]).map((g) => (
          <button
            key={g}
            onClick={() => setGoalType(g)}
            className={`rounded-xl border px-3 py-2 text-sm transition ${
              goalType === g
                ? "border-fuel/60 bg-fuel/15 text-white"
                : "border-line text-white/60 hover:bg-white/5"
            }`}
          >
            {GOAL_LABELS[g]}
          </button>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className="text-xs text-white/50">
          Calories / day
          <input
            inputMode="numeric"
            value={calories}
            onChange={(e) => setCalories(e.target.value.replace(/[^0-9]/g, ""))}
            placeholder="2200"
            className="mt-1 w-full rounded-xl border border-line bg-black/30 px-3 py-2 text-sm text-white focus:border-fuel/50 focus:outline-none"
          />
        </label>
        <label className="text-xs text-white/50">
          Protein (g) / day
          <input
            inputMode="numeric"
            value={protein}
            onChange={(e) => setProtein(e.target.value.replace(/[^0-9]/g, ""))}
            placeholder="140"
            className="mt-1 w-full rounded-xl border border-line bg-black/30 px-3 py-2 text-sm text-white focus:border-fuel/50 focus:outline-none"
          />
        </label>
      </div>
      {error && <p className="mt-2 text-xs text-recovery-low">{error}</p>}
      <button
        onClick={save}
        disabled={saving}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-fuel/40 bg-fuel/10 py-2.5 text-sm font-medium text-fuel-amber transition hover:bg-fuel/20 disabled:opacity-60"
      >
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Target className="h-4 w-4" />}
        {goal ? "Update goal" : "Set goal"}
      </button>
      <p className="mt-2 text-[11px] text-white/35">
        The meal assistant and your AI insights both take this goal into account.
      </p>
    </Card>
  );
}

export function FuelTab({ data, reload }: { data: DashboardData; reload: () => void }) {
  const balance = energyBalance(data.meals, data.cycles, 14);
  const target = data.goal?.targetCalories ?? null;
  const week = Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - i);
    return { day: d, meals: mealsOn(data.meals, d) };
  }).filter((d) => d.meals.length > 0);

  return (
    <div className="space-y-5">
      <div className="animate-fade-in-up relative overflow-hidden rounded-3xl border border-fuel/20 bg-gradient-to-br from-fuel/15 via-fuel-pink/5 to-transparent p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-10 -top-24 h-72 w-72 rounded-full bg-fuel-pink/20 blur-3xl" />
        <div className="relative flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-fuel-amber" />
          <p className="eyebrow text-fuel-amber">New · AI nutrition</p>
        </div>
        <h2 className="relative mt-2 font-display text-3xl font-bold tracking-tight sm:text-4xl">
          Tell it what you ate. <span className="text-fuel-gradient">It does the math.</span>
        </h2>
        <p className="relative mt-2 max-w-xl text-sm text-white/60">
          Type or say a meal. AI breaks it into calories and macros, you confirm, and it lands next
          to your recovery and strain — so your insights finally know how you&apos;re fueling.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card eyebrow="Log a meal" title="Chat with your nutrition assistant" className="flex flex-col lg:col-span-3">
          <MealChat onLogged={reload} autoFocus />
        </Card>
        <div className="space-y-5 lg:col-span-2">
          <FuelToday meals={data.meals} cycles={data.cycles} goal={data.goal} />
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card
          eyebrow="Energy balance · 14 days"
          title="Eaten vs. burned"
          className="lg:col-span-3"
          action={
            <div className="flex gap-3 text-[11px] text-white/50">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-fuel" /> Eaten
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-strain" /> Burned
              </span>
            </div>
          }
        >
          <div className="h-64">
            <ResponsiveContainer>
              <ComposedChart data={balance} margin={{ left: -12, right: 4 }}>
                <defs>
                  <linearGradient id="eaten" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FFB547" />
                    <stop offset="100%" stopColor="#FF2E93" />
                  </linearGradient>
                </defs>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="label" {...AXIS} />
                <YAxis {...AXIS} />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.04)" }}
                  content={<ChartTooltip format={(v) => `${Math.round(v).toLocaleString()} kcal`} />}
                />
                {target && <ReferenceLine y={target} stroke="#FFB547" strokeDasharray="4 4" />}
                <Bar dataKey="eaten" name="Eaten" fill="url(#eaten)" radius={[6, 6, 0, 0]} maxBarSize={26} />
                <Line
                  dataKey="burned"
                  name="Burned"
                  stroke="#3AA0FF"
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: "#3AA0FF" }}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <div className="lg:col-span-2">
          <GoalEditor goal={data.goal} onSaved={reload} />
        </div>
      </div>

      <Card eyebrow="Meal log" title="The last 7 days">
        {week.length === 0 ? (
          <p className="text-sm text-white/50">No meals logged this week yet — start with the chat above.</p>
        ) : (
          <div className="space-y-5">
            {week.map(({ day, meals }) => {
              const t = totals(meals);
              return (
                <div key={day.toDateString()}>
                  <div className="flex items-baseline justify-between">
                    <p className="font-display font-semibold">
                      {day.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
                    </p>
                    <p className="text-sm tabular-nums text-white/60">
                      <span className="font-semibold text-fuel-gradient">{t.calories.toLocaleString()}</span> kcal ·{" "}
                      {Math.round(t.proteinG)}g protein
                    </p>
                  </div>
                  <ul className="mt-2 divide-y divide-line rounded-2xl border border-line bg-white/[0.02]">
                    {meals
                      .sort((a, b) => parseUtc(a.loggedAt).getTime() - parseUtc(b.loggedAt).getTime())
                      .map((m) => (
                        <li key={m.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                          <span className="flex items-center gap-3">
                            <span className="w-14 text-xs tabular-nums text-white/40">{formatTime(m.loggedAt)}</span>
                            {m.description}
                          </span>
                          <span className="shrink-0 tabular-nums text-white/70">{m.calories} kcal</span>
                        </li>
                      ))}
                  </ul>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
