"""
Live PubMed fallback (Component 3 of the spec).

Runs only when the doctor explicitly hits /query/live. Steps:

1. Call PubMed E-utilities to get the top-N PMIDs for the query.
2. Fetch abstracts for those PMIDs.
3. Chunk each article using the same logic as ingestion.
4. Return chunks in the same shape local_search produces, so the pipeline
   can feed them to the synthesizer without branching logic.

The caller (pipeline.py) is responsible for:
  - running synthesizer + verifier
  - if confidence passes, persisting the freshly fetched articles back
    into LanceDB so the same query hits Tier 1 next time (self-improvement).
"""
from __future__ import annotations

import sys
import threading
import re
from pathlib import Path

import httpx
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402
from ingestion.chunker import article_to_chunks  # noqa: E402
from pubmed_client import HTTP_TIMEOUT, fetch_articles, search_pmids  # noqa: E402
from retrieval.local_search import get_db  # noqa: E402


LIVE_TOP_PMIDS = 10
LIVE_TOP_CHUNKS = 5
LIVE_SEARCH_STOPWORDS = {
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
    "best",
    "first-line",
    "recommended",
    "dose",
}

_model: SentenceTransformer | None = None
_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


def _strip_live_search_stopwords(query: str) -> str:
    """
    Build a PubMed-friendly fallback query by dropping filler stopwords.
    Returns the original query if stripping would leave fewer than 2 terms.
    """
    tokens = re.findall(r"[A-Za-z0-9.-]+", query)
    filtered = [t for t in tokens if t.lower() not in LIVE_SEARCH_STOPWORDS]
    if len(filtered) < 2:
        return query.strip()
    return " ".join(filtered)


def live_search(query: str) -> tuple[list[dict], list[dict]]:
    """
    Run a live PubMed search and return:
        chunks   - list of chunk dicts ready for the synthesizer (same shape
                   as local_search.search_local), ranked by cosine similarity
                   against the query embedding.
        articles - raw article dicts fetched from PubMed (for write-back
                   into LanceDB after verification passes).
    """
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        pmids = search_pmids(client, query, retmax=LIVE_TOP_PMIDS)
        if not pmids:
            fallback_query = _strip_live_search_stopwords(query)
            if fallback_query and fallback_query != query.strip():
                pmids = search_pmids(client, fallback_query, retmax=LIVE_TOP_PMIDS)
            if not pmids:
                return [], []
        articles = fetch_articles(client, pmids)

    if not articles:
        return [], articles

    # Chunk everything we just fetched.
    all_chunks: list[dict] = []
    for article in articles:
        article.setdefault("specialty", "live")
        all_chunks.extend(article_to_chunks(article))

    if not all_chunks:
        return [], articles

    # Rank chunks locally by cosine similarity to the query so the synthesizer
    # sees the most-relevant passages first.
    model = _get_model()
    query_vec = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
    chunk_vecs = model.encode(
        [c["chunk_text"] for c in all_chunks],
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    scored: list[dict] = []
    for c, v in zip(all_chunks, chunk_vecs):
        similarity = float((query_vec * v).sum())
        md = c["metadata"]
        scored.append(
            {
                "chunk_text": c["chunk_text"],
                "similarity": similarity,
                "metadata": {
                    "pmid": str(md.get("pmid", "")),
                    "title": md.get("title", ""),
                    "journal": md.get("journal", ""),
                    "year": str(md.get("year", "") or ""),
                    "authors": md.get("authors", ""),
                    "publication_type": md.get("publication_type", "Journal Article"),
                    "url": md.get("url", ""),
                    "doi_url": md.get("doi_url", ""),
                    "specialty": md.get("specialty", "live"),
                    "chunk_index": int(md.get("chunk_index", 0) or 0),
                },
                "_id": c["id"],
                "_vector": v.tolist(),
            }
        )

    scored.sort(key=lambda r: r["similarity"], reverse=True)
    return scored[:LIVE_TOP_CHUNKS], articles


def write_articles_to_lancedb(articles: list[dict]) -> int:
    """
    Persist freshly-fetched articles into LanceDB so Tier 1 catches the same
    query next time. Embeds with the same model + normalization as ingestion.

    Returns the number of chunks written.
    """
    if not articles:
        return 0

    chunks: list[dict] = []
    for article in articles:
        article.setdefault("specialty", "live")
        chunks.extend(article_to_chunks(article))

    if not chunks:
        return 0

    model = _get_model()
    embeddings = model.encode(
        [c["chunk_text"] for c in chunks],
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    rows = []
    for c, emb in zip(chunks, embeddings):
        md = c["metadata"]
        rows.append(
            {
                "vector": emb.tolist(),
                "id": c["id"],
                "pmid": str(md.get("pmid", "")),
                "title": md.get("title", "") or "",
                "journal": md.get("journal", "") or "",
                "year": str(md.get("year", "") or ""),
                "authors": md.get("authors", "") or "",
                "publication_type": md.get("publication_type", "Journal Article") or "Journal Article",
                "url": md.get("url", "") or "",
                "doi_url": md.get("doi_url", "") or "",
                "specialty": md.get("specialty", "live") or "live",
                "chunk_index": int(md.get("chunk_index", 0) or 0),
                "chunk_text": c["chunk_text"],
            }
        )

    db = get_db()
    try:
        table = db.open_table(settings.LANCE_TABLE_NAME)
    except Exception:
        table = None

    if table is None:
        table = db.create_table(settings.LANCE_TABLE_NAME, data=rows)
        return len(rows)

    # De-duplicate: drop any rows with matching chunk ids before re-insert.
    ids_csv = ", ".join(f"'{r['id']}'" for r in rows)
    try:
        table.delete(f"id IN ({ids_csv})")
    except Exception:
        pass
    table.add(rows)
    return len(rows)
