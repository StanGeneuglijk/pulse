"use client";

import { LogOut } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useDemo } from "@/lib/demo/DemoContext";
import type { Profile } from "@/lib/types";

export function UserMenu({ profile }: { profile: Profile | null }) {
  const demo = useDemo();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const initials =
    [profile?.firstName, profile?.lastName].map((n) => n?.[0] ?? "").join("").toUpperCase() || "ME";

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  async function logout() {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      window.location.href = "/login";
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-gradient p-[1.5px]"
      >
        <span className="flex h-full w-full items-center justify-center rounded-full bg-ink font-display text-xs font-bold">
          {initials}
        </span>
      </button>
      {open && (
        <div className="absolute right-0 top-11 z-50 w-56 rounded-2xl border border-line bg-ink/95 p-2 shadow-glass backdrop-blur-xl">
          <div className="px-3 py-2">
            <p className="font-medium">
              {[profile?.firstName, profile?.lastName].filter(Boolean).join(" ") || "Your account"}
            </p>
            {profile?.weightKilogram != null && (
              <p className="text-xs text-white/45">
                {profile.weightKilogram.toFixed(1)} kg
                {profile.heightMeter != null && ` · ${Math.round(profile.heightMeter * 100)} cm`}
                {profile.maxHeartRate != null && ` · max HR ${profile.maxHeartRate}`}
              </p>
            )}
          </div>
          <button
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-white/70 hover:bg-white/5 hover:text-white"
          >
            <LogOut className="h-4 w-4" /> {demo ? "Leave demo" : "Log out"}
          </button>
        </div>
      )}
    </div>
  );
}
