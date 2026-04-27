# MedCite

Medical Q&A for doctors — fast, cited, trustworthy. Built for the Jubilant Pharma hackathon.

**Full project spec:** see [`PROJECT_SPEC.md`](./PROJECT_SPEC.md).

## What it does

Doctor types a medical question. System:

1. Searches a local curated knowledge base of PubMed articles (Diabetes + Cardiology).
2. If found → returns a short answer with clickable PubMed citations in ~3 seconds.
3. If not found → doctor can escalate to a live multi-AI search (PubMed API + Gemini + Llama via Groq).
4. If confidence is low → system honestly says "No reliable answer found".

Every citation is real. LLMs never invent URLs.

## Quick start

```bash
# Backend
cd backend
python -m venv .venv
# activate venv (Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Stack

- **Frontend:** Next.js 16 (App Router, JavaScript) + Tailwind 4 + shadcn/ui
- **Backend:** FastAPI + LanceDB + sentence-transformers (MiniLM-L6-v2)
- **LLMs:** Google Gemini 2.5 Flash-Lite (synthesizer) + Meta Llama 3.3 70B via Groq (verifier)
- **Data:** PubMed E-utilities API

## Status

See section 12 in [`PROJECT_SPEC.md`](./PROJECT_SPEC.md) for current progress.
