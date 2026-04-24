"""
Synthesizer agent — Google Gemini 2.5 Flash.

Given a doctor's query and a list of retrieved chunks, produce a short,
cited answer. NEVER writes URLs. NEVER uses its own medical knowledge.
If the sources don't contain a clear answer, returns the literal string
"INSUFFICIENT_EVIDENCE".
"""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402


def _is_transient(exc: BaseException) -> bool:
    """Retry only on transient server-side errors (overload, 5xx, rate-limit).
    Never retry on auth / invalid-argument / safety-block."""
    if isinstance(exc, (genai_errors.ServerError, genai_errors.APIError)):
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        try:
            code = int(code) if code is not None else None
        except (TypeError, ValueError):
            code = None
        if code is None:
            return True
        return code in (429, 500, 502, 503, 504)
    return False


# Based on PROJECT_SPEC.md section 10. Softened on 2026-04-24 after Gemini 2.5
# Flash was observed literally returning "INSUFFICIENT_EVIDENCE" on in-scope
# queries (top_sim 0.82 on empagliflozin/HFpEF) because the original phrasing
# "clear answer" made the model over-cautious. Non-negotiables preserved:
# no URLs (§3 rule 1), no prior knowledge (§3 rule 2), citation numbers only,
# 2-4 sentences, literal INSUFFICIENT_EVIDENCE abstention token.
SYNTHESIZER_PROMPT_TEMPLATE = """You are a medical evidence assistant helping a physician. Answer the doctor's question using ONLY the numbered sources below.

RULES:
- Cite every factual claim inline using [1], [2], etc.
- Do NOT write URLs or links — only citation numbers.
- Do NOT use your own medical knowledge or information from outside the sources.
- You MAY synthesize across sources and state conclusions that are directly supported by the source text, even if no single source states the exact conclusion verbatim. Prefer answering when the sources provide relevant evidence.
- Keep the answer to 2-4 sentences, clinical tone.
- Only if NONE of the sources are relevant to the question, respond with exactly: INSUFFICIENT_EVIDENCE
  (Do not abstain merely because the wording differs from the question or because a source discusses a related-but-broader population — if the evidence applies, answer and cite it.)

QUESTION: {query}

SOURCES:
{sources_block}

ANSWER:"""


INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

_log = logging.getLogger("medcite.synthesizer")
if not _log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

_client: genai.Client | None = None
_lock = threading.Lock()


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                if not settings.GOOGLE_API_KEY:
                    raise RuntimeError("GOOGLE_API_KEY is not set in .env")
                _client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    return _client


def _format_sources(chunks: list[dict]) -> str:
    lines = []
    for i, c in enumerate(chunks, start=1):
        lines.append(f"[{i}] {c['chunk_text']}")
    return "\n\n".join(lines)


# Safety filters disabled for this service. Context: curated PubMed abstracts
# passed to a medical-evidence synthesizer that only cites those sources.
# No user-generated content is forwarded to the model, so the safety filter
# adds no protection but does occasionally block or empty-out legitimate
# clinical responses. See google.genai docs on SafetySetting.
# google-genai accepts string values for HarmCategory / HarmBlockThreshold;
# the typed aliases exposed on `types` are Literal unions, not Enums, so we
# use the canonical string constants directly.
_SAFETY_SETTINGS = [
    genai_types.SafetySetting(category=cat, threshold="BLOCK_NONE")
    for cat in (
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    )
]


@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    reraise=True,
)
def _generate_one(client: "genai.Client", model: str, prompt: str):
    return client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            temperature=0.0,
            # Gemini 2.5 Flash is a "thinking" model: internal reasoning tokens
            # are counted against this budget before any visible text is
            # emitted. 1024 was enough for thinking but left only ~200 chars
            # of answer (truncated mid-sentence with finish_reason=MAX_TOKENS).
            # Answer itself is 2-4 sentences (~400 chars); 4096 gives ample
            # headroom for thinking + answer. google-genai 0.3.0 doesn't
            # expose ThinkingConfig yet; when upgraded, switch to
            # thinking_config=ThinkingConfig(thinking_budget=0).
            max_output_tokens=4096,
            safety_settings=_SAFETY_SETTINGS,
        ),
    )


def _generate_with_retry(client: "genai.Client", prompt: str):
    """Try the primary synthesizer model with retries. On persistent transient
    failure, fall back to SYNTHESIZER_FALLBACK_MODEL (e.g. gemini-2.5-flash-lite)
    if configured. Any non-transient error propagates immediately."""
    try:
        return _generate_one(client, settings.SYNTHESIZER_MODEL, prompt)
    except Exception as exc:
        if not _is_transient(exc):
            raise
        fallback = settings.SYNTHESIZER_FALLBACK_MODEL
        if not fallback or fallback == settings.SYNTHESIZER_MODEL:
            raise
        # Fall back to the secondary model (separate quota/capacity pool).
        return _generate_one(client, fallback, prompt)


def synthesize(query: str, chunks: list[dict]) -> str:
    """
    Run the synthesizer on query + retrieved chunks.
    Returns either a 2-4 sentence cited answer or "INSUFFICIENT_EVIDENCE".
    """
    if not chunks:
        return INSUFFICIENT

    prompt = SYNTHESIZER_PROMPT_TEMPLATE.format(
        query=query.strip(),
        sources_block=_format_sources(chunks),
    )

    client = _get_client()
    response = _generate_with_retry(client, prompt)

    text = (response.text or "").strip()

    # Diagnostic logging — essential for debugging why the synthesizer
    # refuses to answer despite strong retrieval matches.
    finish_reason = None
    safety = None
    try:
        if response.candidates:
            finish_reason = getattr(response.candidates[0], "finish_reason", None)
            safety = getattr(response.candidates[0], "safety_ratings", None)
    except Exception:
        pass
    _log.info(
        "synth: query=%r chunks=%d text_len=%d finish=%s safety=%s text_preview=%r",
        query[:80],
        len(chunks),
        len(text),
        finish_reason,
        safety,
        text[:200],
    )

    if not text:
        return INSUFFICIENT

    # Only treat EXACT "INSUFFICIENT_EVIDENCE" as abstention (previous
    # .startswith() check mis-classified answers that merely mentioned the
    # token in a hedged preamble).
    stripped_upper = text.upper().strip(" .\"'`")
    if stripped_upper == INSUFFICIENT:
        return INSUFFICIENT

    return text
