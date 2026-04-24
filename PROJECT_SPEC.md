# MedCite — Project Specification

> Single source of truth for the Jubilant Pharma hackathon project. If you are an AI assistant resuming this project, **read this entire file before taking any action**. Do not deviate from Section 3 ("Non-Negotiable Design Principles").

---

## 1. What We Are Building (one paragraph)

A web application where doctors type medical questions and receive short, cited answers with clickable links to the PubMed articles the answer came from. The system first searches a **local curated medical knowledge base** (fast, free, trusted). If no confident answer exists locally, the doctor is shown a button to **escalate to a live multi-AI search** (PubMed API + GPT-4o synthesizer + Claude/Gemini verifier). Every answer either has real citations or explicitly says **"no reliable answer found"** — the system never hallucinates.

## 2. The Problem We Are Solving

- Doctors are overworked and need **fast, trustworthy** medical answers.
- ChatGPT-style tools **hallucinate citations** — unsafe for clinical use.
- Live PubMed search is slow and expensive per query.
- Nobody wants a chatbot; doctors want a **tool** — one question, one answer, with receipts.

## 3. Non-Negotiable Design Principles

These are **hard rules**. Do not violate them during implementation.

1. **LLMs never write URLs.** URLs are built from PMIDs at ingestion time and stored in LanceDB metadata. The Synthesizer outputs only `[1]`, `[2]` citation numbers — the backend stitches URLs in.
2. **LLMs never answer from memory.** The Synthesizer prompt must explicitly forbid using prior knowledge; it must answer from retrieved chunks only, or output `INSUFFICIENT_EVIDENCE`.
3. **A different LLM verifies.** The Verifier must be a different vendor from the Synthesizer (e.g., GPT-4o synthesizes, Claude verifies). Same-model verification is a no-op.
4. **If confidence < 0.75, abstain.** The system returns "No reliable answer found" with an explanation — never a low-confidence guess.
5. **Doctor controls the live search.** Local search runs automatically. Live multi-AI search runs only when the doctor explicitly clicks the button.
6. **Every citation has a quoted passage.** The source card shows the exact chunk text the LLM used — doctors can verify at a glance.
7. **The UI is a clinical tool, not a chatbot.** No chat history, no conversations. One query, one answer card. Clean, whitespace-heavy, neutral palette (white/slate + one accent).

## 4. Architecture — The Four Components

### Component 1: Article Ingestion Pipeline (one-time, Day 1)
- Downloads ~6,000 abstracts from PubMed E-utilities API across 2 specialties (**Diabetes + Cardiology**).
- Chunks each article into ~500-word passages.
- Embeds each chunk with `sentence-transformers/all-MiniLM-L6-v2` (free, local CPU).
- Stores in LanceDB (local persistent vector DB) with full metadata.

### Component 2: Local Retriever (runs on every query)
- Embeds the doctor's query with the same model.
- Runs cosine similarity search in LanceDB.
- Returns top-5 chunks with similarity scores.
- **Threshold logic:** top similarity ≥ `SIMILARITY_THRESHOLD` → "found". Otherwise → "not_found". Default tuned to **0.55** for MiniLM-L6-v2 on this medical corpus (below that, in-scope queries get rejected; above, out-of-scope still cleanly fail at ~0.45). Verifier confidence ≥ 0.75 remains the real safety gate.

### Component 3: Live Multi-AI Fallback (runs only when doctor clicks)
- Calls PubMed E-utilities API for top 10 PMIDs.
- Fetches abstracts for those articles.
- Passes to Synthesizer, then Verifier (same agents as local path).
- **Self-improvement:** embeds and writes new articles back into LanceDB async, so the same query hits Tier 1 next time.

### Component 4: Synthesizer + Verifier (shared between both tiers)
- **Synthesizer (Gemini 2.5 Flash):** receives query + 5 chunks + strict prompt. Outputs 2-3 sentence answer with inline `[1][2]` citations, or `INSUFFICIENT_EVIDENCE`. *(Originally specced as Gemini 2.0 Flash; Google removed 2.0 from the free tier in late 2025, so we use 2.5 Flash — same API, same prompt, stronger model.)*
- **Verifier (Groq — Llama 3.3 70B, different vendor):** receives synthesizer's answer + source chunks. Outputs JSON `{confidence: 0-1, unsupported_claims: [...]}`.
- Final answer returned only if confidence ≥ 0.75.
- **Why this combo:** Google Gemini + Meta Llama (via Groq) = genuine multi-vendor cross-check, both free-tier, both very fast.

## 5. User Flows

### Flow A — Local hit (common case, ~2-5s)
1. Doctor types query → clicks **Ask**.
2. Backend calls `/query/local` → LanceDB match found (similarity ≥ 0.80).
3. Synthesizer + Verifier run on local chunks.
4. Frontend shows: answer + source cards + badge **"Answered from verified knowledge base"** + green confidence meter.

### Flow B — Local miss → doctor escalates (~15-30s total)
1. Doctor types query → clicks **Ask**.
2. Backend calls `/query/local` → no match ≥ 0.80, returns `{status: "not_found"}`.
3. Frontend shows "No verified answer" screen with 3 buttons:
   - **Search live with Multi-AI** (primary)
   - **Show related articles** (shows weaker local matches)
   - **Rephrase my question**
4. Doctor clicks "Search live" → backend calls `/query/live`.
5. Frontend shows progress: `Searching PubMed... → Synthesizing with Gemini... → Verifying with Llama 3.3 (Groq)...`.
6. Answer appears with badge **"Answered by live multi-AI search"** + **"Added to knowledge base for next time"**.

### Flow C — Abstention (any tier, verifier confidence < 0.75)
1. Regardless of tier, if verifier confidence < 0.75 → "No reliable answer" screen.
2. Shows what was searched and suggests rephrasing.

## 6. Data Shapes (contract that must not change)

### LanceDB row shape (flat — no nested `metadata` field)
```json
{
  "pmid": "38245671",
  "title": "SGLT2 inhibitors in heart failure with preserved EF",
  "journal": "New England Journal of Medicine",
  "year": 2024,
  "authors": "Solomon SD, McMurray JJV, et al.",
  "publication_type": "Randomized Controlled Trial",
  "url": "https://pubmed.ncbi.nlm.nih.gov/38245671/",
  "doi_url": "https://doi.org/10.1056/NEJMoa2206286",
  "chunk_text": "In the DELIVER trial, dapagliflozin reduced..."
}
```

### API response shape (both `/query/local` and `/query/live` return this, with different `tier`)
```json
{
  "status": "found | not_found | insufficient_evidence",
  "tier": "local | live",
  "answer": "Metformin can be used in CKD but requires dose adjustment...[1][2]",
  "confidence": 0.92,
  "sources": [
    {
      "citation_number": 1,
      "title": "...",
      "journal": "NEJM",
      "year": 2023,
      "authors": "...",
      "publication_type": "Review",
      "url": "https://pubmed.ncbi.nlm.nih.gov/...",
      "doi_url": "https://doi.org/...",
      "quoted_passage": "For patients with eGFR 30-45..."
    }
  ],
  "reasoning": {
    "queries_searched": ["metformin CKD", "metformin renal impairment"],
    "top_similarity": 0.89,
    "verifier_unsupported_claims": []
  }
}
```

## 7. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript | Fast dev, clean deploys |
| Styling | Tailwind CSS + shadcn/ui | Clinical look out of the box |
| Backend | FastAPI (Python 3.11+) | Fast, great for ML + APIs |
| Vector DB | LanceDB (persistent, local) | Pure Rust, pre-built wheels for Windows Python 3.12/3.13, no MSVC needed. *(Originally planned ChromaDB, swapped due to Windows wheel issue with `chroma-hnswlib`.)* |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Free, CPU-runnable, 384-dim |
| Synthesizer LLM | Google Gemini 2.5 Flash | Free tier (2.0 Flash free tier was removed Q4 2025), fast, strong citation following |
| Verifier LLM | Groq (Llama 3.3 70B) | Free tier, different vendor, ~500 tok/s |
| Article source | PubMed E-utilities API + Europe PMC | Free, no key required (key optional for higher rate limit) |
| Frontend hosting | Vercel | Free, auto-deploy |
| Backend hosting | Railway or Render | Persistent volume for LanceDB |

## 8. Folder Structure

```
medcite/
├── PROJECT_SPEC.md              ← this document
├── README.md
├── .env.example
├── .gitignore
│
├── frontend/                    # Next.js
│   ├── app/
│   │   ├── page.tsx             ← main query page
│   │   ├── layout.tsx
│   │   └── api/                 ← (thin proxy to backend if needed)
│   ├── components/
│   │   ├── QueryCard.tsx
│   │   ├── AnswerPanel.tsx
│   │   ├── SourceCard.tsx
│   │   ├── ConfidenceMeter.tsx
│   │   ├── NotFoundScreen.tsx
│   │   └── LiveSearchProgress.tsx
│   ├── lib/
│   │   └── api.ts               ← fetch helpers
│   ├── package.json
│   └── tailwind.config.ts
│
├── backend/                     # FastAPI
│   ├── main.py                  ← FastAPI app, endpoints
│   ├── requirements.txt
│   ├── ingestion/
│   │   ├── pubmed_downloader.py ← Day 1: pulls abstracts
│   │   ├── chunker.py           ← splits articles
│   │   └── embedder.py          ← writes to LanceDB
│   ├── retrieval/
│   │   ├── local_search.py      ← LanceDB queries
│   │   └── live_search.py       ← PubMed API fallback (Component 3)
│   ├── agents/
│   │   ├── synthesizer.py       ← Gemini 2.0 Flash
│   │   └── verifier.py          ← Groq (Llama 3.3 70B)
│   ├── pipeline.py              ← orchestration
│   └── config.py                ← thresholds, API keys
│
└── data/
    └── lancedb/                 ← persistent vector store (gitignored)
```

## 9. Build Order (3 days)

### Day 1 — Backend end-to-end (target: working curl by bedtime)
1. Scaffold `backend/` and `frontend/` folders, `.env`, git repo.
2. Get API keys: Google Gemini, Groq, NCBI/PubMed (optional but recommended for rate limits).
3. Write `pubmed_downloader.py` for 2 specialties (Diabetes + Cardiology), target 10,000 articles.
4. **Kick off download in background.**
5. While download runs: write `chunker.py` and `embedder.py`, test on 10 articles.
6. When download done: embed all chunks → populate LanceDB (~30 min).
7. Write `local_search.py` → test with 5 queries, tune threshold.
8. Write `live_search.py` → PubMed fallback.
9. Write `synthesizer.py` + `verifier.py` with the strict prompts.
10. Write `pipeline.py` orchestration.
11. Write FastAPI endpoints `/query/local` and `/query/live`.
12. **Success criterion:** `curl` both endpoints, get cited answers.

### Day 2 — UI
1. shadcn/ui setup, install components.
2. Main query screen (centered card, clinical palette).
3. Answer screen (TL;DR + Key Findings + Sources).
4. `SourceCard` component with both `url` and `doi_url` links + quoted passage + publication type badge.
5. "No verified answer" screen with 3 action buttons.
6. Live search progress component (animated stages).
7. `ConfidenceMeter` component.
8. Tier badge ("Verified KB" vs "Live multi-AI").
9. Error / empty / loading states.
10. Test 10 real queries end-to-end.

### Day 3 — Polish + deploy + demo prep
1. **One** wow feature: Evidence Level badges from `publication_type` metadata.
2. Polish pass (typography, spacing, copy, mobile).
3. Deploy frontend to Vercel.
4. Deploy backend to Railway/Render with LanceDB persistent volume.
5. Final test on prod URL.
6. **Record 2-min demo video** (backup).
7. Prepare 5 hero queries, memorize.
8. Write 1-page pitch, rehearse Q&A.

## 10. The Strict Prompts (use verbatim)

### Synthesizer prompt
```
You are a medical evidence assistant. Answer the doctor's question using ONLY the numbered sources below.

RULES:
- Cite every factual claim inline using [1], [2], etc.
- Do NOT write URLs or links — only citation numbers.
- Do NOT use your own medical knowledge. Use only what is in the sources.
- Keep the answer to 2-4 sentences.
- If the sources do not contain a clear answer, respond with exactly: INSUFFICIENT_EVIDENCE

QUESTION: {query}

SOURCES:
[1] {source_1_chunk_text}
[2] {source_2_chunk_text}
...

ANSWER:
```

### Verifier prompt
```
You are a fact-checker. A medical answer has been written based on the sources below. Determine whether every claim in the answer is directly supported by the sources.

OUTPUT JSON ONLY:
{
  "confidence": <float 0-1>,
  "unsupported_claims": [<list of sentences from the answer that are not supported by sources>]
}

ANSWER:
{synthesizer_output}

SOURCES:
[1] {source_1_chunk_text}
[2] {source_2_chunk_text}
...
```

## 11. Hero Queries For Demo (test throughout build)

1. *"What are the renal dose adjustments for metformin in CKD?"* → strong local hit, Tier 1.
2. *"Side effects of SGLT2 inhibitors in elderly patients"* → strong local hit, Tier 1.
3. *"Does empagliflozin reduce cardiovascular mortality in HFpEF?"* → local hit, shows RCT badge.
4. *"First-line treatment for drug-resistant tuberculosis 2024"* → likely miss, triggers "not found" + live multi-AI — **showstopper moment**.
5. *"Is acetaminophen safe in third trimester pregnancy?"* → may return uncertain, shows **"No reliable answer"** abstention — proves safety story.

## 12. Current Progress

### Done
- [x] Git repo initialized AND pushed to GitHub: `https://github.com/Abhishek0489/medCite.git` (remote: `origin`, branch: `main`)
- [x] First commit pushed: "Initial scaffold: spec, env template, ingestion pipeline"
- [x] `PROJECT_SPEC.md`, `README.md`, `.gitignore`, `.env.example` created
- [x] `.env` filled in by user (NOT committed — gitignored)
- [x] Backend scaffold: `backend/config.py`, folders for `ingestion/`, `retrieval/`, `agents/`
- [x] Python 3.12 installed in venv at `backend/.venv/`
- [x] Decisions locked: specialties = Diabetes + Cardiology; LLMs = Gemini 2.5 Flash (synth) + Groq Llama 3.3 70B (verifier); 10K articles target
- [x] **ChromaDB → LanceDB swap** (blocker resolved; pure-Rust wheels, no MSVC needed)
  - [x] `backend/requirements.txt` — `lancedb==0.30.2`
  - [x] `backend/config.py` — `LANCEDB_PATH`, `LANCE_TABLE_NAME`
  - [x] `.env` / `.env.example` updated
  - [x] `.gitignore` ignores `data/lancedb/`
- [x] `backend/pubmed_client.py` — shared httpx PubMed client (search/fetch/parse), reused by ingestion and live search
- [x] `backend/ingestion/pubmed_downloader.py` — refactored to use shared client
- [x] `backend/ingestion/chunker.py`
- [x] `backend/ingestion/embedder.py` — LanceDB backend, normalized vectors, cosine metric
- [x] `backend/retrieval/local_search.py` — LanceDB top-5 cosine search, returns chunks + similarity
- [x] `backend/retrieval/live_search.py` — PubMed live fallback; ranks live chunks locally; `write_articles_to_lancedb()` helper for self-improvement loop
- [x] `backend/agents/synthesizer.py` — Gemini 2.5 Flash, exact spec §10 prompt, returns `INSUFFICIENT_EVIDENCE` on abstain, tenacity retry on 429/5xx
- [x] `backend/agents/verifier.py` — Groq Llama 3.3 70B, `response_format=json_object`, robust JSON parsing, conservative defaults, tenacity retry on 429/5xx
- [x] Similarity threshold tuned from 0.80 → **0.55** based on real retrieval scores (empagliflozin/HFpEF=0.80+, metformin/CKD=0.54, TB=0.44 — 0.55 cleanly separates in/out-of-scope)
- [x] `backend/pipeline.py` — `run_local_query` / `run_live_query` orchestrator; enforces similarity ≥ 0.80 and confidence ≥ 0.75 gates; writes back to LanceDB on verified live answer
- [x] `backend/main.py` — FastAPI app with `/query/local`, `/query/live`, `/health`, CORS open, pydantic response model matches spec §6

### Install + ingestion: DONE
- [x] `pip install -r backend/requirements.txt` succeeded (Windows + Py 3.12, LanceDB wheel installed cleanly, no MSVC)
- [x] `python -m ingestion.pubmed_downloader` — 4,997 diabetes + 4,984 cardiology = **9,981 articles** in `data/raw/`
- [x] `python -m ingestion.embedder` — **17,456 chunks** in `data/lancedb/medcite_articles.lance/`
- [x] Uvicorn running at `http://localhost:8000`, `/health` returns 200

### ⚠️ ACTIVE ISSUE — Gemini returns `INSUFFICIENT_EVIDENCE` even with strong retrieval

After tuning threshold 0.80→0.55, adding tenacity retry for 429/5xx, and adding `gemini-2.5-flash-lite` fallback, the 503s are gone. But:

| # | Query | `top_similarity` | Result |
|---|---|---|---|
| 1 | metformin renal dose in CKD | 0.5414 | `not_found` (0.54 < 0.55 threshold — edge case, tolerable) |
| 2 | empagliflozin CV mortality in HFpEF | **0.8205** | `insufficient_evidence` ← **UNEXPECTED** |
| 3 | drug-resistant TB (local) | 0.4439 | `not_found` ✅ |
| 4 | drug-resistant TB (live) | 0.7864 | `insufficient_evidence` ← **UNEXPECTED** |
| 5 | drug-resistant TB (local, after 4) | 0.4439 | `not_found` (live didn't write back) |

Queries 2 & 4 reached Gemini with strong chunks but the synthesizer returned/produced nothing. Three hypotheses (in descending likelihood):
1. **Gemini 2.5 Flash safety filter** is blocking medical-advice responses → `response.text` comes back empty → our `if not text: return INSUFFICIENT` fires.
2. **Over-cautious prompt.** With strict RULES forbidding outside knowledge, Gemini 2.5 defaults to outputting `INSUFFICIENT_EVIDENCE` literally.
3. Chunks genuinely don't contain the answer (unlikely — DELIVER/EMPEROR trials are indexed).

Diagnostic logging has been added to `synthesizer.py` (logs `finish_reason`, `safety_ratings`, and `text_preview`). **Next chat's first action: restart uvicorn, rerun test 2, read the log line to confirm which hypothesis is true.**

Likely fixes (pick after diagnosis):
- If safety block: configure `safety_settings=BLOCK_NONE` in `GenerateContentConfig` (safe in a medical-lit context, not user-generated content).
- If literal INSUFFICIENT: soften the prompt slightly — allow "You MAY infer clinical implications directly supported by the sources" — or set `thinking_config` / `temperature` higher.
- Last resort: switch primary synthesizer to `gemini-2.0-flash-lite` (still free tier) or a different Groq model; spec §3 rule 3 requires synth ≠ verifier vendor so can't put it on Groq.

### Tuning done this session
- Similarity threshold: 0.80 → **0.55** (data-driven; see gap between 0.44 out-of-scope vs 0.54+ in-scope)
- Synthesizer: `gemini-2.0-flash` → **`gemini-2.5-flash`** (Google removed 2.0 Flash from free tier Q4 2025)
- Added tenacity retry (4 attempts, exp backoff) for 429/5xx to both synthesizer + verifier
- Added `SYNTHESIZER_FALLBACK_MODEL=gemini-2.5-flash-lite` — kicks in if primary is persistently overloaded
- `load_dotenv(override=True)` so `.env` edits propagate on reload
- Fixed LanceDB 0.30.2 API (`list_tables()` returns a pagination object now — switched to try/open_table)

### Not started
- [ ] Fix Gemini INSUFFICIENT_EVIDENCE issue (next chat, first task)
- [ ] Curl tests pass end-to-end with real cited answers
- [ ] Second commit after endpoints verified
- [ ] **Day 2:** Next.js + shadcn/ui frontend
- [ ] **Day 3:** Deploy (Vercel + Railway) + demo prep

### Key env vars user has set (already in `.env`)
- `GOOGLE_API_KEY` (Gemini)
- `GROQ_API_KEY`
- `NCBI_API_KEY` + `NCBI_EMAIL`

---

## Resume Prompt (paste this if Cursor context fills up)

```
I am building "MedCite" — a medical Q&A web app for the Jubilant Pharma hackathon.

READ FIRST: The full spec is in PROJECT_SPEC.md at the repo root. Read that file completely before doing anything else. Do not deviate from the design principles in section 3.

ONE-LINE SUMMARY: Doctor types a medical question → system searches a local LanceDB of ~10,000 pre-embedded PubMed abstracts (Diabetes + Cardiology) → if good match (similarity >= 0.80), Gemini 2.0 Flash synthesizes a cited answer and Groq Llama 3.3 70B verifies it → if no local match, doctor clicks a button to trigger live PubMed API + same multi-LLM pipeline → every answer has clickable PubMed URLs built from PMIDs (never generated by LLM) → confidence < 0.75 means abstain with "No reliable answer found".

TECH: Next.js + Tailwind + shadcn/ui frontend; FastAPI + LanceDB + sentence-transformers backend; Google Gemini 2.5 Flash as synthesizer; Groq Llama 3.3 70B as verifier; PubMed E-utilities for article source.

HARD RULES (do not violate):
1. LLMs never write URLs — only [1][2] citation numbers; backend stitches URLs from metadata
2. Synthesizer prompt forbids using prior knowledge; must answer from chunks only or say INSUFFICIENT_EVIDENCE
3. Verifier must be a different vendor model from Synthesizer
4. Confidence < 0.75 → abstain
5. Live search only runs when user clicks button (not automatic)
6. Every source card shows quoted passage + clickable PubMed URL + DOI URL
7. UI is a clinical tool (one question, one answer card) — NOT a chatbot

CURRENT STATE: [update this line yourself — e.g., "Day 1 complete, curl tests passing. Starting Day 2 UI now."]

NEXT STEP: [what you were about to do]

Continue from where the previous session left off. Reference PROJECT_SPEC.md for anything you're unsure about.
```
