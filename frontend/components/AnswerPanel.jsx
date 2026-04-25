import { CheckCircle2, Sparkles, Database } from "lucide-react";
import ConfidenceMeter from "@/components/ConfidenceMeter";
import SourceCard from "@/components/SourceCard";
import { cn } from "@/lib/utils";

// Renders an inline answer with [1][2] citation markers as small chips
// linked to the corresponding source card via id="source-N".
function renderAnswerWithChips(answer) {
  if (!answer) return null;
  const parts = answer.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (m) {
      const n = m[1];
      return (
        <a
          key={i}
          href={`#source-${n}`}
          className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-100 px-1 text-[10px] font-semibold tabular-nums text-sky-700 align-text-top no-underline ring-1 ring-sky-200 hover:bg-sky-200"
        >
          {n}
        </a>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function TierBadge({ tier, articlesAdded }) {
  const isLive = tier === "live";
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1",
          isLive
            ? "bg-amber-50 text-amber-800 ring-amber-200"
            : "bg-emerald-50 text-emerald-800 ring-emerald-200"
        )}
      >
        {isLive ? (
          <Sparkles className="h-3 w-3" aria-hidden />
        ) : (
          <CheckCircle2 className="h-3 w-3" aria-hidden />
        )}
        {isLive ? "Answered by live multi-AI search" : "Answered from verified knowledge base"}
      </span>
      {isLive && articlesAdded ? (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 ring-1 ring-slate-200">
          <Database className="h-3 w-3" aria-hidden />
          Added {articlesAdded} article{articlesAdded === 1 ? "" : "s"} to knowledge base
        </span>
      ) : null}
    </div>
  );
}

export default function AnswerPanel({ result, query }) {
  if (!result) return null;
  const { tier, answer, confidence, sources = [], reasoning = {} } = result;

  return (
    <section className="space-y-6" aria-label="Answer">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <TierBadge tier={tier} articlesAdded={reasoning?.articles_added_to_kb} />

        {query ? (
          <p className="mt-4 text-xs uppercase tracking-wide text-slate-400 font-medium">
            Question
          </p>
        ) : null}
        {query ? (
          <p className="mt-1 text-sm text-slate-700">{query}</p>
        ) : null}

        <p className="mt-4 text-xs uppercase tracking-wide text-slate-400 font-medium">
          Answer
        </p>
        <p className="mt-2 text-base leading-relaxed text-slate-900">
          {renderAnswerWithChips(answer)}
        </p>

        <div className="mt-5 max-w-sm">
          <ConfidenceMeter confidence={confidence} />
        </div>
      </div>

      {sources.length > 0 ? (
        <div className="space-y-3">
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
              Sources ({sources.length})
            </h2>
            {reasoning?.top_similarity ? (
              <span className="text-xs text-slate-400 tabular-nums">
                top similarity {reasoning.top_similarity.toFixed(2)}
              </span>
            ) : null}
          </div>
          <ul className="space-y-3">
            {sources.map((s) => (
              <li key={s.citation_number} id={`source-${s.citation_number}`}>
                <SourceCard source={s} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
