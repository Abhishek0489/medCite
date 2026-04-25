"use client";

import { Button } from "@/components/ui/button";
import SourceCard from "@/components/SourceCard";
import { Sparkles, BookOpen, Pencil, AlertTriangle, ShieldCheck } from "lucide-react";

// Two distinct screens for "no answer":
//
// 1. NotFoundScreen — local search returned status="not_found"
//    (no chunk above SIMILARITY_THRESHOLD). Spec §5 Flow B requires
//    three buttons: Search live · Show related · Rephrase.
//
// 2. AbstainScreen — verifier confidence < CONFIDENCE_THRESHOLD or
//    synth said INSUFFICIENT_EVIDENCE. Spec §3 rule 4 + §5 Flow C:
//    explicitly say "no reliable answer" and explain why.

export default function NotFoundScreen({
  query,
  result,
  onSearchLive,
  onRephrase,
  liveLoading,
}) {
  const { reasoning = {}, sources = [] } = result || {};
  const topSim = reasoning.top_similarity ?? 0;

  return (
    <section className="space-y-6">
      <div className="rounded-2xl border border-amber-200 bg-amber-50/40 p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700">
            <AlertTriangle className="h-5 w-5" aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold text-slate-900">
              No verified answer in the local knowledge base
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              The closest match scored{" "}
              <span className="tabular-nums font-medium text-slate-700">
                {topSim.toFixed(2)}
              </span>
              , below the safety threshold. We won&apos;t guess.
            </p>
            {query ? (
              <p className="mt-3 text-xs uppercase tracking-wide text-slate-400 font-medium">
                Your question
              </p>
            ) : null}
            {query ? (
              <p className="mt-1 text-sm italic text-slate-700">&ldquo;{query}&rdquo;</p>
            ) : null}
          </div>
        </div>

        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <Button
            type="button"
            size="lg"
            onClick={onSearchLive}
            disabled={liveLoading}
            className="gap-2 bg-sky-600 text-white hover:bg-sky-700"
          >
            <Sparkles className="h-4 w-4" aria-hidden />
            {liveLoading ? "Searching live…" : "Search live with Multi-AI"}
          </Button>
          <Button
            type="button"
            size="lg"
            variant="outline"
            onClick={() => {
              const el = document.getElementById("related-articles");
              el?.scrollIntoView({ behavior: "smooth", block: "start" });
            }}
            disabled={sources.length === 0}
            className="gap-2"
          >
            <BookOpen className="h-4 w-4" aria-hidden />
            Show related articles ({sources.length})
          </Button>
          <Button
            type="button"
            size="lg"
            variant="ghost"
            onClick={onRephrase}
            className="gap-2"
          >
            <Pencil className="h-4 w-4" aria-hidden />
            Rephrase my question
          </Button>
        </div>
      </div>

      {sources.length > 0 ? (
        <div id="related-articles" className="space-y-3 scroll-mt-6">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Closest related articles (below confidence threshold)
          </h3>
          <ul className="space-y-3">
            {sources.map((s) => (
              <li key={s.citation_number}>
                <SourceCard source={s} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

export function AbstainScreen({ query, result, onRephrase }) {
  const { tier, reasoning = {}, sources = [] } = result || {};
  const unsupported = reasoning.verifier_unsupported_claims || [];

  return (
    <section className="space-y-6">
      <div className="rounded-2xl border border-slate-300 bg-white p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-700">
            <ShieldCheck className="h-5 w-5" aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold text-slate-900">
              No reliable answer found
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              We searched the {tier === "live" ? "live PubMed index" : "verified knowledge base"} and
              found candidate passages, but our cross-vendor verifier could not confirm every
              claim. Per safety policy, we will not present an unverified answer.
            </p>
            {query ? (
              <p className="mt-3 text-xs uppercase tracking-wide text-slate-400 font-medium">
                Your question
              </p>
            ) : null}
            {query ? (
              <p className="mt-1 text-sm italic text-slate-700">&ldquo;{query}&rdquo;</p>
            ) : null}

            {unsupported.length > 0 ? (
              <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Verifier flagged unsupported claims
                </p>
                <ul className="mt-1 list-disc list-inside text-sm text-slate-700 space-y-1">
                  {unsupported.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <Button type="button" size="lg" onClick={onRephrase} className="gap-2 bg-sky-600 text-white hover:bg-sky-700">
            <Pencil className="h-4 w-4" aria-hidden />
            Rephrase my question
          </Button>
        </div>
      </div>

      {sources.length > 0 ? (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Articles considered
          </h3>
          <ul className="space-y-3">
            {sources.map((s) => (
              <li key={s.citation_number}>
                <SourceCard source={s} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
