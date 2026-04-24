"""
Verifier agent — Groq's Llama 3.3 70B Versatile.

DIFFERENT VENDOR than the synthesizer (spec §3 rule 3). Receives the
synthesizer's answer plus the source chunks and returns strict JSON:

    {
      "confidence": 0.0 - 1.0,
      "unsupported_claims": ["...", "..."]
    }

If the confidence is below settings.CONFIDENCE_THRESHOLD, the pipeline
abstains.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import threading
from pathlib import Path

from groq import APIError as GroqAPIError
from groq import Groq
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402


_log = logging.getLogger("medcite.verifier")


def _is_transient(exc: BaseException) -> bool:
    """Retry only on transient Groq errors (5xx, 429). Never on auth/invalid."""
    if isinstance(exc, GroqAPIError):
        code = getattr(exc, "status_code", None)
        try:
            code = int(code) if code is not None else None
        except (TypeError, ValueError):
            code = None
        if code is None:
            return True
        return code in (429, 500, 502, 503, 504)
    return False


# Verbatim from PROJECT_SPEC.md section 10.
VERIFIER_PROMPT_TEMPLATE = """You are a fact-checker. A medical answer has been written based on the sources below. Determine whether every claim in the answer is directly supported by the sources.

OUTPUT JSON ONLY:
{{
  "confidence": <float 0-1>,
  "unsupported_claims": [<list of sentences from the answer that are not supported by sources>]
}}

ANSWER:
{synthesizer_output}

SOURCES:
{sources_block}"""


_client: Groq | None = None
_lock = threading.Lock()


def _get_client() -> Groq:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                if not settings.GROQ_API_KEY:
                    raise RuntimeError("GROQ_API_KEY is not set in .env")
                _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def _format_sources(chunks: list[dict]) -> str:
    lines = []
    for i, c in enumerate(chunks, start=1):
        lines.append(f"[{i}] {c['chunk_text']}")
    return "\n\n".join(lines)


@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)
def _chat_with_retry(client: "Groq", prompt: str):
    return client.chat.completions.create(
        model=settings.VERIFIER_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strict medical fact-checker. "
                    "Reply ONLY with a single JSON object. No prose, no markdown."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=512,
        response_format={"type": "json_object"},
    )


def _parse_json(raw: str) -> dict:
    """
    Try hard to extract the JSON object from the model's reply.
    Groq's Llama obeys response_format=json_object well, but guard anyway.
    """
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def verify(synthesizer_output: str, chunks: list[dict]) -> dict:
    """
    Returns {"confidence": float, "unsupported_claims": list[str]}.

    Defensive: if the LLM returns garbage, we conservatively report
    confidence=0.0 so the pipeline abstains.
    """
    prompt = VERIFIER_PROMPT_TEMPLATE.format(
        synthesizer_output=synthesizer_output.strip(),
        sources_block=_format_sources(chunks),
    )

    client = _get_client()
    completion = _chat_with_retry(client, prompt)

    raw = completion.choices[0].message.content or ""
    parsed = _parse_json(raw)

    confidence_raw = parsed.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    unsupported = parsed.get("unsupported_claims", []) or []
    if not isinstance(unsupported, list):
        unsupported = [str(unsupported)]
    unsupported = [str(x) for x in unsupported]

    _log.info(
        "verify: confidence=%.3f unsupported=%d answer_preview=%r raw_preview=%r",
        confidence,
        len(unsupported),
        synthesizer_output[:120],
        raw[:200],
    )

    return {
        "confidence": confidence,
        "unsupported_claims": unsupported,
    }
