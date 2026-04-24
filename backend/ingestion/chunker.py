"""Split article abstracts into passage-sized chunks for embedding."""
from __future__ import annotations

from typing import Iterator


CHUNK_TARGET_WORDS = 180
CHUNK_OVERLAP_WORDS = 30


def chunk_text(text: str, target: int = CHUNK_TARGET_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    """
    Split text into overlapping word-based chunks.

    PubMed abstracts are typically 200-400 words, so most articles produce 1-3 chunks.
    Overlap preserves context across chunk boundaries so key sentences aren't split.
    """
    words = text.split()
    if len(words) <= target:
        return [text.strip()] if text.strip() else []

    chunks: list[str] = []
    step = target - overlap
    for start in range(0, len(words), step):
        end = start + target
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(words):
            break
    return chunks


def article_to_chunks(article: dict) -> Iterator[dict]:
    """
    Convert one article dict (from pubmed_downloader) into chunk records
    ready for embedding, each carrying full metadata.
    """
    body = f"{article['title']}. {article['abstract']}"
    for i, chunk in enumerate(chunk_text(body)):
        yield {
            "id": f"{article['pmid']}_chunk_{i}",
            "chunk_text": chunk,
            "metadata": {
                "pmid": article["pmid"],
                "title": article["title"],
                "journal": article.get("journal", ""),
                "year": article.get("year", ""),
                "authors": article.get("authors", ""),
                "publication_type": article.get("publication_type", "Journal Article"),
                "url": article["url"],
                "doi_url": article.get("doi_url", ""),
                "specialty": article.get("specialty", ""),
                "chunk_index": i,
                "chunk_text": chunk,
            },
        }
