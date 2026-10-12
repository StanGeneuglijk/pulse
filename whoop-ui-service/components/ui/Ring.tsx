"use client";

import { useEffect, useId, useState } from "react";

interface Props {
  value: number | null;
  max?: number;
  size?: number;
  stroke?: number;
  /** A solid color, or [from, to] for a gradient arc. */
  color: string | [string, string];
  label?: string;
  display?: string;
  unit?: string;
  caption?: string;
}

/** WHOOP's signature gauge: an arc that fills in on mount. */
export function Ring({
  value,
  max = 100,
  size = 160,
  stroke = 12,
  color,
  label,
  display,
  unit = "%",
  caption,
}: Props) {
  const id = `ring-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = value == null ? 0 : Math.min(Math.max(value / max, 0), 1);
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const raf = requestAnimationFrame(() => setShown(pct));
    return () => cancelAnimationFrame(raf);
  }, [pct]);

  const [from, to] = Array.isArray(color) ? color : [color, color];
  const fontSize = Math.round(size * 0.25);

  return (
    <div className="flex flex-col items-center" style={{ width: size }}>
      <div
        className="relative"
        style={{
          width: size,
          height: size,
          // Glow on the wrapper, not the SVG arc: an SVG filter is clipped to
          // the shape's bounds and shows up as a faint square.
          filter: value != null ? `drop-shadow(0 0 14px ${from}55)` : undefined,
        }}
      >
        <svg width={size} height={size} className="-rotate-90">
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor={from} />
              <stop offset="100%" stopColor={to} />
            </linearGradient>
          </defs>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={stroke}
          />
          {value != null && (
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={`url(#${id})`}
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - shown)}
              style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(0.16, 1, 0.3, 1)" }}
            />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display font-bold tabular-nums" style={{ fontSize, lineHeight: 1 }}>
            {value == null ? "—" : (display ?? Math.round(value))}
            {value != null && unit && (
              <span className="ml-0.5 text-white/40" style={{ fontSize: fontSize * 0.4 }}>
                {unit}
              </span>
            )}
          </span>
          {caption && <span className="mt-1 text-[11px] text-white/50">{caption}</span>}
        </div>
      </div>
      {label && <p className="eyebrow mt-3">{label}</p>}
    </div>
  );
}
