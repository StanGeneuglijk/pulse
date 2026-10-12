"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "../ui/Card";
import { AXIS, ChartTooltip, GRID } from "../ui/ChartTooltip";
import { Ring } from "../ui/Ring";
import { Stat } from "../ui/Stat";
import { COLORS, formatDay, formatDuration, formatTime, milliToHours, round } from "@/lib/format";
import type { DashboardData } from "@/lib/useDashboardData";

const STAGES = [
  { key: "awake", label: "Awake", color: "#5B6170" },
  { key: "light", label: "Light", color: "#C9C1FF" },
  { key: "deep", label: "Deep (SWS)", color: "#9B8CFF" },
  { key: "rem", label: "REM", color: "#FF2E93" },
] as const;

const hours = (milli: number | null | undefined) => {
  const h = milliToHours(milli);
  return h == null ? null : Math.round(h * 100) / 100;
};

export function SleepTab({ data }: { data: DashboardData }) {
  const last = data.sleep[0];
  const stages = last
    ? {
        awake: last.awakeMilli ?? 0,
        light: last.lightSleepMilli ?? 0,
        deep: last.slowWaveSleepMilli ?? 0,
        rem: last.remSleepMilli ?? 0,
      }
    : null;
  const stageTotal = stages ? Object.values(stages).reduce((a, b) => a + b, 0) : 0;
  const asleep = last?.inBedMilli != null ? last.inBedMilli - (last.awakeMilli ?? 0) : null;

  const nights = [...data.sleep.slice(0, 14)].reverse().map((s) => ({
    label: formatDay(s.recordedAt),
    awake: hours(s.awakeMilli),
    light: hours(s.lightSleepMilli),
    deep: hours(s.slowWaveSleepMilli),
    rem: hours(s.remSleepMilli),
    need: hours(s.sleepNeededMilli),
    performance: s.score,
    consistency: s.sleepConsistencyPercentage,
    efficiency: s.sleepEfficiencyPercentage != null ? Math.round(s.sleepEfficiencyPercentage) : null,
  }));

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-3">
        <Card
          eyebrow="Last night"
          title={last?.start && last?.end ? `${formatTime(last.start)} → ${formatTime(last.end)}` : "Sleep"}
        >
          <div className="flex justify-center py-2">
            <Ring
              value={last?.score ?? null}
              size={190}
              stroke={15}
              color={[COLORS.sleep, "#FF2E93"]}
              caption="performance"
            />
          </div>
        </Card>
        <Card eyebrow="Stages" title={`${formatDuration(asleep)} asleep`} className="lg:col-span-2">
          {stages && stageTotal > 0 ? (
            <>
              <div className="flex h-5 overflow-hidden rounded-full">
                {STAGES.map((s) => (
                  <div
                    key={s.key}
                    style={{ width: `${(stages[s.key] / stageTotal) * 100}%`, background: s.color }}
                    className="transition-all duration-1000"
                  />
                ))}
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {STAGES.map((s) => (
                  <div key={s.key}>
                    <p className="flex items-center gap-1.5 text-xs text-white/50">
                      <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                      {s.label}
                    </p>
                    <p className="font-display text-lg font-semibold">{formatDuration(stages[s.key])}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Need" value={formatDuration(last?.sleepNeededMilli)} />
                <Stat label="Efficiency" value={round(last?.sleepEfficiencyPercentage)} unit="%" />
                <Stat label="Consistency" value={round(last?.sleepConsistencyPercentage)} unit="%" />
                <Stat label="Disturbances" value={round(last?.disturbanceCount)} />
              </div>
            </>
          ) : (
            <p className="text-sm text-white/50">
              Stage data arrives with the next full sync — press refresh.
            </p>
          )}
        </Card>
      </div>

      <Card eyebrow="14 nights" title="Hours by stage">
        <div className="h-64">
          <ResponsiveContainer>
            <BarChart data={nights} margin={{ left: -20 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="label" {...AXIS} interval="preserveStartEnd" minTickGap={20} />
              <YAxis {...AXIS} />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.04)" }}
                content={<ChartTooltip format={(v) => formatDuration(v * 3_600_000)} />}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: "rgba(255,255,255,0.6)" }} iconType="circle" />
              {STAGES.map((s, i) => (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  stackId="sleep"
                  fill={s.color}
                  maxBarSize={26}
                  radius={i === STAGES.length - 1 ? [6, 6, 0, 0] : undefined}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card eyebrow="14 nights" title="Performance, consistency, efficiency">
        <div className="h-56">
          <ResponsiveContainer>
            <LineChart data={nights} margin={{ left: -20, right: 6 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="label" {...AXIS} interval="preserveStartEnd" minTickGap={20} />
              <YAxis {...AXIS} domain={[0, 100]} />
              <Tooltip content={<ChartTooltip format={(v) => `${v}%`} />} />
              <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
              <Line dataKey="performance" name="Performance" stroke={COLORS.sleep} strokeWidth={2.5} dot={false} connectNulls />
              <Line dataKey="consistency" name="Consistency" stroke="#FF2E93" strokeWidth={2} dot={false} connectNulls />
              <Line dataKey="efficiency" name="Efficiency" stroke="#22E57A" strokeWidth={2} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
