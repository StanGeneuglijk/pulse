"use client";

import { Activity, ArrowRight, Droplets, HeartPulse, Moon, Sparkles, Thermometer, Wind } from "lucide-react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { FuelToday } from "../FuelToday";
import { Card } from "../ui/Card";
import { AXIS, ChartTooltip } from "../ui/ChartTooltip";
import { Ring } from "../ui/Ring";
import { Stat } from "../ui/Stat";
import {
  COLORS,
  formatDuration,
  formatWeekday,
  greeting,
  recoveryColor,
  recoveryLabel,
  round,
  strainLabel,
} from "@/lib/format";
import type { DashboardData } from "@/lib/useDashboardData";
import type { Tab } from "../AppShell";

export function OverviewTab({ data, go }: { data: DashboardData; go: (tab: Tab) => void }) {
  const recovery = data.recovery[0];
  const sleep = data.sleep[0];
  const cycle = data.cycles[0];
  const dayStrain = cycle?.score ?? data.workouts[0]?.score ?? null;
  const asleep =
    sleep?.inBedMilli != null ? sleep.inBedMilli - (sleep.awakeMilli ?? 0) : null;
  const week = [...data.recovery.slice(0, 7)].reverse().map((r) => ({
    label: formatWeekday(r.recordedAt),
    score: r.score,
  }));
  const name = data.profile?.firstName;

  return (
    <div className="space-y-5">
      <div className="animate-fade-in-up">
        <p className="eyebrow">
          {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
        </p>
        <h1 className="mt-1 font-display text-3xl font-bold tracking-tight sm:text-4xl">
          {greeting()}
          {name ? `, ${name}` : ""}.{" "}
          <span style={{ color: recoveryColor(recovery?.score) }}>{recoveryLabel(recovery?.score)}</span>
          {recovery?.score != null && <span className="text-white/40"> today.</span>}
        </h1>
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-3" eyebrow="Today" title="Your day at a glance">
          <div className="flex flex-wrap items-center justify-around gap-6 py-2">
            <Ring
              value={recovery?.score ?? null}
              size={180}
              stroke={15}
              color={recoveryColor(recovery?.score)}
              label="Recovery"
              caption={recovery?.hrvRmssdMilli != null ? `HRV ${Math.round(recovery.hrvRmssdMilli)} ms` : undefined}
            />
            <div className="flex gap-6">
              <Ring
                value={dayStrain}
                max={21}
                size={124}
                stroke={11}
                color={[COLORS.strain, "#7CC4FF"]}
                label="Day strain"
                unit=""
                display={dayStrain?.toFixed(1)}
                caption={strainLabel(dayStrain)}
              />
              <Ring
                value={sleep?.score ?? null}
                size={124}
                stroke={11}
                color={[COLORS.sleep, "#C9C1FF"]}
                label="Sleep"
                caption={asleep != null ? formatDuration(asleep) : undefined}
              />
            </div>
          </div>
        </Card>
        <div className="lg:col-span-2">
          <FuelToday meals={data.meals} cycles={data.cycles} goal={data.goal} onLogMeal={() => go("fuel")} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="HRV" value={round(recovery?.hrvRmssdMilli)} unit="ms" icon={Activity} color={COLORS.recoveryHigh} />
        <Stat label="Resting HR" value={round(recovery?.restingHeartRate)} unit="bpm" icon={HeartPulse} color={COLORS.recoveryLow} />
        <Stat label="SpO₂" value={round(recovery?.spo2Percentage, 1)} unit="%" icon={Droplets} color={COLORS.strain} />
        <Stat label="Skin temp" value={round(recovery?.skinTempCelsius, 1)} unit="°C" icon={Thermometer} color={COLORS.fuel} />
        <Stat label="Resp. rate" value={round(sleep?.respiratoryRate, 1)} unit="rpm" icon={Wind} color={COLORS.sleep} />
        <Stat
          label="Sleep need"
          value={formatDuration(sleep?.sleepNeededMilli)}
          hint={asleep != null ? `slept ${formatDuration(asleep)}` : undefined}
          icon={Moon}
          color={COLORS.sleep}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card
          className="lg:col-span-3"
          eyebrow="Last 7 days"
          title="Recovery"
          action={
            <button onClick={() => go("recovery")} className="flex items-center gap-1 text-xs text-white/50 hover:text-white">
              Details <ArrowRight className="h-3.5 w-3.5" />
            </button>
          }
        >
          <div className="h-44">
            <ResponsiveContainer>
              <BarChart data={week}>
                <XAxis dataKey="label" {...AXIS} />
                <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<ChartTooltip format={(v) => `${v}%`} />} />
                <Bar dataKey="score" name="Recovery" radius={[8, 8, 8, 8]} maxBarSize={34}>
                  {week.map((d, i) => (
                    <Cell key={i} fill={recoveryColor(d.score)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <button
          onClick={() => go("insights")}
          className="glass group animate-fade-in-up relative overflow-hidden p-6 text-left lg:col-span-2"
        >
          <div className="pointer-events-none absolute -bottom-16 -right-16 h-48 w-48 rounded-full bg-sleep/20 blur-3xl" />
          <Sparkles className="h-5 w-5 text-sleep" />
          <p className="mt-3 font-display text-xl font-semibold">
            What does it all <span className="text-brand-gradient">mean</span>?
          </p>
          <p className="mt-1 text-sm text-white/55">
            Let AI connect your recovery, sleep, strain and meals into one plain-language read — daily,
            weekly or monthly.
          </p>
          <p className="mt-4 flex items-center gap-1 text-sm font-medium text-white/80 group-hover:text-white">
            Generate an insight <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
          </p>
        </button>
      </div>
    </div>
  );
}
