"use client";

import { Check, Loader2, Mic, Send, Sparkles, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useApiFetch, useDemo } from "@/lib/demo/DemoContext";
import { DEMO_CHAT_PREFILL } from "@/lib/demo/script";
import type { ChatResponse, MealProposal } from "@/lib/types";

interface ChatEntry {
  role: "user" | "assistant";
  text: string;
  voice?: boolean;
}

const SUGGESTIONS = [
  "Two eggs, sourdough toast and a flat white",
  "Chicken burrito bowl with rice and guac",
  "Protein shake with a banana after my run",
];

interface Props {
  onLogged: () => void;
  autoFocus?: boolean;
  compact?: boolean;
}

export function MealChat({ onLogged, autoFocus, compact }: Props) {
  const apiFetch = useApiFetch();
  // In the demo the chat opens on the example exchange, and the mic replays
  // it without ever asking for microphone access.
  const demo = useDemo();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [entries, setEntries] = useState<ChatEntry[]>(() => (demo ? DEMO_CHAT_PREFILL(new Date()) : []));
  const [pendingMeal, setPendingMeal] = useState<MealProposal | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  // Recording spans several renders; the in-flight conversation id lives in a
  // ref so the recorder's onstop callback never sees a stale value.
  const conversationIdRef = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [entries, pendingMeal, sending]);

  function applyChatResponse(userText: string, data: ChatResponse, voice = false) {
    conversationIdRef.current = data.conversationId;
    setConversationId(data.conversationId);
    setEntries((prev) => [
      ...prev,
      { role: "user", text: userText, voice },
      ...(data.reply ? [{ role: "assistant" as const, text: data.reply }] : []),
    ]);
    setPendingMeal(data.pendingMeal);
  }

  async function sendText(text?: string) {
    const message = (text ?? input).trim();
    if (!message || sending) return;
    setSending(true);
    setError(null);
    setInput("");
    try {
      const res = await apiFetch("/api/nutrition/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversationId, message }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? `Failed with status ${res.status}`);
        return;
      }
      applyChatResponse(message, data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSending(false);
    }
  }

  async function sendAudio(blob: Blob) {
    setSending(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("audio", blob, "recording.webm");
      if (conversationIdRef.current) form.append("conversationId", conversationIdRef.current);
      const res = await apiFetch("/api/nutrition/chat/audio", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? `Failed with status ${res.status}`);
        return;
      }
      applyChatResponse(data.transcript ?? "(voice message)", data, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSending(false);
    }
  }

  const startRecording = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        void sendAudio(new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" }));
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setError("Couldn't access the microphone — check the browser's permission prompt.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  async function resolveMeal(action: "confirm" | "discard") {
    if (!conversationId) return;
    setResolving(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/nutrition/meals/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversationId }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.error ?? `Failed with status ${res.status}`);
        return;
      }
      if (action === "confirm") {
        const data = await res.json();
        setEntries((prev) => [
          ...prev,
          { role: "assistant", text: `Logged ✓ ${data.description} — ${data.calories} kcal` },
        ]);
        onLogged();
      } else {
        setEntries((prev) => [...prev, { role: "assistant", text: "Discarded — nothing saved." }]);
      }
      setPendingMeal(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setResolving(false);
    }
  }

  const busy = sending || recording;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        ref={scrollRef}
        className={`scrollbar-thin flex-1 space-y-3 overflow-y-auto pr-1 ${
          compact ? "max-h-64" : "max-h-[26rem] min-h-[14rem]"
        }`}
      >
        {entries.length === 0 && !sending && (
          <div className="flex h-full flex-col items-start justify-center gap-3 py-4">
            <p className="text-sm text-white/60">
              Say it like you&apos;d text a friend. AI estimates the macros — you confirm.
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => sendText(s)}
                  className="rounded-full border border-fuel/30 bg-fuel/10 px-3 py-1.5 text-xs text-fuel-amber transition hover:border-fuel/60 hover:bg-fuel/20"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {entries.map((entry, i) => (
          <div
            key={i}
            className={`flex animate-fade-in-up ${entry.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed ${
                entry.role === "user"
                  ? "rounded-br-md bg-fuel-gradient font-medium text-black"
                  : "rounded-bl-md border border-line bg-white/[0.05] text-white/90"
              }`}
            >
              {entry.voice && <Mic className="mr-1.5 inline h-3.5 w-3.5 -translate-y-px" />}
              {entry.text}
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex items-center gap-2 text-sm text-white/50">
            <Sparkles className="h-4 w-4 animate-pulse text-fuel" />
            {recording ? "Listening…" : "Crunching the numbers…"}
          </div>
        )}

        {pendingMeal && (
          <div className="animate-fade-in-up rounded-2xl bg-fuel-gradient p-[1.5px] shadow-fuel">
            <div className="rounded-[15px] bg-ink p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="eyebrow text-fuel-amber">AI estimate · confirm to log</p>
                  <p className="mt-1 font-display text-base font-semibold">
                    {pendingMeal.description}
                  </p>
                </div>
                <p className="font-display text-3xl font-bold text-fuel-gradient tabular-nums">
                  {pendingMeal.totalCalories}
                  <span className="ml-1 text-sm text-white/40">kcal</span>
                </p>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                {[
                  ["Protein", pendingMeal.totalProteinG],
                  ["Carbs", pendingMeal.totalCarbsG],
                  ["Fat", pendingMeal.totalFatG],
                ].map(([label, grams]) => (
                  <div key={label} className="rounded-xl bg-white/[0.04] px-3 py-2">
                    <p className="text-[11px] text-white/40">{label}</p>
                    <p className="font-display font-semibold tabular-nums">
                      {Math.round(grams as number)}g
                    </p>
                  </div>
                ))}
              </div>
              <ul className="mt-3 space-y-1 text-sm text-white/60">
                {pendingMeal.items.map((item, i) => (
                  <li key={i} className="flex justify-between gap-3">
                    <span>
                      {item.name} <span className="text-white/35">· {item.quantity}</span>
                    </span>
                    <span className="tabular-nums">{item.calories} kcal</span>
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => resolveMeal("confirm")}
                  disabled={resolving}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-fuel-gradient px-4 py-2.5 text-sm font-semibold text-black transition hover:brightness-110 disabled:opacity-60"
                >
                  {resolving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                  Log it
                </button>
                <button
                  onClick={() => resolveMeal("discard")}
                  disabled={resolving}
                  className="flex items-center gap-1.5 rounded-xl border border-line px-4 py-2.5 text-sm text-white/70 transition hover:bg-white/5 disabled:opacity-60"
                >
                  <X className="h-4 w-4" /> Discard
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {error && (
        <p className="mt-3 rounded-xl border border-recovery-low/30 bg-recovery-low/10 px-3 py-2 text-sm text-recovery-low">
          {error}
        </p>
      )}

      <div className="mt-4 flex items-center gap-2 rounded-2xl border border-line bg-black/30 p-1.5 focus-within:border-fuel/50">
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void sendText();
          }}
          placeholder={recording ? "Listening… tap the mic to finish" : "What did you eat?"}
          disabled={busy}
          maxLength={2000}
          className="flex-1 bg-transparent px-3 py-2 text-sm placeholder:text-white/30 focus:outline-none disabled:opacity-60"
        />
        <button
          onClick={demo ? () => void sendAudio(new Blob([], { type: "audio/webm" })) : recording ? stopRecording : startRecording}
          disabled={sending}
          title={recording ? "Stop recording" : "Speak your meal"}
          className={`flex h-10 w-10 items-center justify-center rounded-xl transition disabled:opacity-50 ${
            recording
              ? "bg-recovery-low shadow-[0_0_24px_rgba(255,59,92,0.6)]"
              : "bg-white/[0.06] text-white/80 hover:bg-white/10"
          }`}
        >
          {recording ? (
            <span className="flex h-4 items-end gap-[3px]">
              {[0, 1, 2, 3].map((i) => (
                <span
                  key={i}
                  className="h-full w-[3px] animate-wave rounded-full bg-white"
                  style={{ animationDelay: `${i * 0.12}s` }}
                />
              ))}
            </span>
          ) : (
            <Mic className="h-[18px] w-[18px]" />
          )}
        </button>
        <button
          onClick={() => void sendText()}
          disabled={busy || !input.trim()}
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-fuel-gradient text-black transition hover:brightness-110 disabled:opacity-40"
          title="Send"
        >
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}
