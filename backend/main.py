"""
FastAPI entrypoint for MedCite backend.

Endpoints (response shape fixed by spec §6):

    POST /query/local   - Tier 1: LanceDB-only retrieval + synth + verify.
    POST /query/live    - Tier 2: PubMed live fetch + synth + verify, also
                          writes fresh articles back to LanceDB on success.
    GET  /health        - Simple liveness probe.

Run:
    cd backend
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import settings  # noqa: E402
from pipeline import run_live_query, run_local_query  # noqa: E402


app = FastAPI(
    title="MedCite",
    version="0.1.0",
    description="Cited medical Q&A over a local PubMed knowledge base with live-search fallback.",
)

# Frontend runs on Vercel / localhost:3000 in dev. Keep CORS permissive —
# the backend has no auth and the payloads are non-sensitive.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)


class Source(BaseModel):
    citation_number: int
    title: str
    journal: str = ""
    year: str = ""
    authors: str = ""
    publication_type: str = "Journal Article"
    url: str = ""
    doi_url: str = ""
    quoted_passage: str = ""


class Reasoning(BaseModel):
    queries_searched: list[str]
    top_similarity: float
    verifier_unsupported_claims: list[str] = []
    articles_added_to_kb: int | None = None
    write_back_error: str | None = None


class QueryResponse(BaseModel):
    status: str
    tier: str
    answer: str
    confidence: float
    sources: list[Source]
    reasoning: Reasoning


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "lancedb_path": str(settings.LANCEDB_PATH),
        "lance_table": settings.LANCE_TABLE_NAME,
        "synthesizer_model": settings.SYNTHESIZER_MODEL,
        "verifier_model": settings.VERIFIER_MODEL,
        "similarity_threshold": settings.SIMILARITY_THRESHOLD,
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
    }


@app.post("/query/local", response_model=QueryResponse)
def query_local(req: QueryRequest) -> QueryResponse:
    """Tier 1 — local LanceDB retrieval only."""
    try:
        result = run_local_query(req.query.strip())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Local pipeline failed: {exc}")
    return QueryResponse(**result)


@app.post("/query/live", response_model=QueryResponse)
def query_live(req: QueryRequest) -> QueryResponse:
    """Tier 2 — live PubMed fetch + same synth/verify pipeline.
    Writes new articles into LanceDB on a verified answer."""
    try:
        result = run_live_query(req.query.strip())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Live pipeline failed: {exc}")
    return QueryResponse(**result)
