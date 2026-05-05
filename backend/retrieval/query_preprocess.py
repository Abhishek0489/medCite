"""
Deterministic query normalization and retrieval variants for Tier-1 search.

No LLMs. Used to widen LanceDB ANN probes; final scores must always use the
primary (first) variant's embedding against stored chunk vectors — see
local_search.search_local.

Stopwords are split: local embedding strips only grammatical / conversational
filler so clinical tokens (e.g. dose, first-line) stay meaningful. PubMed
E-search retry uses the broader PROJECT_SPEC §9 list including dose/best/etc.
"""
from __future__ import annotations

import re
import unicodedata

# Filler dropped only for the optional *second Lance ANN probe* (embedding).
# Excludes tokens that often carry clinical meaning (dose, first-line, …).
_LOCAL_EMBED_FILLERS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "for",
        "in",
        "on",
        "with",
        "and",
        "or",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "when",
        "where",
        "why",
        "how",
        "please",
        "explain",
        "describe",
        "tell",
        "me",
        "about",
        "briefly",
        "can",
        "you",
        "could",
        "would",
        "should",
        "just",
        "really",
        "very",
    }
)

# PubMed ESearch retry (PROJECT_SPEC §9 polish A) — broader than local embed strip.
PUBMED_FALLBACK_STOPWORDS: frozenset[str] = _LOCAL_EMBED_FILLERS | frozenset(
    {
        "dose",
        "best",
        "first-line",
        "recommended",
    }
)


def normalize_query(raw: str) -> str:
    """Trim, collapse whitespace, NFC unicode, normalize common smart quotes."""
    q = raw.strip()
    q = re.sub(r"\s+", " ", q)
    q = unicodedata.normalize("NFC", q)
    q = (
        q.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    return q.strip()


def strip_filler_tokens(query: str) -> str:
    """
    Drop local embed filler tokens; return original trimmed query if fewer than
    two tokens would remain (same guard pattern as live PubMed retry).
    """
    tokens = re.findall(r"[A-Za-z0-9.-]+", query)
    filtered = [t for t in tokens if t.lower() not in _LOCAL_EMBED_FILLERS]
    if len(filtered) < 2:
        return query.strip()
    return " ".join(filtered)


def retrieval_query_variants(raw: str) -> list[str]:
    """
    Up to two strings: [normalized full text, optional filler-stripped form].
    Stripped form is omitted if identical (case-insensitive) or empty.
    """
    q = normalize_query(raw)
    if not q:
        return []
    stripped = strip_filler_tokens(q)
    out: list[str] = [q]
    if stripped and stripped.casefold() != q.casefold():
        out.append(stripped)
    return out
