"""
Local vector search against the LanceDB table populated by ingestion.embedder.

Returns the top-5 chunks ranked by cosine similarity plus their full metadata
so the pipeline can stitch [n] citations -> real PubMed URLs without ever
asking an LLM to produce URLs.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import lancedb
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402
from retrieval.query_preprocess import retrieval_query_variants  # noqa: E402

# Wider than top_k so a second ANN probe can surface chunks re-ranked up by
# the primary-query embedding.
ANN_PROBE_LIMIT = 15

# Second (filler-stripped) ANN probe only for longer questions so short
# clinical phrasing (e.g. metformin + CKD) keeps the original single-probe path.
_MIN_WORDS_FOR_FUSION = 9

_model: SentenceTransformer | None = None
_db = None  # lancedb.DBConnection
_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


def get_db():
    """Shared LanceDB connection. Reused by live_search write-back so that
    reads and writes go through the same in-process handle (otherwise the
    reader's cached snapshot misses freshly written rows — see spec §12
    'Known minor issue')."""
    global _db
    if _db is None:
        with _lock:
            if _db is None:
                _db = lancedb.connect(str(settings.LANCEDB_PATH))
    return _db


def get_table():
    """Always re-open the table so we observe the latest committed version
    (LanceDB Table handles are snapshot-pinned; caching them across writes
    causes the reader to keep returning pre-writeback similarities)."""
    db = get_db()
    try:
        return db.open_table(settings.LANCE_TABLE_NAME)
    except Exception as exc:
        raise RuntimeError(
            f"LanceDB table '{settings.LANCE_TABLE_NAME}' not found at "
            f"{settings.LANCEDB_PATH}. Run `python -m ingestion.embedder` first. "
            f"(underlying error: {exc})"
        ) from exc


def embed_query(query: str) -> list[float]:
    """Embed a user query with the same model used at ingestion time."""
    model = _get_model()
    vec = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
    return vec.tolist()


def _row_key(row: dict) -> tuple:
    kid = row.get("id")
    if kid is not None and str(kid) != "":
        return ("id", str(kid))
    return ("pmid_ci", str(row.get("pmid", "")), int(row.get("chunk_index", 0) or 0))


def _chunk_vector_list(row: dict) -> list[float] | None:
    v = row.get("vector")
    if v is None:
        return None
    if hasattr(v, "tolist"):
        return v.tolist()
    if isinstance(v, list):
        return v
    try:
        return list(v)
    except TypeError:
        return None


def _hit_from_row(row: dict, similarity: float) -> dict:
    return {
        "chunk_text": row.get("chunk_text", ""),
        "similarity": similarity,
        "metadata": {
            "pmid": row.get("pmid", ""),
            "title": row.get("title", ""),
            "journal": row.get("journal", ""),
            "year": row.get("year", ""),
            "authors": row.get("authors", ""),
            "publication_type": row.get("publication_type", "Journal Article"),
            "url": row.get("url", ""),
            "doi_url": row.get("doi_url", ""),
            "specialty": row.get("specialty", ""),
            "chunk_index": row.get("chunk_index", 0),
        },
    }


def _search_local_single_probe(table, query: str, top_k: int) -> list[dict]:
    """Original single-vector ANN path (used as fallback)."""
    vec = embed_query(query)
    rows = (
        table.search(vec)
        .metric("cosine")
        .limit(top_k)
        .to_list()
    )
    results: list[dict] = []
    for r in rows:
        distance = float(r.get("_distance", 1.0))
        similarity = 1.0 - distance
        results.append(_hit_from_row(r, similarity))
    return results


def search_local(query: str, top_k: int = 5) -> list[dict]:
    """
    Return up to `top_k` chunks from LanceDB ranked by cosine similarity to
    the **primary** normalized user text (first retrieval variant).

    Runs up to two ANN probes (full normalized query + optional filler-stripped
    variant), merges candidates, then re-ranks by dot(primary_embedding, chunk)
    so pipeline `top_similarity` matches the original question, not the probe.

    Each result:
        {
          "chunk_text": "...",
          "similarity": 0.87,
          "metadata": {pmid, title, journal, year, authors,
                       publication_type, url, doi_url, specialty, chunk_index}
        }

    Since vectors are normalized at ingestion, cosine_distance is in [0, 2]
    and similarity = 1 - cosine_distance is in [-1, 1] (practically [0, 1]
    for semantically similar text).
    """
    variants = retrieval_query_variants(query)
    if not variants:
        return []

    table = get_table()
    model = _get_model()
    primary_text = variants[0]
    if len(variants) > 1 and len(primary_text.split()) < _MIN_WORDS_FOR_FUSION:
        variants = [primary_text]

    if len(variants) == 1:
        return _search_local_single_probe(table, primary_text, top_k)

    q_primary = embed_query(primary_text)

    probe_limit = max(top_k, ANN_PROBE_LIMIT)
    by_key: dict[tuple, dict] = {}
    for probe in variants:
        probe_vec = model.encode(
            [probe], normalize_embeddings=True, show_progress_bar=False
        )[0]
        rows = (
            table.search(probe_vec.tolist())
            .metric("cosine")
            .limit(probe_limit)
            .to_list()
        )
        for r in rows:
            k = _row_key(r)
            if k not in by_key:
                by_key[k] = r

    scored: list[tuple[float, dict]] = []
    for r in by_key.values():
        cv = _chunk_vector_list(r)
        if cv is None or len(cv) != len(q_primary):
            continue
        sim = sum(float(a) * float(b) for a, b in zip(q_primary, cv))
        scored.append((sim, r))

    if not scored:
        return _search_local_single_probe(table, primary_text, top_k)

    scored.sort(key=lambda x: x[0], reverse=True)
    return [_hit_from_row(r, sim) for sim, r in scored[:top_k]]


def top_similarity(results: list[dict]) -> float:
    """Helper: highest similarity in a result list, or 0.0 if empty."""
    if not results:
        return 0.0
    return max(r["similarity"] for r in results)


if __name__ == "__main__":
    # Quick smoke test
    import json

    queries = [
        "renal dose adjustments for metformin in CKD",
        "SGLT2 inhibitors side effects elderly",
        "first-line treatment for drug-resistant tuberculosis",
    ]
    for q in queries:
        print(f"\n=== {q} ===")
        hits = search_local(q, top_k=3)
        print(f"top_similarity = {top_similarity(hits):.3f}")
        for h in hits:
            print(
                f"  [{h['similarity']:.3f}] "
                f"{h['metadata'].get('title', '')[:80]} "
                f"({h['metadata'].get('publication_type', '')})"
            )
        print(json.dumps(hits[0]["metadata"], indent=2) if hits else "no hits")
