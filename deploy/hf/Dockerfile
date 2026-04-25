# MedCite backend — Hugging Face Spaces Dockerfile (Docker SDK).
# Spaces requirements honoured here:
#   - Listen on port 7860 (HF Spaces hard-coded routing).
#   - Run as non-root user, UID 1000 ("user").
#   - Read API keys from injected env vars (Space "Secrets") — no .env file shipped.
#
# This image bundles the existing 53.5 MB LanceDB cache (~17,456 chunks) so Tier-1
# queries hit the same corpus as the local laptop. Self-improvement write-backs
# during a Space session land on the container's writable filesystem; they are
# lost on the next container restart, which is acceptable for the hackathon demo.

FROM python:3.12-slim

# Build deps for any wheels that need to compile (sentence-transformers /
# tokenizers occasionally fall back to source on slim images). git is needed
# because some HF Hub model fetches use it. ca-certificates for HTTPS to
# Gemini / Groq / PubMed.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces requires a non-root user with UID 1000.
RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    HF_HOME=/home/user/.cache/huggingface

WORKDIR $HOME/app

# Install Python deps first so this Docker layer is cached across code edits.
COPY --chown=user:user backend/requirements.txt ./backend/requirements.txt
RUN pip install --user --no-cache-dir --upgrade pip \
 && pip install --user --no-cache-dir -r backend/requirements.txt

# Pre-download the embedding model into the image so the first user query
# doesn't time out waiting for a 90 MB cold model fetch on the Space's
# shared bandwidth.
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Backend code + the prebuilt LanceDB cache. Layout matches the local repo
# so backend/config.py's ROOT_DIR = parent.parent resolves to /home/user/app
# and LANCEDB_PATH resolves to /home/user/app/data/lancedb (where we copy it).
COPY --chown=user:user backend/ ./backend/
COPY --chown=user:user data/lancedb/ ./data/lancedb/

WORKDIR $HOME/app/backend

EXPOSE 7860

# --proxy-headers so X-Forwarded-* from the HF reverse proxy are honoured.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers"]
