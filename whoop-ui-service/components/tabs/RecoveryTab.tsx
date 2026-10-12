"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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
import { COLORS, formatDay, recoveryColor, recoveryLabel, round } from "@/lib/format";
import type { DashboardData } from "@/lib/useDashboardData";

function avg(values: (number | null)[]): number | null {
  const v = values.filter((x): x is number => x != null);
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
}

export function RecoveryTab({ data }: { data: DashboardData }) {
  const latest = data.recovery[0];
  const month = [...data.recovery.slice(0, 30)].reverse().map((r) => ({
    label: formatDay(r.recordedAt),
    score: r.score,
    hrv: r.hrvRmssdMilli != null ? Math.round(r.hrvRmssdMilli) : null,
    rhr: r.restingHeartRate,
  }));
  const hrv7 = avg(data.recovery.slice(0, 7).map((r) => r.hrvRmssdMilli));
  const hrv30 = avg(data.recovery.slice(0, 30).map((r) => r.hrvRmssdMilli));
  const rhr7 = avg(data.recovery.slice(0, 7).map((r) => r.restingHeartRate));
  const rec30 = avg(data.recovery.slice(0, 30).map((r) => r.score));
  const green = data.recovery.slice(0, 30).filter((r) => (r.score ?? 0) >= 67).length;

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-3">
        <Card eyebrow="Today" title={recoveryLabel(latest?.score)}>
          <div className="flex justify-center py-2">
            <Ring value={latest?.score ?? null} size={200} stroke={16} color={recoveryColor(latest?.score)} />
          </div>
          {latest?.userCalibrating && (
            <p className="mt-2 text-center text-xs text-white/40">WHOOP is still calibrating to you.</p>
          )}
        </Card>
        <div className="grid grid-cols-2 gap-3 lg:col-span-2">
          <Stat label="HRV · 7d avg" value={round(hrv7)} unit="ms" hint={`30d avg ${round(hrv30)} ms`} color={COLORS.recoveryHigh} />
          <Stat label="Resting HR · 7d" value={round(rhr7)} unit="bpm" color={COLORS.recoveryLow} />
          <Stat label="Recovery · 30d avg" value={round(rec30)} unit="%" color={recoveryColor(rec30)} />
          <Stat label="Green days · 30d" value={`${green}`} hint="recovery ≥ 67%" color={COLORS.recoveryHigh} />
        </div>
      </div>

      <Card eyebrow="30 days" title="Recovery score">
        <div className="h-56">
          <ResponsiveContainer>
            <BarChart data={month} margin={{ left: -20 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="label" {...AXIS} interval="preserveStartEnd" minTickGap={24} />
              <YAxis {...AXIS} domain={[0, 100]} />
              <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<ChartTooltip format={(v) => `${v}%`} />} />
              <Bar dataKey="score" name="Recovery" radius={[5, 5, 0, 0]} maxBarSize={18}>
                {month.map((d, i) => (
                  <Cell key={i} fill={recoveryColor(d.score)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        {(
          [
            ["hrv", "Heart rate variability", "ms", COLORS.recoveryHigh],
            ["rhr", "Resting heart rate", "bpm", COLORS.recoveryLow],
          ] as const
        ).map(([key, title, unit, color]) => (
          <Card key={key} eyebrow="30 days" title={title}>
            <div className="h-48">
              <ResponsiveContainer>
                <LineChart data={month} margin={{ left: -20, right: 6 }}>
                  <CartesianGrid {...GRID} />
                  <XAxis dataKey="label" {...AXIS} interval="preserveStartEnd" minTickGap={24} />
                  <YAxis {...AXIS} domain={["dataMin - 5", "dataMax + 5"]} />
                  <Tooltip content={<ChartTooltip format={(v) => `${Math.round(v)} ${unit}`} />} />
                  <Line
                    dataKey={key}
                    name={title}
                    stroke={color}
                    strokeWidth={2.5}
                    dot={false}
                    connectNulls
                    style={{ filter: `drop-shadow(0 0 6px ${color}90)` }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
