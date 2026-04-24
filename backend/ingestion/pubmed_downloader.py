"""
Download PubMed abstracts for MedCite's local knowledge base.

Uses the shared httpx-based PubMed client (backend/pubmed_client.py) — no
biopython, no compiled deps. Saves raw articles as JSONL per specialty in
data/raw/. Next step: chunker.py + embedder.py will pick these up.

Usage:
    cd backend
    python -m ingestion.pubmed_downloader

Rate limits: 3 req/s without NCBI_API_KEY, 10 req/s with one.
For 10,000 articles this takes ~30-60 min depending on key availability.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Iterator

import httpx
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402
from pubmed_client import HTTP_TIMEOUT, fetch_articles, search_pmids  # noqa: E402


BATCH_SIZE = 200


def _chunked(seq: list[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def download_specialty(
    client: httpx.Client, name: str, query: str, target_count: int
) -> Path:
    """Download articles for one specialty, save to JSONL, return path."""
    out_path = settings.RAW_DATA_DIR / f"{name}.jsonl"

    if out_path.exists():
        with out_path.open("r", encoding="utf-8") as f:
            existing = sum(1 for _ in f)
        if existing >= target_count:
            print(f"[{name}] already has {existing} articles at {out_path}, skipping.")
            return out_path
        print(f"[{name}] partial file exists ({existing}). Re-running from scratch.")

    print(f"[{name}] searching PubMed for up to {target_count} articles...")
    pmids = search_pmids(client, query, retmax=target_count)
    print(f"[{name}] got {len(pmids)} PMIDs. Fetching in batches of {BATCH_SIZE}...")

    sleep_s = 0.12 if settings.NCBI_API_KEY else 0.35
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for batch in tqdm(list(_chunked(pmids, BATCH_SIZE)), desc=f"{name}"):
            articles = fetch_articles(client, batch)
            for article in articles:
                article["specialty"] = name
                f.write(json.dumps(article, ensure_ascii=False) + "\n")
                count += 1
            time.sleep(sleep_s)

    print(f"[{name}] saved {count} articles -> {out_path}")
    return out_path


def main() -> None:
    print(f"NCBI email: {settings.NCBI_EMAIL}")
    print(f"NCBI API key: {'SET' if settings.NCBI_API_KEY else 'not set (slower rate limit)'}")
    print(f"Target: {settings.ARTICLES_PER_SPECIALTY} articles per specialty")
    print(f"Output: {settings.RAW_DATA_DIR}\n")

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        for name, query in settings.SPECIALTIES.items():
            download_specialty(client, name, query, settings.ARTICLES_PER_SPECIALTY)

    print("\nAll specialties downloaded. Next: run `python -m ingestion.embedder`.")


if __name__ == "__main__":
    main()
