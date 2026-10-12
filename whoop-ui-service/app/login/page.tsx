import { ArrowRight, HeartPulse, Mic, PlayCircle, Sparkles } from "lucide-react";
import { redirect } from "next/navigation";
import { Logomark } from "@/components/Logomark";
import { BRAND } from "@/lib/brand";
import { config } from "@/lib/config";
import { getCaller } from "@/lib/session";

const ERROR_MESSAGES: Record<string, string> = {
  missing_code: "That link was missing its login code — try connecting again.",
  exchange_failed: "That login link already expired or was already used — try connecting again.",
  cookies_blocked: "The demo needs cookies — allow them for this site and try again.",
};

const FEATURES = [
  {
    icon: HeartPulse,
    title: "Every WHOOP metric",
    body: "Recovery, HRV, sleep stages, day strain, workouts and heart-rate zones — synced and charted.",
    accent: "text-recovery-high",
    fuel: false,
  },
  {
    icon: Mic,
    title: "Talk. It logs your food.",
    body: "Say what you ate. AI breaks it into calories and macros, you confirm — and it sits next to what you burned.",
    accent: "text-fuel",
    fuel: true,
  },
  {
    icon: Sparkles,
    title: "Insights that connect it all",
    body: "AI reads recovery, sleep, strain and meals together and tells you the one thing to do next.",
    accent: "text-sleep",
    fuel: false,
  },
];

export default function LoginPage({ searchParams }: { searchParams: { error?: string } }) {
  if (getCaller()) {
    redirect("/");
  }
  const error = searchParams.error ? ERROR_MESSAGES[searchParams.error] : null;

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8">
      <header className="flex items-center gap-2.5">
        <Logomark size={34} />
        <span className="font-display text-xl font-bold tracking-tight">{BRAND.name}</span>
      </header>

      <section className="flex flex-1 flex-col items-center justify-center py-16 text-center">
        <span className="animate-fade-in-up inline-flex items-center gap-2 rounded-full border border-fuel/30 bg-fuel/10 px-3 py-1 text-xs font-medium text-fuel-amber">
          <Sparkles className="h-3.5 w-3.5" /> New: AI nutrition, by voice
        </span>
        <h1
          className="animate-fade-in-up mt-6 max-w-3xl font-display text-5xl font-bold leading-[1.05] tracking-tight sm:text-7xl"
          style={{ animationDelay: "60ms" }}
        >
          Your WHOOP, decoded.
          <br />
          <span className="text-fuel-gradient">Your fuel, dialed in.</span>
        </h1>
        <p
          className="animate-fade-in-up mt-6 max-w-xl text-lg text-white/60"
          style={{ animationDelay: "120ms" }}
        >
          Connect WHOOP once. See every metric, log meals by just talking, and get AI insights that
          finally connect how you train, sleep and eat.
        </p>

        {error && (
          <p className="mt-6 rounded-xl border border-recovery-low/30 bg-recovery-low/10 px-4 py-2 text-sm text-recovery-low">
            {error}
          </p>
        )}

        <div
          className="animate-fade-in-up mt-10 flex flex-col items-center gap-3 sm:flex-row"
          style={{ animationDelay: "180ms" }}
        >
          <a
            href={`${config.whoopServiceUrl}/auth/login`}
            className="group inline-flex items-center gap-2 rounded-2xl bg-brand-gradient px-7 py-4 font-display text-lg font-semibold text-black shadow-[0_0_60px_-10px_rgba(58,160,255,0.6)] transition hover:brightness-110"
          >
            Connect WHOOP
            <ArrowRight className="h-5 w-5 transition group-hover:translate-x-1" />
          </a>
          <a
            href="/demo/start"
            className="inline-flex items-center gap-2 rounded-2xl border border-line bg-white/[0.04] px-7 py-4 font-display text-lg font-semibold text-white/85 transition hover:bg-white/10 hover:text-white"
          >
            <PlayCircle className="h-5 w-5" />
            Try the demo
          </a>
        </div>
        <p className="mt-3 text-xs text-white/35">
          Read-only access. Your WHOOP password never touches us. No WHOOP? The demo shows the whole app
          with sample data.
        </p>

        <div className="mt-20 grid w-full gap-4 text-left sm:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body, accent, fuel }, i) => (
            <div
              key={title}
              className={`animate-fade-in-up ${fuel ? "rounded-3xl bg-fuel-gradient p-[1.5px] shadow-fuel" : ""}`}
              style={{ animationDelay: `${240 + i * 80}ms` }}
            >
              <div className={`h-full p-6 ${fuel ? "rounded-[23px] bg-ink" : "glass"}`}>
                <Icon className={`h-6 w-6 ${accent}`} />
                <p className="mt-4 font-display text-lg font-semibold">{title}</p>
                <p className="mt-1.5 text-sm text-white/55">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
