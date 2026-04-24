"""
Download PubMed abstracts for MedCite's local knowledge base.

Uses httpx + stdlib xml.etree.ElementTree (no biopython, no compiled deps).
Hits NCBI E-utilities directly. Saves raw articles as JSONL per specialty
in data/raw/. Next step: chunker.py + embedder.py will pick these up.

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
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings  # noqa: E402


EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BATCH_SIZE = 200
HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _common_params() -> dict:
    p: dict[str, str] = {
        "tool": "medcite",
        "email": settings.NCBI_EMAIL,
    }
    if settings.NCBI_API_KEY:
        p["api_key"] = settings.NCBI_API_KEY
    return p


@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30))
def _search_pmids(client: httpx.Client, query: str, retmax: int) -> list[str]:
    """Search PubMed via ESearch, return list of PMIDs sorted by relevance."""
    params = {
        **_common_params(),
        "db": "pubmed",
        "term": query,
        "retmax": str(retmax),
        "sort": "relevance",
        "retmode": "json",
    }
    r = client.get(f"{EUTILS_BASE}/esearch.fcgi", params=params)
    r.raise_for_status()
    data = r.json()
    return data["esearchresult"]["idlist"]


@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30))
def _fetch_batch(client: httpx.Client, pmids: list[str]) -> list[dict]:
    """Fetch a batch of articles via EFetch (PubMed XML), return parsed list."""
    params = {
        **_common_params(),
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "medline",
        "retmode": "xml",
    }
    r = client.get(f"{EUTILS_BASE}/efetch.fcgi", params=params)
    r.raise_for_status()

    root = ET.fromstring(r.content)
    articles: list[dict] = []
    for article_el in root.findall(".//PubmedArticle"):
        parsed = _parse_article(article_el)
        if parsed is not None:
            articles.append(parsed)
    return articles


def _text(el: ET.Element | None) -> str:
    """Flatten an element's text (including nested tags) into a single string."""
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _parse_article(article_el: ET.Element) -> dict | None:
    """Extract the fields we care about. Returns None if required fields missing."""
    try:
        pmid_el = article_el.find(".//MedlineCitation/PMID")
        if pmid_el is None or not pmid_el.text:
            return None
        pmid = pmid_el.text.strip()

        title = _text(article_el.find(".//Article/ArticleTitle"))
        if not title:
            return None

        # Abstract can be multiple <AbstractText> elements with Label attributes
        abstract_parts: list[str] = []
        for at in article_el.findall(".//Article/Abstract/AbstractText"):
            label = at.attrib.get("Label", "").strip()
            body = _text(at)
            if not body:
                continue
            abstract_parts.append(f"{label}: {body}" if label else body)
        abstract_text = " ".join(abstract_parts).strip()
        if len(abstract_text) < 100:
            return None

        journal = _text(article_el.find(".//Article/Journal/Title"))

        year = ""
        pub_date = article_el.find(".//Article/Journal/JournalIssue/PubDate")
        if pub_date is not None:
            year_el = pub_date.find("Year")
            if year_el is not None and year_el.text:
                year = year_el.text.strip()
            else:
                medline_date = pub_date.find("MedlineDate")
                if medline_date is not None and medline_date.text:
                    year = medline_date.text.strip()[:4]

        authors_list = article_el.findall(".//Article/AuthorList/Author")
        author_names: list[str] = []
        for a in authors_list[:3]:
            last = _text(a.find("LastName"))
            initials = _text(a.find("Initials"))
            if last:
                author_names.append(f"{last} {initials}".strip())
        authors = ", ".join(author_names)
        if len(authors_list) > 3 and authors:
            authors += ", et al."

        pub_types = [
            _text(pt) for pt in article_el.findall(".//Article/PublicationTypeList/PublicationType")
        ]
        publication_type = _pick_best_pub_type(pub_types)

        doi = ""
        for aid in article_el.findall(".//PubmedData/ArticleIdList/ArticleId"):
            if aid.attrib.get("IdType") == "doi" and aid.text:
                doi = aid.text.strip()
                break

        return {
            "pmid": pmid,
            "title": title,
            "abstract": abstract_text,
            "journal": journal,
            "year": year,
            "authors": authors,
            "publication_type": publication_type,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "doi_url": f"https://doi.org/{doi}" if doi else "",
        }
    except (AttributeError, KeyError, IndexError, TypeError, ET.ParseError):
        return None


EVIDENCE_RANK = [
    "Meta-Analysis",
    "Systematic Review",
    "Randomized Controlled Trial",
    "Clinical Trial",
    "Practice Guideline",
    "Guideline",
    "Review",
    "Observational Study",
    "Comparative Study",
    "Case Reports",
    "Journal Article",
]


def _pick_best_pub_type(pub_types: list[str]) -> str:
    """Pick the highest-evidence publication type from the list."""
    for ranked in EVIDENCE_RANK:
        if ranked in pub_types:
            return ranked
    return pub_types[0] if pub_types else "Journal Article"


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
    pmids = _search_pmids(client, query, retmax=target_count)
    print(f"[{name}] got {len(pmids)} PMIDs. Fetching in batches of {BATCH_SIZE}...")

    sleep_s = 0.12 if settings.NCBI_API_KEY else 0.35
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for batch in tqdm(list(_chunked(pmids, BATCH_SIZE)), desc=f"{name}"):
            articles = _fetch_batch(client, batch)
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
