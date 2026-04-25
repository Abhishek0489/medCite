"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Search, Loader2 } from "lucide-react";

// Spec §3 rule 7: clinical tool, not a chatbot. One question, one answer.
// Submitting REPLACES the current answer rather than appending to a thread.
export default function QueryCard({ onSubmit, loading, defaultValue = "" }) {
  const [value, setValue] = useState(defaultValue);

  function handleSubmit(e) {
    e?.preventDefault?.();
    const q = value.trim();
    if (!q || loading) return;
    onSubmit?.(q);
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      handleSubmit(e);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm focus-within:ring-2 focus-within:ring-sky-200"
    >
      <label
        htmlFor="medcite-query"
        className="block text-xs font-medium uppercase tracking-wide text-slate-500 mb-2"
      >
        Clinical question
      </label>
      <Textarea
        id="medcite-query"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={3}
        placeholder="e.g. Does empagliflozin reduce cardiovascular mortality in HFpEF?"
        className="resize-none border-0 px-0 shadow-none focus-visible:ring-0 text-base text-slate-900 placeholder:text-slate-400"
        disabled={loading}
        autoFocus
      />
      <div className="mt-3 flex items-center justify-between">
        <p className="text-xs text-slate-400">
          ⌘/Ctrl + Enter to ask · answers are cited from PubMed
        </p>
        <Button
          type="submit"
          size="lg"
          disabled={loading || !value.trim()}
          className="gap-2 bg-sky-600 text-white hover:bg-sky-700"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Search className="h-4 w-4" aria-hidden />
          )}
          {loading ? "Searching…" : "Ask"}
        </Button>
      </div>
    </form>
  );
}
