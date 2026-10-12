"use client";

import { Activity, Flame, HeartPulse, LayoutGrid, Moon, Sparkles, Utensils } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { DemoBanner } from "./DemoBanner";
import { Logomark } from "./Logomark";
import { SyncButton } from "./SyncButton";
import { UserMenu } from "./UserMenu";
import { BRAND } from "@/lib/brand";
import type { Profile } from "@/lib/types";

export type Tab = "overview" | "fuel" | "recovery" | "sleep" | "strain" | "insights";

export const TABS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: "overview", label: "Today", icon: LayoutGrid },
  { id: "fuel", label: "Fuel", icon: Utensils },
  { id: "recovery", label: "Recovery", icon: HeartPulse },
  { id: "sleep", label: "Sleep", icon: Moon },
  { id: "strain", label: "Strain", icon: Activity },
  { id: "insights", label: "Insights", icon: Sparkles },
];

interface Props {
  tab: Tab;
  onTab: (tab: Tab) => void;
  profile: Profile | null;
  lastSyncedAt: string | null;
  onSynced: () => void;
  children: ReactNode;
}

export function AppShell({ tab, onTab, profile, lastSyncedAt, onSynced, children }: Props) {
  return (
    <div className="min-h-screen pb-28 lg:pb-12">
      <header className="sticky top-0 z-40 border-b border-line bg-base/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 sm:px-6">
          <button onClick={() => onTab("overview")} className="flex items-center gap-2.5">
            <Logomark size={32} />
            <span className="font-display text-lg font-bold tracking-tight">{BRAND.name}</span>
          </button>

          <nav className="ml-4 hidden items-center gap-1 lg:flex">
            {TABS.map(({ id, label, icon: Icon }) => {
              const active = tab === id;
              if (id === "fuel") {
                return (
                  <button
                    key={id}
                    onClick={() => onTab(id)}
                    className={`relative flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-semibold transition ${
                      active ? "bg-fuel-gradient text-black shadow-fuel" : "text-fuel-amber hover:bg-fuel/10"
                    }`}
                  >
                    <Flame className="h-4 w-4" /> {label}
                    <span className="absolute -right-1 -top-1.5 rounded-full bg-fuel-pink px-1.5 text-[9px] font-bold uppercase leading-4 text-white">
                      new
                    </span>
                  </button>
                );
              }
              return (
                <button
                  key={id}
                  onClick={() => onTab(id)}
                  className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm transition ${
                    active ? "bg-white/10 text-white" : "text-white/55 hover:bg-white/5 hover:text-white"
                  }`}
                >
                  <Icon className="h-4 w-4" /> {label}
                </button>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <SyncButton lastSyncedAt={lastSyncedAt} onSynced={onSynced} />
            <UserMenu profile={profile} />
          </div>
        </div>
        <DemoBanner />
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>

      {/* Mobile tab bar — Fuel sits in the middle, raised. */}
      <nav className="fixed inset-x-3 bottom-3 z-40 flex items-center justify-around rounded-3xl border border-line bg-ink/85 px-2 py-2 shadow-glass backdrop-blur-xl lg:hidden">
        {TABS.map(({ id, label, icon: Icon }) =>
          id === "fuel" ? (
            <button
              key={id}
              onClick={() => onTab(id)}
              className="-mt-8 flex h-14 w-14 flex-col items-center justify-center rounded-2xl bg-fuel-gradient text-black shadow-fuel"
            >
              <Flame className="h-5 w-5" />
              <span className="text-[10px] font-bold">{label}</span>
            </button>
          ) : (
            <button
              key={id}
              onClick={() => onTab(id)}
              className={`flex flex-col items-center gap-0.5 px-2 py-1 text-[10px] ${
                tab === id ? "text-white" : "text-white/45"
              }`}
            >
              <Icon className="h-5 w-5" />
              {label}
            </button>
          )
        )}
      </nav>
    </div>
  );
}
