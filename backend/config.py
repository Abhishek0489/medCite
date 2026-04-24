"""Central config loaded from .env. Import `settings` from here everywhere."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    NCBI_API_KEY: str = os.getenv("NCBI_API_KEY", "")
    NCBI_EMAIL: str = os.getenv("NCBI_EMAIL", "medcite@example.com")

    CHROMADB_PATH: Path = ROOT_DIR / os.getenv("CHROMADB_PATH", "data/chromadb").lstrip("./")
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.80"))
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

    SYNTHESIZER_MODEL: str = os.getenv("SYNTHESIZER_MODEL", "gemini-2.0-flash")
    VERIFIER_MODEL: str = os.getenv("VERIFIER_MODEL", "llama-3.3-70b-versatile")
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    CHROMA_COLLECTION: str = "medcite_articles"

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
settings.CHROMADB_PATH.mkdir(parents=True, exist_ok=True)
settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
