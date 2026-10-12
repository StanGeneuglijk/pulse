"use client";

import { useCallback, useEffect, useState } from "react";
import type {
  CycleRecord,
  NutritionGoal,
  NutritionLogRecord,
  Profile,
  RecoveryRecord,
  SleepRecord,
  SyncLogEntry,
  WorkoutRecord,
} from "./types";
import { useApiFetch } from "./demo/DemoContext";
import { newestFirst } from "./format";

export interface DashboardData {
  recovery: RecoveryRecord[];
  sleep: SleepRecord[]; // main sleeps only, newest first (naps excluded)
  naps: SleepRecord[];
  workouts: WorkoutRecord[];
  cycles: CycleRecord[];
  profile: Profile | null;
  syncs: SyncLogEntry[];
  meals: NutritionLogRecord[];
  goal: NutritionGoal | null;
}

const EMPTY: DashboardData = {
  recovery: [],
  sleep: [],
  naps: [],
  workouts: [],
  cycles: [],
  profile: null,
  syncs: [],
  meals: [],
  goal: null,
};

async function json<T>(res: Response, fallback: T): Promise<T> {
  if (!res.ok) return fallback;
  const body = await res.json().catch(() => fallback);
  return body ?? fallback;
}

/** Everything the dashboard shows, loaded in parallel. A 401 means the
 * session is gone, so the browser goes back to /login. */
export function useDashboardData() {
  const [data, setData] = useState<DashboardData>(EMPTY);
  const [loading, setLoading] = useState(true);
  const apiFetch = useApiFetch();

  const reload = useCallback(async () => {
    const responses = await Promise.all(
      [
        "/api/whoop/recovery",
        "/api/whoop/sleep",
        "/api/whoop/workout",
        "/api/whoop/cycles",
        "/api/whoop/profile",
        "/api/whoop/syncs",
        "/api/nutrition/meals/list?days=30",
        "/api/nutrition/goal",
      ].map((url) => apiFetch(url))
    );
    if (responses[0].status === 401) {
      window.location.href = "/login";
      return;
    }
    const [recovery, sleep, workouts, cycles, profile, syncs, meals, goal] = await Promise.all([
      json<RecoveryRecord[]>(responses[0], []),
      json<SleepRecord[]>(responses[1], []),
      json<WorkoutRecord[]>(responses[2], []),
      json<CycleRecord[]>(responses[3], []),
      json<Profile | null>(responses[4], null),
      json<SyncLogEntry[]>(responses[5], []),
      json<NutritionLogRecord[]>(responses[6], []),
      json<NutritionGoal | null>(responses[7], null),
    ]);
    const sleeps = newestFirst(sleep);
    setData({
      recovery: newestFirst(recovery),
      sleep: sleeps.filter((s) => !s.nap),
      naps: sleeps.filter((s) => s.nap),
      workouts: newestFirst(workouts),
      cycles: newestFirst(cycles),
      profile,
      syncs,
      meals: [...meals].sort((a, b) => b.loggedAt.localeCompare(a.loggedAt)),
      // The goal route answers {} when there's none.
      goal: goal && "goalType" in goal ? goal : null,
    });
    setLoading(false);
  }, [apiFetch]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, loading, reload };
}
