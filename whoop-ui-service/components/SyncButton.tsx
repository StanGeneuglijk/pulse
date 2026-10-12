"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { useApiFetch } from "@/lib/demo/DemoContext";
import { formatRelativeTime } from "@/lib/format";

interface Props {
  lastSyncedAt: string | null;
  onSynced: () => void;
}

export function SyncButton({ lastSyncedAt, onSynced }: Props) {
  const apiFetch = useApiFetch();
  const [syncing, setSyncing] = useState(false);

  async function handleClick() {
    setSyncing(true);
    try {
      const res = await apiFetch("/api/whoop/sync", { method: "POST" });
      if (!res.ok) {
        setSyncing(false);
        return;
      }
      // The sync runs on a worker; refetch after a short wait.
      setTimeout(() => {
        onSynced();
        setSyncing(false);
      }, 5000);
    } catch {
      setSyncing(false);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={syncing}
      title={`Last synced ${formatRelativeTime(lastSyncedAt)}`}
      className="group flex items-center gap-2 rounded-full border border-line bg-white/[0.04] px-3 py-1.5 text-xs text-white/70 transition hover:bg-white/10 hover:text-white disabled:cursor-wait"
    >
      <RefreshCw className={`h-3.5 w-3.5 ${syncing ? "animate-spin text-recovery-high" : ""}`} />
      <span className="hidden sm:inline">{syncing ? "Syncing…" : formatRelativeTime(lastSyncedAt)}</span>
    </button>
  );
}
