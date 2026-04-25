import { cn } from "@/lib/utils";

// Maps a 0–1 verifier confidence to a color band + label.
// Spec §3 rule 4: < 0.75 means abstain, so any meter we ever render
// for an actual answer will be in the green band. Amber/red bands are
// kept here for completeness in case we ever surface borderline scores
// in a debug/reasoning panel.
function band(confidence) {
  if (confidence >= 0.85) {
    return {
      label: "High confidence",
      bar: "bg-emerald-500",
      track: "bg-emerald-100",
      text: "text-emerald-700",
    };
  }
  if (confidence >= 0.75) {
    return {
      label: "Verified",
      bar: "bg-emerald-500",
      track: "bg-emerald-100",
      text: "text-emerald-700",
    };
  }
  if (confidence >= 0.5) {
    return {
      label: "Borderline",
      bar: "bg-amber-500",
      track: "bg-amber-100",
      text: "text-amber-700",
    };
  }
  return {
    label: "Low confidence",
    bar: "bg-red-500",
    track: "bg-red-100",
    text: "text-red-700",
  };
}

export default function ConfidenceMeter({ confidence, className }) {
  const c = typeof confidence === "number" ? Math.max(0, Math.min(1, confidence)) : 0;
  const pct = Math.round(c * 100);
  const { label, bar, track, text } = band(c);

  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-baseline justify-between mb-1.5">
        <span className={cn("text-xs font-medium tracking-wide uppercase", text)}>
          {label}
        </span>
        <span className="text-xs tabular-nums text-slate-500">
          {pct}% verifier confidence
        </span>
      </div>
      <div className={cn("h-1.5 w-full rounded-full overflow-hidden", track)}>
        <div
          className={cn("h-full rounded-full transition-all duration-500", bar)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
