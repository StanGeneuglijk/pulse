// The backends return naive UTC timestamps ("2026-09-01T07:00:00"); without
// an explicit zone the browser would read them as local time.
export function parseUtc(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const diffSec = Math.round((Date.now() - parseUtc(iso).getTime()) / 1000);
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

export function formatDay(iso: string): string {
  return parseUtc(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function formatWeekday(iso: string): string {
  return parseUtc(iso).toLocaleDateString(undefined, { weekday: "short" });
}

export function formatTime(iso: string): string {
  return parseUtc(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/** "7h 32m" */
export function formatDuration(milli: number | null | undefined): string {
  if (milli == null) return "—";
  const totalMin = Math.round(milli / 60000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return h > 0 ? `${h}h ${m.toString().padStart(2, "0")}m` : `${m}m`;
}

export const milliToHours = (milli: number | null | undefined) =>
  milli == null ? null : milli / 3_600_000;

export const kjToKcal = (kj: number | null | undefined) =>
  kj == null ? null : Math.round(kj / 4.184);

export function isToday(iso: string): boolean {
  const d = parseUtc(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

/** Local calendar-day key, for grouping records by day. */
export function dayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

export function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export const COLORS = {
  recoveryHigh: "#22E57A",
  recoveryMid: "#FFD60A",
  recoveryLow: "#FF3B5C",
  strain: "#3AA0FF",
  sleep: "#9B8CFF",
  fuel: "#FF6B3D",
  fuelPink: "#FF2E93",
  muted: "#5B6170",
};

// WHOOP's recovery bands: green >=67, yellow 34-66, red <34. Sleep
// performance uses the same 0-100 bands.
export function recoveryColor(score: number | null | undefined): string {
  if (score == null) return COLORS.muted;
  if (score >= 67) return COLORS.recoveryHigh;
  if (score >= 34) return COLORS.recoveryMid;
  return COLORS.recoveryLow;
}

export function recoveryLabel(score: number | null | undefined): string {
  if (score == null) return "No data";
  if (score >= 67) return "Primed";
  if (score >= 34) return "Steady";
  return "Take it easy";
}

export function strainLabel(strain: number | null | undefined): string {
  if (strain == null) return "No data";
  if (strain >= 18) return "All out";
  if (strain >= 14) return "Strenuous";
  if (strain >= 10) return "Moderate";
  return "Light";
}

export function sportLabel(name: string | null): string {
  if (!name) return "Activity";
  return name.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatUsd(value: number): string {
  return `$${value.toFixed(value < 1 ? 3 : 2)}`;
}

export function round(value: number | null | undefined, digits = 0): string {
  return value == null ? "—" : value.toFixed(digits);
}

/** Newest-first records, sorted by their UTC timestamp. */
export function newestFirst<T extends { recordedAt: string }>(records: T[]): T[] {
  return [...records].sort(
    (a, b) => parseUtc(b.recordedAt).getTime() - parseUtc(a.recordedAt).getTime()
  );
}
