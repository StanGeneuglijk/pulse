"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Card } from "../ui/Card";
import { useApiFetch } from "@/lib/demo/DemoContext";
import { formatDay, formatUsd } from "@/lib/format";
import type { InsightPeriod, InsightRecord, InsightUsage } from "@/lib/types";

const PERIODS: { value: InsightPeriod; label: string; blurb: string }[] = [
  { value: "daily", label: "Today", blurb: "A quick read on the last 24 hours" },
  { value: "weekly", label: "This week", blurb: "Trends across your last 7 days" },
  { value: "monthly", label: "This month", blurb: "The big picture over 30 days" },
];

export function InsightsTab() {
  const apiFetch = useApiFetch();
  const [period, setPeriod] = useState<InsightPeriod>("weekly");
  const [insight, setInsight] = useState<InsightRecord | null>(null);
  const [history, setHistory] = useState<InsightRecord[]>([]);
  const [usage, setUsage] = useState<InsightUsage | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingLatest, setLoadingLatest] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load(p: InsightPeriod) {
    setLoadingLatest(true);
    const [latest, list, use] = await Promise.all([
      apiFetch(`/api/insight/latest?period=${p}`),
      apiFetch(`/api/insight/list?period=${p}`),
      apiFetch("/api/insight/usage"),
    ]);
    const latestBody = latest.ok ? await latest.json() : null;
    setInsight(latestBody && latestBody.content ? latestBody : null);
    setHistory(list.ok ? await list.json() : []);
    setUsage(use.ok ? await use.json() : null);
    setLoadingLatest(false);
  }

  useEffect(() => {
    void load(period);
  }, [period]);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/insight/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? `Failed with status ${res.status}`);
        return;
      }
      setInsight(data);
      void load(period);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="animate-fade-in-up">
        <p className="eyebrow">AI insights</p>
        <h2 className="mt-1 font-display text-3xl font-bold tracking-tight">
          Your numbers, <span className="text-brand-gradient">in plain words</span>.
        </h2>
        <p className="mt-1 text-sm text-white/55">
          Recovery, sleep, strain and what you ate — read together by AI, ending in one thing to do next.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {PERIODS.map((p) => (
          <button
            key={p.value}
            onClick={() => setPeriod(p.value)}
            className={`glass p-4 text-left transition ${
              period === p.value ? "border-sleep/60 bg-sleep/10" : "hover:bg-white/[0.05]"
            }`}
          >
            <p className="font-display font-semibold">{p.label}</p>
            <p className="text-xs text-white/50">{p.blurb}</p>
          </button>
        ))}
      </div>

      <button
        onClick={generate}
        disabled={loading}
        className="relative flex w-full items-center justify-center gap-2 overflow-hidden rounded-2xl bg-brand-gradient px-5 py-4 font-display text-lg font-semibold text-black transition hover:brightness-110 disabled:opacity-70"
      >
        {loading && (
          <span className="absolute inset-0 animate-shimmer bg-[linear-gradient(110deg,transparent,rgba(255,255,255,0.45),transparent)] bg-[length:200%_100%]" />
        )}
        {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Sparkles className="h-5 w-5" />}
        {loading ? "Reading your data…" : "Generate insight"}
      </button>

      {error && (
        <p className="rounded-xl border border-recovery-low/30 bg-recovery-low/10 px-4 py-3 text-sm text-recovery-low">
          {error}
        </p>
      )}

      <Card eyebrow={PERIODS.find((p) => p.value === period)?.label} title="Latest insight">
        {loadingLatest ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-4 animate-pulse-soft rounded bg-white/[0.06]" style={{ width: `${90 - i * 15}%` }} />
            ))}
          </div>
        ) : insight ? (
          <div>
            <p className="whitespace-pre-wrap font-display text-lg leading-relaxed text-white/90">
              {insight.content}
            </p>
            <p className="mt-4 text-xs text-white/40">
              {formatDay(insight.periodStart)} – {formatDay(insight.periodEnd)} · {insight.modelName}
            </p>
          </div>
        ) : (
          <p className="text-sm text-white/50">Nothing yet for this period — generate one above.</p>
        )}
      </Card>

      {history.length > 1 && (
        <Card eyebrow="History" title="Earlier insights">
          <ul className="space-y-4">
            {history.slice(1, 6).map((h) => (
              <li key={h.id} className="border-l-2 border-sleep/40 pl-4">
                <p className="text-xs text-white/40">
                  {formatDay(h.periodStart)} – {formatDay(h.periodEnd)}
                </p>
                <p className="mt-1 text-sm text-white/75">{h.content}</p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {usage && (
        <p className="text-center text-xs text-white/35">
          {usage.totalGenerated} insights generated · {formatUsd(usage.spendUsd)} of AI spend
        </p>
      )}
    </div>
  );
}
