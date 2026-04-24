"""
Embed article chunks with sentence-transformers and write them to ChromaDB.

Run after pubmed_downloader.py.

Usage:
    cd backend
    python -m ingestion.embedder
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
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


def main() -> None:
    print(f"Loading articles from {settings.RAW_DATA_DIR}...")
    articles = _iter_articles()
    print(f"Loaded {len(articles)} articles.")

    print("Chunking...")
    records: list[dict] = []
    for article in articles:
        records.extend(article_to_chunks(article))
    print(f"Produced {len(records)} chunks.")

    print(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
    model = SentenceTransformer(settings.EMBEDDING_MODEL)

    print(f"Connecting to ChromaDB at {settings.CHROMADB_PATH}")
    client = chromadb.PersistentClient(
        path=str(settings.CHROMADB_PATH),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    try:
        client.delete_collection(settings.CHROMA_COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    print("Embedding + writing to ChromaDB...")
    for start in tqdm(range(0, len(records), EMBED_BATCH)):
        batch = records[start : start + EMBED_BATCH]
        texts = [r["chunk_text"] for r in batch]
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        collection.add(
            ids=[r["id"] for r in batch],
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=[r["metadata"] for r in batch],
        )

    count = collection.count()
    print(f"\nChromaDB collection '{settings.CHROMA_COLLECTION}' now has {count} chunks.")
    print("Next: build local_search.py and test retrieval.")


if __name__ == "__main__":
    main()
