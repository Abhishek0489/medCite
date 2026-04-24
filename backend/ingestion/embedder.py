"""
Embed article chunks with sentence-transformers and write them to LanceDB.

Run after pubmed_downloader.py.

Usage:
    cd backend
    python -m ingestion.embedder

LanceDB records are flat dicts with a 'vector' key (list[float]) plus metadata
at the top level. We normalize embeddings so cosine similarity == dot product.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lancedb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402
from ingestion.chunker import article_to_chunks  # noqa: E402


EMBED_BATCH = 64


def _iter_articles() -> list[dict]:
    """Load all downloaded articles from JSONL files in data/raw/."""
    articles: list[dict] = []
    for path in sorted(settings.RAW_DATA_DIR.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                articles.append(json.loads(line))
    return articles


def _build_record(chunk: dict, vector: list[float]) -> dict:
    """Flatten chunk + metadata into a single LanceDB row."""
    md = chunk["metadata"]
    return {
        "vector": vector,
        "id": chunk["id"],
        "pmid": str(md.get("pmid", "")),
        "title": md.get("title", "") or "",
        "journal": md.get("journal", "") or "",
        "year": str(md.get("year", "") or ""),
        "authors": md.get("authors", "") or "",
        "publication_type": md.get("publication_type", "Journal Article") or "Journal Article",
        "url": md.get("url", "") or "",
        "doi_url": md.get("doi_url", "") or "",
        "specialty": md.get("specialty", "") or "",
        "chunk_index": int(md.get("chunk_index", 0) or 0),
        "chunk_text": chunk["chunk_text"],
    }


def main() -> None:
    print(f"Loading articles from {settings.RAW_DATA_DIR}...")
    articles = _iter_articles()
    print(f"Loaded {len(articles)} articles.")

    print("Chunking...")
    chunks: list[dict] = []
    for article in articles:
        chunks.extend(article_to_chunks(article))
    print(f"Produced {len(chunks)} chunks.")

    if not chunks:
        print("No chunks to embed. Did you run `python -m ingestion.pubmed_downloader` first?")
        return

    print(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
    model = SentenceTransformer(settings.EMBEDDING_MODEL)

    print(f"Connecting to LanceDB at {settings.LANCEDB_PATH}")
    db = lancedb.connect(str(settings.LANCEDB_PATH))

    try:
        db.drop_table(settings.LANCE_TABLE_NAME)
        print(f"Dropped existing table '{settings.LANCE_TABLE_NAME}'")
    except Exception:
        pass

    print("Embedding + writing to LanceDB...")
    table = None
    for start in tqdm(range(0, len(chunks), EMBED_BATCH)):
        batch = chunks[start : start + EMBED_BATCH]
        texts = [c["chunk_text"] for c in batch]
        embeddings = model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        rows = [
            _build_record(c, emb.tolist())
            for c, emb in zip(batch, embeddings)
        ]
        if table is None:
            table = db.create_table(settings.LANCE_TABLE_NAME, data=rows)
        else:
            table.add(rows)

    count = table.count_rows() if table is not None else 0
    print(
        f"\nLanceDB table '{settings.LANCE_TABLE_NAME}' now has {count} chunks "
        f"at {settings.LANCEDB_PATH}"
    )
    print("Next: build local_search.py and test retrieval.")


if __name__ == "__main__":
    main()
