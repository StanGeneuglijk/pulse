"use client";

import { useEffect, useState } from "react";
import { AppShell, TABS, type Tab } from "./AppShell";
import { FuelTab } from "./tabs/FuelTab";
import { InsightsTab } from "./tabs/InsightsTab";
import { OverviewTab } from "./tabs/OverviewTab";
import { RecoveryTab } from "./tabs/RecoveryTab";
import { SleepTab } from "./tabs/SleepTab";
import { StrainTab } from "./tabs/StrainTab";
import { DemoProvider } from "@/lib/demo/DemoContext";
import { useDashboardData } from "@/lib/useDashboardData";

function Skeleton() {
  return (
    <div className="space-y-5">
      <div className="h-10 w-2/3 animate-pulse-soft rounded-xl bg-white/[0.05]" />
      <div className="grid gap-5 lg:grid-cols-5">
        <div className="glass h-72 animate-pulse-soft lg:col-span-3" />
        <div className="glass h-72 animate-pulse-soft lg:col-span-2" />
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="glass h-24 animate-pulse-soft" />
        ))}
      </div>
    </div>
  );
}

/** `demo` swaps every /api call for the in-browser fake (lib/demo/fakeApi.ts). */
export function Dashboard({ demo = false }: { demo?: boolean }) {
  return (
    <DemoProvider demo={demo}>
      <DashboardBody />
    </DemoProvider>
  );
}

function DashboardBody() {
  const { data, loading, reload } = useDashboardData();
  const [tab, setTab] = useState<Tab>("overview");

  // The tab lives in the URL hash, so reloads and the back button keep it.
  useEffect(() => {
    const fromHash = window.location.hash.slice(1) as Tab;
    if (TABS.some((t) => t.id === fromHash)) setTab(fromHash);
    const onHash = () => {
      const h = window.location.hash.slice(1) as Tab;
      if (TABS.some((t) => t.id === h)) setTab(h);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function go(next: Tab) {
    setTab(next);
    window.history.pushState(null, "", `#${next}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <AppShell
      tab={tab}
      onTab={go}
      profile={data.profile}
      lastSyncedAt={data.syncs[0]?.createdAt ?? null}
      onSynced={reload}
    >
      {loading ? (
        <Skeleton />
      ) : (
        <div key={tab}>
          {tab === "overview" && <OverviewTab data={data} go={go} />}
          {tab === "fuel" && <FuelTab data={data} reload={reload} />}
          {tab === "recovery" && <RecoveryTab data={data} />}
          {tab === "sleep" && <SleepTab data={data} />}
          {tab === "strain" && <StrainTab data={data} />}
          {tab === "insights" && <InsightsTab />}
        </div>
      )}
    </AppShell>
  );
}
