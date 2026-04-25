"use client";

import { useEffect, useState } from "react";
import { Loader2, Check, Search, Brain, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

// Live search runs server-side as one request (no SSE), so we can't tail
// real progress. We fake-stage timed transitions purely as a UX cue —
// PubMed → Synthesizing → Verifying. Real backend latency is ~15-30s
// per spec §5 Flow B; the timings below are tuned around that.
const STAGES = [
  {
    id: "pubmed",
    label: "Searching PubMed",
    detail: "Fetching candidate abstracts via E-utilities…",
    Icon: Search,
    durationMs: 6000,
  },
  {
    id: "synth",
    label: "Synthesizing with Gemini",
    detail: "Composing a cited answer from retrieved passages…",
    Icon: Brain,
    durationMs: 6000,
  },
  {
    id: "verify",
    label: "Verifying with Llama 3.3 (Groq)",
    detail: "Cross-vendor fact-check against the same sources…",
    Icon: ShieldCheck,
    durationMs: 1000_000, // remain on this stage until response arrives
  },
];

export default function LiveSearchProgress() {
  const [stageIdx, setStageIdx] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timeout;

    function advance(i) {
      if (cancelled) return;
      if (i >= STAGES.length - 1) return;
      timeout = setTimeout(() => {
        if (cancelled) return;
        setStageIdx(i + 1);
        advance(i + 1);
      }, STAGES[i].durationMs);
    }

    advance(0);
    return () => {
      cancelled = true;
      if (timeout) clearTimeout(timeout);
    };
  }, []);

  return (
    <section
      role="status"
      aria-live="polite"
      className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div className="flex items-center gap-2 mb-4">
        <Loader2 className="h-4 w-4 animate-spin text-sky-600" aria-hidden />
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
          Live multi-AI search in progress
        </h2>
      </div>

      <ol className="space-y-3">
        {STAGES.map((s, i) => {
          const done = i < stageIdx;
          const active = i === stageIdx;
          const Icon = s.Icon;
          return (
            <li key={s.id} className="flex items-start gap-3">
              <div
                className={cn(
                  "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-1 transition-colors",
                  done && "bg-emerald-50 text-emerald-600 ring-emerald-200",
                  active && "bg-sky-50 text-sky-600 ring-sky-200",
                  !done && !active && "bg-slate-50 text-slate-400 ring-slate-200"
                )}
              >
                {done ? (
                  <Check className="h-4 w-4" aria-hidden />
                ) : active ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                ) : (
                  <Icon className="h-4 w-4" aria-hidden />
                )}
              </div>
              <div className="min-w-0">
                <p
                  className={cn(
                    "text-sm font-medium",
                    done && "text-slate-500 line-through decoration-slate-300",
                    active && "text-slate-900",
                    !done && !active && "text-slate-400"
                  )}
                >
                  {s.label}
                </p>
                {active ? (
                  <p className="mt-0.5 text-xs text-slate-500">{s.detail}</p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>

      <p className="mt-5 text-xs text-slate-400">
        Verified results are also written back to the local knowledge base, so the same
        question is instant next time.
      </p>
    </section>
  );
}
