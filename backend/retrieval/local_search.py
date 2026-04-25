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


def search_local(query: str, top_k: int = 5) -> list[dict]:
    """
    Return up to `top_k` chunks from LanceDB ranked by cosine similarity.

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
    table = get_table()
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
        results.append(
            {
                "chunk_text": r.get("chunk_text", ""),
                "similarity": similarity,
                "metadata": {
                    "pmid": r.get("pmid", ""),
                    "title": r.get("title", ""),
                    "journal": r.get("journal", ""),
                    "year": r.get("year", ""),
                    "authors": r.get("authors", ""),
                    "publication_type": r.get("publication_type", "Journal Article"),
                    "url": r.get("url", ""),
                    "doi_url": r.get("doi_url", ""),
                    "specialty": r.get("specialty", ""),
                    "chunk_index": r.get("chunk_index", 0),
                },
            }
        )
    return results


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
