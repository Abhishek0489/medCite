"""Central config loaded from .env. Import `settings` from here everywhere."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
# override=True so edits to .env are picked up on uvicorn --reload without
# needing a full process restart (default load_dotenv leaves existing env vars
# alone and silently uses the stale values).
load_dotenv(ROOT_DIR / ".env", override=True)


class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    NCBI_API_KEY: str = os.getenv("NCBI_API_KEY", "")
    NCBI_EMAIL: str = os.getenv("NCBI_EMAIL", "medcite@example.com")

    LANCEDB_PATH: Path = ROOT_DIR / os.getenv("LANCEDB_PATH", "data/lancedb").lstrip("./")
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.55"))
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

    # gemini-2.5-flash-lite is the PRIMARY synthesizer. Rationale:
    # gemini-2.5-flash is a "thinking" model that burns hundreds of internal
    # reasoning tokens against max_output_tokens before emitting any visible
    # text; on this "read 5 chunks -> cite what's there" task it either
    # truncates the answer mid-sentence (MAX_TOKENS) or talks itself into
    # abstaining. flash-lite has much tighter reasoning and produces stable,
    # complete, cited answers at temperature=0. We keep flash as the fallback
    # in case flash-lite is capacity-constrained, since free-tier quotas pool
    # separately between the two models.
    SYNTHESIZER_MODEL: str = os.getenv("SYNTHESIZER_MODEL", "gemini-2.5-flash-lite")
    SYNTHESIZER_FALLBACK_MODEL: str = os.getenv(
        "SYNTHESIZER_FALLBACK_MODEL", "gemini-2.5-flash"
    )
    VERIFIER_MODEL: str = os.getenv("VERIFIER_MODEL", "llama-3.3-70b-versatile")
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    LANCE_TABLE_NAME: str = "medcite_articles"

    RAW_DATA_DIR: Path = ROOT_DIR / "data" / "raw"

    SPECIALTIES: dict[str, str] = {
        "diabetes": (
            '("diabetes mellitus"[MeSH Terms] OR "diabetes"[Title/Abstract]) '
            'AND ("2015"[Date - Publication] : "3000"[Date - Publication]) '
            "AND English[lang] AND hasabstract"
        ),
        "cardiology": (
            '("cardiovascular diseases"[MeSH Terms] OR "heart failure"[Title/Abstract] '
            'OR "myocardial infarction"[Title/Abstract] OR "hypertension"[Title/Abstract]) '
            'AND ("2015"[Date - Publication] : "3000"[Date - Publication]) '
            "AND English[lang] AND hasabstract"
        ),
    }
    ARTICLES_PER_SPECIALTY: int = 5000


settings = Settings()
settings.LANCEDB_PATH.mkdir(parents=True, exist_ok=True)
settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
