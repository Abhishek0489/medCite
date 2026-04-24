"""
Pipeline orchestrator: retrieve -> synthesize -> verify -> abstain-or-return.

Shared by both /query/local and /query/live.

Hard rules enforced here (spec §3):
  - Only the retrieved chunks feed the synthesizer (LLM never invents URLs).
  - If chunk top-similarity < SIMILARITY_THRESHOLD on local path, return
    status="not_found" without calling any LLM.
  - If synthesizer returns INSUFFICIENT_EVIDENCE, return status accordingly.
  - If verifier confidence < CONFIDENCE_THRESHOLD, abstain.
  - On /query/live success, new articles are written back to LanceDB.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents.synthesizer import INSUFFICIENT, synthesize  # noqa: E402
from agents.verifier import verify  # noqa: E402
from config import settings  # noqa: E402
from retrieval.live_search import live_search, write_articles_to_lancedb  # noqa: E402
from retrieval.local_search import search_local, top_similarity  # noqa: E402


def _build_source(citation_number: int, chunk: dict) -> dict:
    md = chunk["metadata"]
    return {
        "citation_number": citation_number,
        "title": md.get("title", ""),
        "journal": md.get("journal", ""),
        "year": md.get("year", ""),
        "authors": md.get("authors", ""),
        "publication_type": md.get("publication_type", "Journal Article"),
        "url": md.get("url", ""),
        "doi_url": md.get("doi_url", ""),
        "quoted_passage": chunk.get("chunk_text", ""),
    }


def _empty_response(
    status: str,
    tier: str,
    queries_searched: list[str],
    top_sim: float,
    unsupported: list[str] | None = None,
) -> dict:
    return {
        "status": status,
        "tier": tier,
        "answer": "",
        "confidence": 0.0,
        "sources": [],
        "reasoning": {
            "queries_searched": queries_searched,
            "top_similarity": round(top_sim, 4),
            "verifier_unsupported_claims": unsupported or [],
        },
    }


def run_local_query(query: str) -> dict:
    """Tier 1: LanceDB retrieval -> synth -> verify. No external API calls
    for retrieval. Abstains instead of calling the live fallback."""
    chunks = search_local(query, top_k=5)
    top_sim = top_similarity(chunks)

    if not chunks or top_sim < settings.SIMILARITY_THRESHOLD:
        return _empty_response("not_found", "local", [query], top_sim)

    return _synthesize_and_verify(
        query=query,
        chunks=chunks,
        tier="local",
        top_sim=top_sim,
    )


def run_live_query(query: str) -> dict:
    """Tier 2: PubMed live fetch -> synth -> verify. On success, writes
    fetched articles back into LanceDB so Tier 1 catches the same query
    next time (self-improvement loop, spec §4 Component 3)."""
    chunks, articles = live_search(query)
    top_sim = top_similarity(chunks)

    if not chunks:
        return _empty_response("not_found", "live", [query], top_sim)

    result = _synthesize_and_verify(
        query=query,
        chunks=chunks,
        tier="live",
        top_sim=top_sim,
    )

    if result["status"] == "found" and articles:
        try:
            written = write_articles_to_lancedb(articles)
            result["reasoning"]["articles_added_to_kb"] = written
        except Exception as exc:
            # Write-back is best-effort; never fail the user-facing request.
            result["reasoning"]["articles_added_to_kb"] = 0
            result["reasoning"]["write_back_error"] = str(exc)

    return result


def _synthesize_and_verify(
    query: str, chunks: list[dict], tier: str, top_sim: float
) -> dict:
    answer = synthesize(query, chunks)

    if answer == INSUFFICIENT:
        return _empty_response("insufficient_evidence", tier, [query], top_sim)

    verdict = verify(answer, chunks)
    confidence = verdict["confidence"]
    unsupported = verdict["unsupported_claims"]

    if confidence < settings.CONFIDENCE_THRESHOLD:
        return _empty_response(
            "insufficient_evidence",
            tier,
            [query],
            top_sim,
            unsupported=unsupported,
        )

    sources = [
        _build_source(i + 1, chunk) for i, chunk in enumerate(chunks)
    ]

    return {
        "status": "found",
        "tier": tier,
        "answer": answer,
        "confidence": round(confidence, 4),
        "sources": sources,
        "reasoning": {
            "queries_searched": [query],
            "top_similarity": round(top_sim, 4),
            "verifier_unsupported_claims": unsupported,
        },
    }
