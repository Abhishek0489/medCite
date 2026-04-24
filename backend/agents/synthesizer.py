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


# Use verbatim from PROJECT_SPEC.md section 10.
SYNTHESIZER_PROMPT_TEMPLATE = """You are a medical evidence assistant. Answer the doctor's question using ONLY the numbered sources below.

RULES:
- Cite every factual claim inline using [1], [2], etc.
- Do NOT write URLs or links — only citation numbers.
- Do NOT use your own medical knowledge. Use only what is in the sources.
- Keep the answer to 2-4 sentences.
- If the sources do not contain a clear answer, respond with exactly: INSUFFICIENT_EVIDENCE

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
            max_output_tokens=512,
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
