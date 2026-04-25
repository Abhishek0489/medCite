import { Badge } from "@/components/ui/badge";
import { ExternalLink, FileText, Quote } from "lucide-react";
import { cn } from "@/lib/utils";

// Spec §3 rule 1+6: URLs come from backend metadata (built from PMID),
// never from the LLM. Each card MUST show the quoted_passage so doctors
// can verify the citation at a glance.

function evidenceLevel(publicationType = "") {
  const t = publicationType.toLowerCase();
  if (t.includes("meta-analysis") || t.includes("systematic review")) {
    return { label: "Meta-analysis", color: "bg-violet-50 text-violet-700 border-violet-200" };
  }
  if (t.includes("randomized") || t.includes("rct") || t.includes("clinical trial, phase")) {
    return { label: "RCT", color: "bg-emerald-50 text-emerald-700 border-emerald-200" };
  }
  if (t.includes("review")) {
    return { label: "Review", color: "bg-sky-50 text-sky-700 border-sky-200" };
  }
  if (t.includes("guideline") || t.includes("practice guideline")) {
    return { label: "Guideline", color: "bg-amber-50 text-amber-700 border-amber-200" };
  }
  if (t.includes("case report")) {
    return { label: "Case report", color: "bg-slate-50 text-slate-600 border-slate-200" };
  }
  return { label: publicationType || "Journal article", color: "bg-slate-50 text-slate-600 border-slate-200" };
}

export default function SourceCard({ source }) {
  if (!source) return null;
  const {
    citation_number,
    title,
    journal,
    year,
    authors,
    publication_type,
    url,
    doi_url,
    quoted_passage,
  } = source;

  const ev = evidenceLevel(publication_type);

  return (
    <article className="group relative rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-start gap-4">
        <div className="shrink-0">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-sky-50 text-sky-700 text-sm font-semibold tabular-nums ring-1 ring-sky-200">
            {citation_number}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                ev.color
              )}
            >
              {ev.label}
            </span>
            {journal ? (
              <span className="text-xs text-slate-500 truncate">
                {journal}
                {year ? <span className="text-slate-400"> · {year}</span> : null}
              </span>
            ) : year ? (
              <span className="text-xs text-slate-500">{year}</span>
            ) : null}
          </div>

          <h3 className="text-sm font-semibold leading-snug text-slate-900">
            {title || "Untitled article"}
          </h3>

          {authors ? (
            <p className="mt-1 text-xs text-slate-500 line-clamp-2">{authors}</p>
          ) : null}

          {quoted_passage ? (
            <blockquote className="mt-3 rounded-md border-l-2 border-sky-300 bg-slate-50/70 px-3 py-2">
              <div className="flex items-start gap-2">
                <Quote className="mt-0.5 h-3 w-3 shrink-0 text-sky-500" aria-hidden />
                <p className="text-xs leading-relaxed text-slate-700 italic">
                  {quoted_passage}
                </p>
              </div>
            </blockquote>
          ) : null}

          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs">
            {url ? (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-medium text-sky-700 hover:text-sky-900 hover:underline"
              >
                <ExternalLink className="h-3 w-3" aria-hidden />
                PubMed
              </a>
            ) : null}
            {doi_url ? (
              <a
                href={doi_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-medium text-slate-600 hover:text-slate-900 hover:underline"
              >
                <FileText className="h-3 w-3" aria-hidden />
                DOI
              </a>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}
