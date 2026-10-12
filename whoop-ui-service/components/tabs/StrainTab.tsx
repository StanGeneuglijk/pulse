"use client";

import { Clock, Flame, HeartPulse, MapPin, Mountain } from "lucide-react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "../ui/Card";
import { AXIS, ChartTooltip, GRID } from "../ui/ChartTooltip";
import { Ring } from "../ui/Ring";
import {
  COLORS,
  formatDay,
  formatDuration,
  kjToKcal,
  parseUtc,
  sportLabel,
  strainLabel,
} from "@/lib/format";
import type { DashboardData } from "@/lib/useDashboardData";
import type { WorkoutRecord } from "@/lib/types";

const ZONE_COLORS = ["#3a3f4b", "#6B7280", "#3AA0FF", "#22E57A", "#FFD60A", "#FF3B5C"];

function ZoneBar({ zones }: { zones: (number | null)[] | null }) {
  const values = (zones ?? []).map((z) => z ?? 0);
  const total = values.reduce((a, b) => a + b, 0);
  if (!total) return null;
  return (
    <div className="mt-3">
      <div className="flex h-2 overflow-hidden rounded-full">
        {values.map((v, i) => (
          <div key={i} style={{ width: `${(v / total) * 100}%`, background: ZONE_COLORS[i] }} />
        ))}
      </div>
      <p className="mt-1 text-[10px] text-white/35">Heart-rate zones 0–5</p>
    </div>
  );
}

function WorkoutCard({ w }: { w: WorkoutRecord }) {
  const duration =
    w.start && w.end ? parseUtc(w.end).getTime() - parseUtc(w.start).getTime() : null;
  const kcal = kjToKcal(w.kilojoule);
  return (
    <div className="glass animate-fade-in-up p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-display font-semibold">{sportLabel(w.sportName)}</p>
          <p className="text-xs text-white/45">{formatDay(w.start ?? w.recordedAt)}</p>
        </div>
        <span
          className="rounded-full px-2.5 py-1 font-display text-sm font-bold tabular-nums"
          style={{ background: `${COLORS.strain}22`, color: COLORS.strain }}
        >
          {w.score?.toFixed(1) ?? "—"}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs text-white/60">
        <span className="flex items-center gap-1.5">
          <Clock className="h-3.5 w-3.5" /> {formatDuration(duration)}
        </span>
        <span className="flex items-center gap-1.5">
          <Flame className="h-3.5 w-3.5 text-fuel" /> {kcal != null ? `${kcal} kcal` : "—"}
        </span>
        <span className="flex items-center gap-1.5">
          <HeartPulse className="h-3.5 w-3.5 text-recovery-low" /> {w.averageHeartRate ?? "—"} avg ·{" "}
          {w.maxHeartRate ?? "—"} max
        </span>
        {w.distanceMeter ? (
          <span className="flex items-center gap-1.5">
            <MapPin className="h-3.5 w-3.5" /> {(w.distanceMeter / 1000).toFixed(2)} km
          </span>
        ) : w.altitudeGainMeter ? (
          <span className="flex items-center gap-1.5">
            <Mountain className="h-3.5 w-3.5" /> {Math.round(w.altitudeGainMeter)} m
          </span>
        ) : null}
      </div>
      <ZoneBar zones={w.zoneDurationsMilli} />
    </div>
  );
}

export function StrainTab({ data }: { data: DashboardData }) {
  const today = data.cycles[0];
  const month = [...data.cycles.slice(0, 30)].reverse().map((c) => ({
    label: formatDay(c.start ?? c.recordedAt),
    strain: c.score != null ? Math.round(c.score * 10) / 10 : null,
    kcal: kjToKcal(c.kilojoule),
  }));
  const strain = today?.score ?? data.workouts[0]?.score ?? null;

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-3">
        <Card eyebrow="Today" title={strainLabel(strain)}>
          <div className="flex justify-center py-2">
            <Ring
              value={strain}
              max={21}
              size={190}
              stroke={15}
              color={[COLORS.strain, "#7CC4FF"]}
              unit=""
              display={strain?.toFixed(1)}
              caption={today?.kilojoule != null ? `${kjToKcal(today.kilojoule)} kcal burned` : "day strain"}
            />
          </div>
        </Card>
        <Card eyebrow="30 days" title="Day strain & energy" className="lg:col-span-2">
          {month.length ? (
            <div className="h-56">
              <ResponsiveContainer>
                <ComposedChart data={month} margin={{ left: -20, right: -12 }}>
                  <CartesianGrid {...GRID} />
                  <XAxis dataKey="label" {...AXIS} interval="preserveStartEnd" minTickGap={24} />
                  <YAxis yAxisId="s" {...AXIS} domain={[0, 21]} />
                  <YAxis yAxisId="k" orientation="right" {...AXIS} />
                  <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<ChartTooltip />} />
                  <Bar yAxisId="s" dataKey="strain" name="Strain" fill={COLORS.strain} radius={[5, 5, 0, 0]} maxBarSize={16} />
                  <Line yAxisId="k" dataKey="kcal" name="kcal" stroke={COLORS.fuel} strokeWidth={2} dot={false} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-white/50">
              Day strain needs the <span className="text-white">cycles</span> permission — log out and
              reconnect WHOOP once to grant it.
            </p>
          )}
        </Card>
      </div>

      <div>
        <p className="eyebrow mb-3">Workouts</p>
        {data.workouts.length === 0 ? (
          <p className="text-sm text-white/50">No workouts synced yet.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.workouts.slice(0, 12).map((w) => (
              <WorkoutCard key={w.id} w={w} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
