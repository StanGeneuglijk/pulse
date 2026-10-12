import type { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: string;
  unit?: string;
  hint?: string;
  icon?: LucideIcon;
  color?: string;
}

export function Stat({ label, value, unit, hint, icon: Icon, color = "#ffffff" }: Props) {
  return (
    <div className="glass animate-fade-in-up p-4">
      <div className="flex items-center justify-between">
        <p className="eyebrow">{label}</p>
        {Icon && <Icon className="h-4 w-4" style={{ color }} />}
      </div>
      <p className="mt-2 font-display text-2xl font-semibold tabular-nums">
        {value}
        {unit && value !== "—" && <span className="ml-1 text-sm text-white/40">{unit}</span>}
      </p>
      {hint && <p className="mt-0.5 text-xs text-white/40">{hint}</p>}
    </div>
  );
}
