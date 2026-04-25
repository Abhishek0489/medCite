"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Stethoscope, AlertCircle, RotateCw } from "lucide-react";
import QueryCard from "@/components/QueryCard";
import AnswerPanel from "@/components/AnswerPanel";
import NotFoundScreen, { AbstainScreen } from "@/components/NotFoundScreen";
import LiveSearchProgress from "@/components/LiveSearchProgress";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { queryLocal, queryLive, checkHealth } from "@/lib/api";

// Spec §3 rule 7: clinical tool, NOT a chatbot. The page is a single-screen
// state machine, not a thread. Submitting a new query wipes prior result.
//
// Phases:
//   idle      — empty input, hero copy below
//   loading   — local search in flight
//   live      — live multi-AI in flight (after user clicks "Search live")
//   answered  — found result with confidence ≥ threshold
//   notfound  — local status="not_found" (allow live escalation)
//   abstain   — status="insufficient_evidence" from either tier
//   error     — network / 5xx
// Refreshed 2026-04-25 (Day-3 PM, post-recording):
//  - Dropped "metformin in CKD" — now Tier-1 hits via Day-2 write-back, no longer
//    a clean abstention example.
//  - Dropped the long-form CAP-antibiotics phrasing — PubMed E-utilities ESearch
//    returns 0 PMIDs for natural-language sentences with grammatical filler.
//  - "H. pylori first-line eradication 2024" was used during the backup-demo
//    recording, so its write-back contaminated the live container. Swapped to
//    "Levetiracetam status epilepticus dose" — out of corpus (no neurology
//    specialty), 169 PMIDs in PubMed, full live pipeline verified end-to-end
//    (status=found, conf=0.80, top_sim=0.8054, 5 cited sources). DO NOT click
//    before stage time — first click writes the articles back into the cache
//    and ruins the live-multi-AI showstopper animation.
const HERO_QUERIES = [
  "Does empagliflozin reduce cardiovascular mortality in HFpEF?",
  "First-line treatment for drug-resistant tuberculosis 2024",
  "Levetiracetam status epilepticus dose",
  "Is acetaminophen safe in third trimester pregnancy?",
  "Side effects of SGLT2 inhibitors in elderly patients",
];

const HEALTH_RETRY_DELAYS_MS = [5000, 10000, 20000];

export default function HomePage() {
  const [phase, setPhase] = useState("idle");
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [health, setHealth] = useState(null);

  const abortRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    const runHealthCheck = async () => {
      // While HF wakes from sleep, expose an explicit warming state.
      setHealth({ status: "warming" });
      for (let attempt = 0; attempt <= HEALTH_RETRY_DELAYS_MS.length; attempt += 1) {
        try {
          const h = await checkHealth();
          if (!cancelled) setHealth(h);
          return;
        } catch {
          if (attempt === HEALTH_RETRY_DELAYS_MS.length) break;
          if (!cancelled) setHealth({ status: "warming" });
          await sleep(HEALTH_RETRY_DELAYS_MS[attempt]);
          if (cancelled) return;
        }
      }
      if (!cancelled) setHealth({ status: "error" });
    };

    runHealthCheck();
    return () => {
      cancelled = true;
    };
  }, []);

  const cancelInFlight = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const runLocal = useCallback(async (q) => {
    cancelInFlight();
    const controller = new AbortController();
    abortRef.current = controller;

    setSubmittedQuery(q);
    setResult(null);
    setError(null);
    setPhase("loading");

    try {
      const data = await queryLocal(q, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setResult(data);
      if (data.status === "found") setPhase("answered");
      else if (data.status === "insufficient_evidence") setPhase("abstain");
      else setPhase("notfound");
    } catch (e) {
      if (controller.signal.aborted) return;
      setError(e.message || String(e));
      setPhase("error");
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [cancelInFlight]);

  const runLive = useCallback(async () => {
    if (!submittedQuery) return;
    cancelInFlight();
    const controller = new AbortController();
    abortRef.current = controller;

    setError(null);
    setResult(null);
    setPhase("live");

    try {
      const data = await queryLive(submittedQuery, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setResult(data);
      if (data.status === "found") setPhase("answered");
      else if (data.status === "insufficient_evidence") setPhase("abstain");
      else setPhase("notfound");
    } catch (e) {
      if (controller.signal.aborted) return;
      setError(e.message || String(e));
      setPhase("error");
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [submittedQuery, cancelInFlight]);

  const handleSubmit = useCallback(
    (q) => {
      setQuery(q);
      runLocal(q);
    },
    [runLocal]
  );

  const handleRephrase = useCallback(() => {
    cancelInFlight();
    setResult(null);
    setError(null);
    setPhase("idle");
    requestAnimationFrame(() => {
      const el = document.getElementById("medcite-query");
      el?.focus?.();
    });
  }, [cancelInFlight]);

  const onPickSample = useCallback(
    (q) => {
      setQuery(q);
      handleSubmit(q);
    },
    [handleSubmit]
  );

  const handleRefresh = useCallback(() => {
    window.location.reload();
  }, []);

  const synthLabel = useMemo(() => {
    if (!health || health.status !== "ok") return null;
    return `${health.synthesizer_model} · ${health.verifier_model}`;
  }, [health]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:py-14">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-sky-600 text-white shadow-sm">
              <Stethoscope className="h-5 w-5" aria-hidden />
            </span>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
              MedCite
            </h1>
          </div>
          <p className="mt-2 text-sm text-slate-600 max-w-xl">
            Cited medical answers from PubMed. One question, one verified answer —
            never a guess.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 text-right">
          <button
            type="button"
            onClick={handleRefresh}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 shadow-sm transition-colors hover:border-sky-300 hover:text-sky-700"
            aria-label="Refresh app"
            title="Refresh app"
          >
            <RotateCw className="h-3.5 w-3.5" aria-hidden />
            Refresh
          </button>
          <div className="hidden sm:flex flex-col items-end text-right">
            <span
              className={
                "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs ring-1 " +
                (health?.status === "ok"
                  ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                  : health?.status === "warming"
                    ? "bg-slate-100 text-slate-600 ring-slate-200"
                    : "bg-rose-50 text-rose-700 ring-rose-200")
              }
            >
              <span
                className={
                  "h-1.5 w-1.5 rounded-full " +
                  (health?.status === "ok"
                    ? "bg-emerald-500"
                    : health?.status === "warming"
                      ? "bg-slate-400"
                      : "bg-rose-500")
                }
              />
              {health?.status === "ok"
                ? "Backend online"
                : health?.status === "warming"
                  ? "Backend warming..."
                  : "Backend offline"}
            </span>
            {synthLabel ? (
              <span className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">
                {synthLabel}
              </span>
            ) : null}
          </div>
        </div>
      </header>

      <div className="space-y-6">
        <QueryCard
          onSubmit={handleSubmit}
          loading={phase === "loading" || phase === "live"}
          defaultValue={query}
        />

        {phase === "idle" ? (
          <section className="rounded-2xl border border-dashed border-slate-200 bg-white/60 p-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">
              Try a hero question
            </p>
            <ul className="grid gap-2 sm:grid-cols-2">
              {HERO_QUERIES.map((q) => (
                <li key={q}>
                  <button
                    type="button"
                    onClick={() => onPickSample(q)}
                    className="w-full text-left rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm hover:border-sky-300 hover:bg-sky-50/50 hover:text-slate-900 transition-colors"
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {phase === "loading" ? (
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-3">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-11/12" />
            <Skeleton className="h-3 w-9/12" />
            <div className="pt-2">
              <Skeleton className="h-2 w-1/2" />
            </div>
          </section>
        ) : null}

        {phase === "live" ? <LiveSearchProgress /> : null}

        {phase === "error" ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Request failed</AlertTitle>
            <AlertDescription>
              {error || "Unknown error contacting the backend."}
              <div className="mt-2 text-xs">
                Make sure FastAPI is running at the URL configured by{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5">
                  NEXT_PUBLIC_API_URL
                </code>
                .
              </div>
            </AlertDescription>
          </Alert>
        ) : null}

        {phase === "answered" && result ? (
          <AnswerPanel result={result} query={submittedQuery} />
        ) : null}

        {phase === "notfound" && result ? (
          <NotFoundScreen
            query={submittedQuery}
            result={result}
            onSearchLive={runLive}
            onRephrase={handleRephrase}
            liveLoading={false}
          />
        ) : null}

        {phase === "abstain" && result ? (
          <AbstainScreen
            query={submittedQuery}
            result={result}
            onRephrase={handleRephrase}
          />
        ) : null}
      </div>

      <footer className="mt-12 border-t border-slate-200 pt-6 text-xs text-slate-400">
        <p>
          MedCite is a research prototype. Every answer is grounded in cited PubMed
          sources or returns an explicit abstention — never a hallucinated fact.
        </p>
      </footer>
    </main>
  );
}
