interface Payload {
  name?: string;
  value?: number | string;
  color?: string;
  payload?: Record<string, unknown>;
}

interface Props {
  active?: boolean;
  payload?: Payload[];
  label?: string;
  format?: (value: number, name: string) => string;
}

/** A dark, glassy tooltip for every Recharts chart. */
export function ChartTooltip({ active, payload, label, format }: Props) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-line bg-ink/95 px-3 py-2 text-xs shadow-glass backdrop-blur">
      {label && <p className="mb-1 text-white/50">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} className="flex items-center gap-2 tabular-nums">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span className="text-white/60">{p.name}</span>
          <span className="ml-auto font-medium">
            {typeof p.value === "number" && format ? format(p.value, p.name ?? "") : p.value}
          </span>
        </p>
      ))}
    </div>
  );
}

export const AXIS = {
  stroke: "rgba(255,255,255,0.25)",
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const;

export const GRID = { stroke: "rgba(255,255,255,0.05)", vertical: false } as const;
