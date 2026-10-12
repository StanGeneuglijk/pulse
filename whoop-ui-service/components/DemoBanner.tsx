"use client";

import { ArrowRight, FlaskConical, LogOut } from "lucide-react";
import { useDemo } from "@/lib/demo/DemoContext";
import { DEMO_PROFILE } from "@/lib/demo/data";

/**
 * Shown on every screen of the demo, and never dismissible, so a screenshot
 * of the demo always reads as sample data.
 */
export function DemoBanner() {
  const demo = useDemo();
  if (!demo) return null;

  async function leave() {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      window.location.href = "/login";
    }
  }

  return (
    <div className="border-t border-fuel-amber/20 bg-fuel-amber/[0.08]">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2 text-xs sm:px-6">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-fuel-amber/20 px-2 py-0.5 font-semibold uppercase tracking-wide text-fuel-amber">
          <FlaskConical className="h-3.5 w-3.5" /> Demo · sample data
        </span>
        <span className="text-white/60">
          You&apos;re exploring as {DEMO_PROFILE.firstName}, a sample person. AI answers are pre-written
          examples and nothing you do is saved.
        </span>
        <span className="ml-auto flex items-center gap-2">
          <a
            href="/demo/connect"
            className="inline-flex items-center gap-1 rounded-full bg-brand-gradient px-3 py-1 font-semibold text-black transition hover:brightness-110"
          >
            Connect your WHOOP <ArrowRight className="h-3.5 w-3.5" />
          </a>
          <button
            onClick={leave}
            className="inline-flex items-center gap-1 rounded-full border border-line px-3 py-1 text-white/70 transition hover:bg-white/10 hover:text-white"
          >
            <LogOut className="h-3.5 w-3.5" /> Leave demo
          </button>
        </span>
      </div>
    </div>
  );
}
