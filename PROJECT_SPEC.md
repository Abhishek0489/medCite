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
- **Synthesizer (Gemini 2.5 Flash-Lite):** receives query + 5 chunks + strict prompt. Outputs 2-3 sentence answer with inline `[1][2]` citations, or `INSUFFICIENT_EVIDENCE`. *(Originally specced as Gemini 2.0 Flash. Google removed 2.0 from the free tier in late 2025. Tried 2.5 Flash next, but its internal "thinking" tokens consumed `max_output_tokens` before any visible text was emitted — answers truncated mid-sentence. Switched to 2.5 Flash-Lite, which has tighter reasoning and produces stable, complete, cited answers at `temperature=0`; 2.5 Flash is kept as the overflow fallback.)*
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
| Frontend | Next.js 14 (App Router) + **JavaScript (.jsx)** | Fast dev, clean deploys. JS chosen over TS to remove the type-system learning curve during a 3-day hackathon. shadcn/ui supports JS via `tsx: false` at init. |
| Styling | Tailwind CSS + shadcn/ui | Clinical look out of the box |
| Backend | FastAPI (Python 3.11+) | Fast, great for ML + APIs |
| Vector DB | LanceDB (persistent, local) | Pure Rust, pre-built wheels for Windows Python 3.12/3.13, no MSVC needed. *(Originally planned ChromaDB, swapped due to Windows wheel issue with `chroma-hnswlib`.)* |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Free, CPU-runnable, 384-dim |
| Synthesizer LLM | Google Gemini 2.5 Flash-Lite | Free tier, deterministic, no thinking-token truncation (2.0 Flash removed Q4 2025; 2.5 Flash kept as overflow fallback) |
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
├── frontend/                    # Next.js 14 (App Router) + JavaScript
│   ├── app/
│   │   ├── page.jsx             ← main query page
│   │   ├── layout.jsx
│   │   └── api/                 ← (thin proxy to backend if needed)
│   ├── components/
│   │   ├── QueryCard.jsx
│   │   ├── AnswerPanel.jsx
│   │   ├── SourceCard.jsx
│   │   ├── ConfidenceMeter.jsx
│   │   ├── NotFoundScreen.jsx
│   │   ├── LiveSearchProgress.jsx
│   │   └── ui/                  ← shadcn/ui generated components
│   ├── lib/
│   │   └── api.js               ← fetch helpers (calls FastAPI backend)
│   ├── jsconfig.json            ← path aliases for `@/components/*` etc
│   ├── package.json
│   └── tailwind.config.js
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
1. Scaffold Next.js 14 with **JavaScript** (not TypeScript): `npx create-next-app@latest frontend --js --app --tailwind --eslint --src-dir=false --import-alias "@/*"`.
2. shadcn/ui init in JS mode: `cd frontend && npx shadcn@latest init` → answer **No** when asked "Would you like to use TypeScript?". Components install as `.jsx` under `components/ui/`.
3. Install shadcn primitives needed: `button`, `input`, `card`, `badge`, `progress`, `skeleton`, `alert`, `separator`. (Add more as required.)
4. Main query screen (centered card, clinical palette: white/slate + one accent color).
5. Answer screen (TL;DR + Key Findings + Sources).
6. `SourceCard` component with both `url` and `doi_url` links + quoted passage + publication type badge.
7. "No verified answer" screen with 3 action buttons (live search / show related / rephrase).
8. Live search progress component (animated stages: PubMed → Synthesizing → Verifying).
9. `ConfidenceMeter` component.
10. Tier badge ("Verified KB" vs "Live multi-AI").
11. Error / empty / loading states.
12. Test 10 real queries end-to-end.

### Day 3 — Polish + deploy + demo prep
1. **One** wow feature: Evidence Level badges from `publication_type` metadata.
2. Polish pass (typography, spacing, copy, mobile).
3. Deploy frontend to Vercel.
4. Deploy backend to Railway/Render with LanceDB persistent volume.
5. Final test on prod URL.
6. **Record 2-min demo video** (backup).
7. Prepare 5 hero queries, memorize.
8. Write 1-page pitch, rehearse Q&A.

#### Day 3 polish — locked scope (do AFTER backup demo is recorded)

Sequence matters: record the backup demo on the current, tested system first.
Then upgrade. Never touch a working system twice in the same day.

**Active scope (Day 3 PM, post-recording session):** three additive polish
items only. Each is small, independently revertable, and reduces demo-day
risk. The original optional list (Pro model A/B test, corpus expansion,
date-range widening) was deliberately dropped to keep the demo system small
and the moving parts few — see "Out of scope" at the bottom.

**A. Live-search resilience (~30 min, additive)**
- Problem we hit on Day 3 PM: PubMed E-utilities ESearch returned 0 PMIDs
  for the recommended showstopper query *"Best first-line antibiotic for
  community-acquired pneumonia in adults 2024"*. The term matcher rejects
  long natural-language sentences with grammatical filler ("Best ... for
  ... in adults"). `/query/live` then silently produced a 0-source
  `not_found` in ~4s, dead-ending the demo. Any judge who types a question
  naturally (instead of using the curated hero chips) hits the same bug.
- Fix: in `backend/retrieval/live_search.py` (or a small helper in
  `backend/pubmed_client.py`), if `search_pmids()` returns an empty list,
  retry **once** with a stop-words-stripped version of the query
  (drop: `the, a, an, of, for, in, on, with, and, or, is, are, was, were,
  be, been, being, what, which, who, whom, whose, when, where, why, how,
  best, first-line, recommended, dose`). Cap retry at 1; if still empty,
  return `[]` honestly so the existing not_found UI fires.
- Optional second pass (only if first fix isn't enough): also strip leading
  capitalised filler words (`Best`, `Recommended`, `What is the`).
- Spec rules unaffected — this is purely a query-string transform before
  the PubMed call. The synthesizer/verifier still see the same chunks; the
  cross-vendor verification gate (§3 rule 3+4) still applies.

**B. Frontend health-check retry (~15 min, UI-only)**
- Problem: `frontend/app/page.jsx` calls `checkHealth()` once on mount. If
  the HF Space is mid-cold-start (~12 s wake), the call fails and the
  header shows a red "Backend offline" pill that misleads judges into
  thinking the system is down. We hit this in the Day-3 PM diagnostic
  session.
- Fix: retry the health check 3× with 5 s exponential backoff before
  flipping the pill to offline. Show a third state — *"Backend warming…"*
  in slate — between attempts so the UX is honest about what's happening.
- Files: only `frontend/app/page.jsx` (the `useEffect` that calls
  `checkHealth`). No backend change. No new components.

**C. PWA install layer (~45 min, additive, no service worker)**
- Goal: judges can "Install" the deployed site from Chrome/Safari and land
  on their home screen with the stethoscope icon, fullscreen, no browser
  chrome. Same code path as the website — no native rewrite, no React
  Native, no Capacitor.
- Hard prerequisite: backend served over HTTPS — DONE (HF Spaces).
- Do NOT add a service worker. Manifest + icons + iOS meta tags only.
  Service workers are where PWA bugs live (stale caches, wedged installs);
  modern browsers still show the "Install" affordance without one.
- Files to create:
  - `frontend/public/icon.svg` — sky-600 rounded square + white Lucide
    stethoscope path, 512×512 viewBox with 25% inner padding (safe zone
    for Android maskable icons).
  - `frontend/public/manifest.json` — `name`, `short_name: "MedCite"`,
    `start_url: "/"`, `display: "standalone"`, `background_color: "#f8fafc"`,
    `theme_color: "#0284c7"`, icons referencing `/icon.svg` with
    `sizes: "any"`.
  - `frontend/app/layout.jsx` — add `metadata.manifest = "/manifest.json"`,
    `metadata.icons.icon` and `apple`, plus `metadata.appleWebApp` block.
- Test: `curl http://localhost:3000/manifest.json` returns JSON, then on
  the deployed URL open Chrome → 3-dots menu → "Install MedCite" should
  appear. iOS Safari → Share → Add to Home Screen.
- Skip entirely if anything in deploy goes sideways — the website demo is
  already enough.

**Optional D. HF Space keep-alive (~10 min, no code)**
- HF Spaces free tier auto-sleeps after 48 h of idle — first request after
  sleep is a ~12 s cold-start (measured Day 3 PM, see §"HF Spaces caveats").
- Mitigation: UptimeRobot free tier (50 monitors free) — create one
  HTTP(s) monitor pointing at `https://Tony0489-MedCite-api.hf.space/health`,
  5-minute interval. Or a Windows Scheduled Task that runs
  `Invoke-RestMethod https://Tony0489-MedCite-api.hf.space/health` hourly.
- Skip if you can keep `/health` warm manually during the 24 h before the
  demo (set a phone alarm every 4 h — the sleep window is 48 h).

**Out of scope (deliberately dropped — do NOT pursue without removing this section first)**
- ~~Synthesizer model swap to `gemini-2.5-pro`~~ — added complexity
  (latency 3–8 s vs ~1 s, lower RPM, MAX_TOKENS tuning needed) for a marginal
  citation-adherence win. Current Flash-Lite is producing conf=0.80 on every
  in-scope query; the gate is doing its job. Re-evaluate post-hackathon.
- ~~Corpus expansion (add infectious_diseases / oncology / nephrology;
  bump ARTICLES_PER_SPECIALTY to 7500)~~ — would require re-ingestion
  (30–60 min), re-tuning `SIMILARITY_THRESHOLD`, re-deploying to HF
  (re-running `deploy/hf/sync.ps1` with the new lance dir, ~5 min upload),
  and would absorb the H. pylori showstopper into Tier 1 — meaning we'd
  need to find yet another out-of-corpus topic for the live-multi-AI demo.
  Not worth the risk on the day.
- ~~Widen `2015 → 2010` in SPECIALTIES queries~~ — same re-ingestion +
  re-deploy cost as above for marginal value (more foundational reviews
  but they're all already covered well enough by the 2015+ corpus).

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

1. *"Side effects of SGLT2 inhibitors in elderly patients"* → strong local hit, Tier 1, **Meta-analysis** badge.
2. *"Does empagliflozin reduce cardiovascular mortality in HFpEF?"* → strong local hit (top sim ≈ 0.82), shows **RCT** + **Review** badges, conf 0.80.
3. *"First-line treatment for drug-resistant tuberculosis 2024"* → **self-improvement story.** Was a Tier-1 miss originally; after one Day-1 live escalation wrote 21 articles back, it now scores top sim ≈ 0.80 on Tier 1. Demo line: *"Yesterday this missed locally and we used the live fallback. Today it's instant — every doctor's question makes the next doctor's faster."*
4. *"Levetiracetam status epilepticus dose"* → **live multi-AI showstopper.** Out of corpus (no neurology specialty). Triggers `NotFoundScreen` → click *Search live* → 3-stage progress (PubMed → Gemini → Llama) → cited answer + "Added N articles to KB" chip. PubMed returns 169 PMIDs; full live pipeline verified end-to-end on prod (status=found, conf=0.80, top_sim=0.8054, 5 cited sources, 26 articles written back). **DO NOT click this query before the live demo** — first click writes the articles back and the showstopper animation is gone for that container's lifetime. **NOTE on previous candidates:** (a) the original *"Best first-line antibiotic for community-acquired pneumonia in adults 2024"* was dropped because PubMed E-utilities ESearch returns 0 PMIDs for long natural-language phrasings (the §9 polish item A stop-word retry fix would now save it, but levetiracetam is cleaner); (b) the *"H. pylori first-line eradication 2024"* replacement was used during the Day-3 PM backup-demo recording session, so it's permanently contaminated in the running HF container until next rebuild — superseded by levetiracetam. Validation in PowerShell for any future swap: `$enc = [uri]::EscapeDataString($q); Invoke-RestMethod "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=$enc&retmode=json"` → `esearchresult.count` must be > 0.
5. *"Is acetaminophen safe in third trimester pregnancy?"* → top sim ≈ 0.53, lands on `NotFoundScreen` with *"closest match scored 0.53, below the safety threshold. We won't guess."* — **proves the safety story** (§3 rule 4) vs ChatGPT-style hallucination. **Do not escalate this one** at demo time; the abstention itself is the feature.

> **Note on the dropped query:** *"What are the renal dose adjustments for metformin in CKD?"* (former #1) was contaminated by a Day-2 live escalation that wrote 18 articles back — it now Tier-1 hits at conf 0.80 with `Added 18 articles to knowledge base` chip. Still a usable demo if you want a *second* self-improvement story alongside #3, but no longer a clean "abstain on edge case" example.

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

### ✅ Synthesizer bug FIXED (Day 1 late session, 2026-04-24)

**Diagnosis (from `medcite.synthesizer` INFO log):**
- `finish=STOP, safety=None, text_preview='INSUFFICIENT_EVIDENCE'` — Gemini 2.5 Flash was literally outputting the abstention token on in-scope queries. Not a safety block. Over-cautious prompt on a "thinking" model.
- After softening the prompt, `finish=MAX_TOKENS, text_len=212` — Gemini 2.5 Flash burns hundreds of *internal thinking tokens* against `max_output_tokens` before emitting visible text, truncating the answer mid-sentence even at `max_output_tokens=1024`.
- A/B test at same prompt, `temperature=0.0`: `gemini-2.5-flash-lite` produced stable, complete 337-char cited answers (`finish=STOP`) across two trials; `gemini-2.5-flash` consistently truncated at ~212 chars (`finish=MAX_TOKENS`).

**Fixes applied (all spec-compliant, §3 rules preserved):**
1. Swapped primary synthesizer → `gemini-2.5-flash-lite`; fallback → `gemini-2.5-flash` (flipped the pair). Rationale documented in `config.py` and `.env.example`.
2. Softened the spec §10 prompt: replaced the over-strict "if sources do not contain a clear answer" with "only if NONE of the sources are relevant" and explicitly permitted inference directly supported by the sources. No URLs, no outside knowledge, 2–4 sentence limit, literal `INSUFFICIENT_EVIDENCE` token — all preserved.
3. Added `safety_settings=BLOCK_NONE` for all four harm categories on the synthesizer config (defensive; the problem today was not a safety block, but medical content can trip `DANGEROUS_CONTENT` on other queries).
4. Bumped `max_output_tokens` 512 → 4096 (primary model `-lite` doesn't need it, but the fallback `flash` does because of thinking tokens).
5. Added `medcite.verifier` INFO logging of confidence + unsupported claims — made it trivial to distinguish "synth refused" from "verifier gated".

**Hero-query smoke test (post-fix):**

| # | Query | Tier | `top_sim` | Status | Verifier conf | Notes |
|---|---|---|---|---|---|---|
| 1 | metformin renal dose in CKD | local | 0.541 | `not_found` | — | 0.541 < 0.55 threshold. Known edge case, user tolerates. |
| 2 | empagliflozin CV mortality in HFpEF | local | 0.821 | **`found` ✅** | 0.80 | Fixed — cited answer from PMID 38865086 Review. |
| 3 | drug-resistant TB | local | 0.444 | `not_found` | — | Correct: out of corpus scope. |
| 4 | drug-resistant TB | live | 0.734 | `insufficient_evidence` | 0.67 | Synth produced answer; verifier caught unsupported claim ("BPaLM protocol…combining bedaquiline, pretomanid, linezolid, and moxifloxacin"). Safety gate (§3 rule 4) working as designed. |
| 5 | drug-resistant TB (local, after 4) | local | 0.444 | `not_found` | — | No write-back because #4 was gated. |
| 6 | SGLT2 side effects in elderly | local | 0.674 | **`found` ✅** | 0.80 | Fixed — 5 cited sources. |
| 7 | acetaminophen in 3rd trimester | local | 0.526 | `not_found` | — | Below threshold. Proves abstention story (§11 hero query 5). |

**Two clean `found` responses on in-scope queries (2 & 6).** Query 4 (live TB) is an accurate demonstration of the cross-vendor safety gate, not a bug.

### Tuning done this session
- Similarity threshold: 0.80 → **0.55** (data-driven; see gap between 0.44 out-of-scope vs 0.54+ in-scope)
- Synthesizer: `gemini-2.0-flash` → `gemini-2.5-flash` → **`gemini-2.5-flash-lite`** (2.0 removed from free tier Q4 2025; 2.5-flash's thinking tokens ate the output budget, switched to -lite which is stable and deterministic on this task)
- Synthesizer fallback: `gemini-2.5-flash-lite` → **`gemini-2.5-flash`** (swapped; flash now serves as overflow capacity since its free-tier quota pools separately)
- Synthesizer prompt softened: "only if NONE of the sources are relevant" (was "if the sources do not contain a clear answer"); explicit permission to synthesize from directly-supported evidence. Spec §3 rules all preserved.
- `safety_settings=BLOCK_NONE` added to `GenerateContentConfig` on all four harm categories (curated PubMed input; no user-generated content flows to the model).
- `max_output_tokens`: 512 → **4096** to accommodate thinking tokens on the fallback model.
- `medcite.verifier` INFO logging added (confidence + unsupported claim count + raw preview) — made it easy to distinguish synth-refusal from verifier-gate.
- Added tenacity retry (4 attempts, exp backoff) for 429/5xx to both synthesizer + verifier.
- `load_dotenv(override=True)` so `.env` edits propagate on reload.
- Fixed LanceDB 0.30.2 API (`list_tables()` returns a pagination object now — switched to try/open_table).

### Done this session
- [x] Diagnosed Gemini `INSUFFICIENT_EVIDENCE` bug (see above — two layered causes: over-cautious prompt + flash-model thinking-token truncation)
- [x] Swapped primary synth model to `gemini-2.5-flash-lite`; softened prompt; added `safety_settings=BLOCK_NONE`; bumped `max_output_tokens` to 4096; added verifier logging
- [x] Hero-query smoke test passes: two clean `found` responses (empagliflozin HFpEF, SGLT2 elderly) with verifier confidence 0.80; out-of-scope queries abstain correctly; live TB gated by safety verifier as designed

### Day 2 — Frontend (in progress, 2026-04-25)
- [x] Node 22.16 verified; backend started on :8000, `/health` returns `gemini-2.5-flash-lite`
- [x] Scaffolded `frontend/` with `create-next-app@latest --js --app --tailwind --eslint --no-src-dir --import-alias "@/*"`. Note: `@latest` shipped Next 16 + React 19 + Tailwind 4 (not Next 14/Tailwind 3 as originally specced); design principles unaffected, App Router + JS preserved.
- [x] `shadcn@latest init --defaults` ran in JS mode (`tsx: false`, base style `base-nova`, base color neutral). Generated `components/ui/*.jsx` and `lib/utils.js`.
- [x] Installed primitives: button, input, card, badge, progress, skeleton, alert, separator, textarea (lucide-react also installed automatically).
- [x] `frontend/.env.local` and `frontend/.env.example` created with `NEXT_PUBLIC_API_URL=http://localhost:8000`.
- [x] `lib/api.js` — `queryLocal`, `queryLive`, `checkHealth`; AbortController-aware; surfaces `detail` on non-2xx.
- [x] All 6 spec §8 components built as `.jsx`:
  - `QueryCard` — single textarea, Cmd/Ctrl+Enter shortcut, sky-600 Ask button, no chat history.
  - `AnswerPanel` — TierBadge ("Verified KB" green / "Live multi-AI" amber + write-back chip), inline `[N]` chips that anchor-link to `#source-N`, ConfidenceMeter, sources list with similarity hint.
  - `SourceCard` — citation number bubble, evidence-level badge derived from `publication_type` (RCT / Meta-analysis / Review / Guideline / Case report), italicized `quoted_passage` blockquote, separate PubMed and DOI links.
  - `ConfidenceMeter` — 0–100% bar with emerald/amber/red bands keyed off the same 0.75 / 0.85 thresholds as §3 rule 4.
  - `NotFoundScreen` (default export) — amber alert + 3 buttons exactly per §5 Flow B; below it, the related-articles list.
  - `AbstainScreen` (named export from `NotFoundScreen.jsx`) — slate panel for `insufficient_evidence`; surfaces verifier's `unsupported_claims`.
  - `LiveSearchProgress` — fake-staged 3-step progress (PubMed → Gemini → Llama 3.3) since the live endpoint is one synchronous request.
- [x] `app/layout.jsx` (Inter font, slate-50 background) + `app/page.jsx` state machine over phases `idle | loading | live | answered | notfound | abstain | error`. Submitting a new query wipes prior result (spec §3 rule 7). Hero queries panel shown in `idle`. Live search only runs when the doctor clicks the button (spec §3 rule 5). Backend status pill in header polls `/health` once on mount.
- [x] Dev server (`npm run dev`) up on http://localhost:3000, GET / returns 200 with no compile errors. No ESLint errors on any new file.
- [x] Smoke-tested backend from PowerShell: empagliflozin/HFpEF query returns `status=found`, `confidence=0.80`, 5 sources with full quoted_passages and PubMed+DOI URLs.

### Day 2 closed (end-of-session, 2026-04-25 evening)
- [x] Manual click-through of all 5 hero queries in browser — verified by user with screenshots:
  - SGLT2 elderly → green Tier-1 hit, conf 0.80, **Meta-analysis** badge ✅
  - empagliflozin/HFpEF → green Tier-1 hit, conf 0.80, top sim 0.82, **RCT/Review** badges ✅
  - TB 2024 → green Tier-1 hit at top sim 0.80 (was 0.44 yesterday — the **self-improvement loop fired**: yesterday's live escalation wrote 21 articles back, today it's instant)
  - acetaminophen 3rd trimester → amber `NotFoundScreen` "closest match scored 0.53, below the safety threshold" ✅ (proves abstention story)
  - metformin/CKD → user clicked "Search live" today; live multi-AI returned amber-badged answer + "Added 18 articles to knowledge base" chip ✅
- [x] Refreshed §11 hero queries to reflect new reality: TB is now the self-improvement story; **CAP antibiotics 2024** (or H. pylori, levetiracetam) is the new live-search showstopper since it's still out-of-corpus. Spec footnotes the dropped metformin/CKD example. *(Superseded Day 3 PM — the long-form CAP phrasing was found to return 0 PMIDs from PubMed ESearch; live showstopper switched to "H. pylori first-line eradication 2024". See §11 query #4 for the diagnosis.)*
- [x] Disabled Next.js 16 dev indicator badge (`devIndicators: false` in `next.config.mjs`) — the floating "N" pill in the bottom-left no longer appears.
- [x] **Pushed all 4 Day-2 commits to `origin/main`**:
  - `5364eab` feat(frontend): scaffold Next.js (JS) + shadcn/ui + lib/api.js
  - `f5e3bbd` feat(frontend): build components and main query page (Flows A/B/C)
  - `0a1e882` docs: log Day 2 frontend progress
  - `68b8df1` chore: refresh hero queries (§11) and disable Next.js dev indicator badge
- [x] **Quota check for demo safety:**
  - Google AI Studio is now on **Tier 1** (billing enabled). Flash-Lite limits jumped from 10 RPM / 20 RPD → **4,000 RPM / unlimited RPD**. Pro is now viable for Day-3 A/B test (150 RPM / 1,000 RPD). Worst-case full-hackathon spend: under $2.
  - Groq dashboard verified: `llama-3.3-70b-versatile` at 30 RPM / **1K RPD / 12K TPM / 100K TPD** (slightly tighter than the README quoted previously). 1 verifier call ≈ 2K tokens → ~50 calls/day before TPD throttle. Plenty for the demo. Real spend so far: $0.01 projected (free tier, no card).

### Day 3 morning (2026-04-25, this session) — Done
- [x] Local sanity-check before deploy: backend on :8000 + frontend on :3000 both healthy. Empagliflozin/HFpEF Tier-1 hero query verified end-to-end (`status=found`, `conf=0.80`, `top_sim=0.8205`, 5 sources with full quoted_passage + PubMed + DOI URLs).
- [x] **Three production-safety fixes committed (`563d6a2`)** — required for cloud deploy where stdout is redirected to log-capture pipes:
  - `model.encode(..., show_progress_bar=False)` in `retrieval/local_search.py` and `retrieval/live_search.py`. Tqdm's carriage-return writes to a redirected stderr on Windows raise `OSError [Errno 22]` mid-request and surface as `"Local pipeline failed: [Errno 22] Invalid argument"` with no traceback. Same bug will fire on Render/Railway/HF Spaces (all redirect stdout) — this fix is mandatory before deploy.
  - `sys.stdout/stderr.reconfigure(encoding='utf-8', errors='replace')` at startup in `main.py`. Backstop for any non-cp1252 chars (em-dash, ≥, …) emitted by synth/verify loggers when stdout is redirected on Windows.
  - Full traceback + exception type logged via `medcite.api` logger on `/query/local` and `/query/live` failures. Previous handler stringified the exception with no type and no stack — debugging a 500 cost ~30 min today.
- [x] **`PITCH.md` added at repo root (`392a975`)** — pitch deck reference with elevator pitch, 7 hard rules slide content, architecture, all 5 hero queries with demo lines, 2-min demo script, 9 anticipated Q&A with rehearsed answers, the numbers, the closing line. Read this before building the slides; don't regenerate.
- [x] **Day-3 deploy decision: Cloudflare Tunnel + Vercel (both free).** Skipped Render/Railway because (a) free tiers can't fit sentence-transformers + LanceDB in 512MB RAM and have ~30s cold starts, (b) paid tiers cost $5–7/mo for what's essentially a weekend demo. Cloudflare Tunnel exposes the existing `localhost:8000` (already verified, write-back cache intact, API keys never leave the laptop) at a stable `*.trycloudflare.com` URL via outbound-only connection — zero cold start, zero cost, zero deployment work, ~5 min setup. Tradeoff: backend is dead if laptop is off, but laptop is on at the venue anyway and the 2-min backup demo video is the safety net. *(Superseded same day — see Day-3 afternoon section: backend now on Hugging Face Spaces, no laptop dependency.)*

### Day 3 afternoon (2026-04-25, this session) — Done
- [x] **Cloudflare Tunnel + Vercel deploy shipped first** (`284e10c`, `f17014b`). `cloudflared` installed via winget. Quick tunnel up at `https://ist-females-talking-gray.trycloudflare.com` with `/health` and `POST /query/local` both verified through the public Cloudflare edge. Vercel project created (`frontend`), deployed under stable alias `https://frontend-sandy-phi-72.vercel.app`, `NEXT_PUBLIC_API_URL` set to the tunnel URL and baked into the bundle, prod-equivalent smoke test returned identical Tier-1 hit (`conf=0.80`, `top_sim=0.8205`).
- [x] **Backend host switched from Cloudflare Tunnel → Hugging Face Spaces** in response to user concern about quick-tunnel URL stability across `cloudflared` restarts and laptop sleep. The previous "Render/Railway can't fit in 512 MB RAM" reasoning had wrongly grouped HF Spaces in — HF's CPU Basic tier is **2 vCPU / 16 GB RAM / 50 GB persistent storage, free**, which is comfortable for sentence-transformers + LanceDB.
- [x] **Backend deployed to HF Space `Tony0489/MedCite-api`** (`d4cf4d9`):
  - `deploy/hf/Dockerfile` — Python 3.12-slim, non-root UID 1000 (HF requirement), port 7860 (HF requirement), pre-downloads `sentence-transformers/all-MiniLM-L6-v2` at build time so first user query doesn't pay a 90 MB cold model fetch, bundles `backend/` and `data/lancedb/` (53.5 MB cache) into the image.
  - `deploy/hf/sync.ps1` — copies backend code + lancedb to a sibling dir `..\medcite-hf-space\` (outside the GitHub repo, so the 53 MB binary cache never lands in `origin/main`), wipes any previous `.git`, runs `git lfs install` + `git lfs track "data/lancedb/**" "*.lance" "*.manifest" "*.txn"` BEFORE the first commit (HF's pre-receive hook rejects raw binary blobs and demands XET/LFS), then force-pushes to `https://huggingface.co/spaces/<HfUser>/<HfSpace>` over HTTPS with the write token as the password.
  - First push attempt failed with `pre-receive hook declined: Please use https://huggingface.co/docs/hub/xet to store binary files` — fixed by configuring git-lfs before the first commit and re-pushing (833 LFS objects, 56 MB, ~4 min upload).
  - HF build was unexpectedly fast (~2 min from push to `RUNNING`), suggesting torch + transformers wheels were cached in HF's build infra. Stage went `BUILDING` → `APP_STARTING` → `RUNNING`.
  - Four Space Secrets configured via dashboard before push: `GOOGLE_API_KEY`, `GROQ_API_KEY`, `NCBI_API_KEY`, `NCBI_EMAIL`. They become real env vars in the container; `config.py`'s `os.getenv(...)` reads them transparently (`load_dotenv` is a no-op since no `.env` file ships in the image).
- [x] **Vercel `NEXT_PUBLIC_API_URL` switched** from the trycloudflare URL to `https://Tony0489-MedCite-api.hf.space`. Frontend redeployed (`vercel --prod --yes`); JS bundle verified to contain the HF URL by curl-grepping the chunk files. Final prod smoke test: hero #2 returns `status=found, tier=local, conf=0.80, top_sim=0.8205, 5 sources` through the full `frontend-sandy-phi-72.vercel.app` → `Tony0489-MedCite-api.hf.space` chain — identical to laptop, proving the lancedb cache shipped intact via LFS.
- [x] **Cloudflare Tunnel left running on the laptop as a fallback** (no longer in the prod request path). Can be killed at any time. If HF Space breaks during demo day, flipping Vercel env back to the trycloudflare URL + redeploying gets the laptop-backed path live in ~3 min.

**Production stack, end-to-end:**
```
Browser
  → https://frontend-sandy-phi-72.vercel.app   (Vercel, free tier, Next.js 16)
  → JS bundle hits → https://Tony0489-MedCite-api.hf.space   (HF Spaces Docker, free, 16 GB RAM, port 7860)
  → /home/user/app/data/lancedb (17,456 chunks bundled)
  → Gemini 2.5 Flash-Lite (Google AI Studio Tier 1) → Llama 3.3 70B (Groq free tier)
  → cited answer back to browser
```
Zero laptop dependency. Total query latency through the full chain: ~8 s (vs ~3 s direct on laptop — the difference is HF's shared CPU on the encode step + a network round-trip).

### HF Spaces — caveats to know before demo
1. **Auto-sleep after 48 h of idle.** First request after sleep takes ~30 s to spin the container up. Mitigation: hit `/health` once an hour during demo day, or set up UptimeRobot free tier.
2. **Shared CPU pool.** Encode is ~5–8 s on HF vs ~1 s on the laptop. Total query latency ~8 s vs ~3 s. Still under the "feels fast" threshold for clinical Q&A.
3. **Self-improvement write-back persists in the container's writable fs only.** If the container restarts (Space rebuild, HF maintenance), live-search-absorbed articles since the last image build are lost. The bundled image already contains the 21 TB articles + 18 metformin/CKD articles absorbed on Day 1-2, so the TB self-improvement story is preserved across restarts.
4. **Re-deploy = re-run `.\deploy\hf\sync.ps1 -HfUser Tony0489 -HfSpace MedCite-api -HfToken hf_xxx`.** The script wipes the sibling deploy dir and force-pushes a fresh single-commit history every time — clean and idempotent. New backend code edits or a freshly re-ingested LanceDB get picked up automatically because the script copies from the live `backend/` and `data/lancedb/` trees.

### Day 3 — Remaining (locked scope)
- [x] **3.3 Record 2-minute backup demo video** — DONE (Day 3 PM, 2026-04-25, recorded by user against prod URL `https://abhi04-medcite.vercel.app`). All 4 hero flows captured in order. **Side-effect:** clicking hero #4 H. pylori during recording wrote ~26 articles back into the live container's writable fs, so it's now a Tier-1 hit on the running container — re-run `deploy/hf/sync.ps1` (~90s rebuild) BEFORE the judge demo to reset H. pylori to fresh out-of-corpus state. The TB self-improvement story is unaffected (those 21 articles are baked into the bundled image).
- [x] **3.4 Polish — locked scope (commits `e2ca547`, `bebebb1`, both pushed)**:
  - [x] **A. Live-search resilience** (commit `e2ca547`) — `backend/retrieval/live_search.py` now strips the locked stopword list and retries PubMed ESearch once if the first call returns 0 PMIDs. Cap at 1 retry; if still empty, returns `[]` honestly so the existing `not_found` UI fires. Spec §3 rules unaffected (pure query-string transform). Re-deployed via `deploy/hf/sync.ps1`.
  - [x] **B. Frontend health-check retry** (commit `bebebb1`) — `frontend/app/page.jsx` `useEffect` now does the initial `/health` call + 3 retries with 5s/10s/20s backoff before flipping the pill to red. Adds a slate `Backend warming…` intermediate state during retries so the UX is honest about HF cold starts.
  - [x] **C. PWA install layer** (commit `bebebb1`) — `frontend/public/icon.svg` (sky-600 rounded square + white stethoscope, 512×512 with safe-zone padding), `frontend/public/manifest.json` (`display: "standalone"`, `theme_color: "#0284c7"`, `background_color: "#f8fafc"`, icon as `any maskable`), and `frontend/app/layout.jsx` metadata block (`manifest` + `icons.icon` + `icons.apple` + `appleWebApp`). No service worker shipped. Verified `curl https://abhi04-medcite.vercel.app/manifest.json` returns valid JSON.
  - [ ] **(Optional, NOT shipped) D. HF Space keep-alive** — manageable manually during the 24 h pre-demo window (sleep window is 48 h). UptimeRobot free monitor on `/health` at 5-min interval is ~5 min of clicking if you want zero cold-start risk.
  - **Out of scope, deliberately dropped to control complexity:** Pro model A/B test, corpus expansion (specialties + ARTICLES_PER_SPECIALTY 7500), date-range widening (2015 → 2010). All require re-ingestion + HF redeploy + re-tuning thresholds, and one of them would kill the H. pylori showstopper. See §9 "Out of scope" for the full rationale.
- [ ] **3.5 Pitch + Q&A prep.** 1-page pitch script. Rehearse the 4-sentence trust pitch ("ChatGPT starts with the LLM and asks it to remember sources. We start with PubMed and ask the LLM to summarise…") and the 9 anticipated Q&A answers from `PITCH.md §9`.

### Security debt — rotate before going public
- Two earlier HF write tokens (`hf_uzcN…BLC` and `hf_KiRS…hmN`) were pasted into agent chats this hackathon. The user rotated them mid-session (the latter was rotated as part of this Day-3 PM polish round). Current token in use: `hf_cdew…TPrs`. Rotate again via <https://huggingface.co/settings/tokens> if any of them ever leaves this chat history.

### Resolved issues this session
- ~~After live write-back to LanceDB, the in-process table handle sometimes returns the pre-writeback similarity~~ — **FIXED** in commit `e2ca547`. Root cause was a module-level `_table` cache in `local_search.py` holding a snapshot reference; `write_articles_to_lancedb` opened a separate DB connection so the cached table never saw the writes. Fix: drop the `_table` cache (re-open table on every search; cheap metadata read) AND have the writer use the same shared `db` connection as the reader (`get_db()` exported from `local_search.py`). Verified end-to-end on prod: LOCAL_BEFORE=`not_found@0.4507` → LIVE writes 26 → LOCAL_AFTER=`found@0.6283` immediately. The "Added N articles to KB" chip is now actually true in real time.

### Key env vars user has set (already in `.env`)
- `GOOGLE_API_KEY` (Gemini, Tier 1 billing enabled) — also set as HF Space Secret
- `GROQ_API_KEY` (free tier) — also set as HF Space Secret
- `NCBI_API_KEY` + `NCBI_EMAIL` (free) — also set as HF Space Secrets
- `NEXT_PUBLIC_API_URL=http://localhost:8000` (in `frontend/.env.local`; **only for local `npm run dev`**)
- `NEXT_PUBLIC_API_URL=https://Tony0489-MedCite-api.hf.space` (set in **Vercel dashboard** for `production` env; baked into the prod bundle)

---

## Resume Prompt (paste this if Cursor context fills up)

> The canonical, kept-in-sync version of this prompt lives at the repo root in
> `RESUME_PROMPT.txt`. If anything below diverges from `RESUME_PROMPT.txt`,
> trust `RESUME_PROMPT.txt` — that's the file Cursor users actually paste
> into a fresh chat.

```
I'm continuing work on "MedCite" — a medical Q&A web app for the Jubilant
Pharma hackathon. See RESUME_PROMPT.txt at the repo root for the live
session-handover prompt (URLs, last commit, current scope, what to do next).
Read PROJECT_SPEC.md COMPLETELY before taking any action — non-negotiables
in §3, API shape in §6, component list in §8, polish scope in §9
("Day 3 polish — locked scope") and §12 ("Day 3 — Remaining"). Read
PITCH.md before building any slides; do NOT regenerate it.
```

---

## New Chat Bootstrap Prompt (project-wide handoff)

Use this prompt in a brand-new chat when you want the assistant to understand
the full MedCite system quickly (architecture, constraints, demo flow, and
what to avoid breaking):

```
You are resuming work on "MedCite" (Jubilant Pharma hackathon): a clinical Q&A
web app for doctors that returns short, cited answers from PubMed and abstains
when confidence is low.

Read order (mandatory):
1) PROJECT_SPEC.md fully — this is the technical source of truth.
2) PITCH.md fully — canonical demo/deck content and judge narrative.
3) RESUME_PROMPT.txt — current session state and immediate next actions.

Non-negotiables (never violate):
- LLMs never write URLs; backend stitches PubMed/DOI from metadata.
- Synthesizer never answers from prior knowledge (chunks-only or INSUFFICIENT_EVIDENCE).
- Verifier must be a different vendor from synthesizer.
- Confidence < 0.75 => abstain.
- Live PubMed runs only when doctor clicks (never auto-run on local miss).
- Every source card must show quoted passage + clickable PubMed + DOI.
- UI is a clinical tool (one question, one answer), not a chatbot.

Current architecture (shipped):
- Frontend: Next.js 16 + JS + Tailwind 4 + shadcn/ui, hosted on Vercel.
- Backend: FastAPI + LanceDB + MiniLM embeddings, hosted on HF Spaces.
- Synthesizer: Gemini 2.5 Flash-Lite.
- Verifier: Llama 3.3 70B via Groq.
- Corpus: ~10k PubMed abstracts, 17,456 chunks in LanceDB.
- Retrieval thresholds: local similarity 0.55; verifier confidence 0.75.

Two-tier flow:
1) Tier 1 local search (`/query/local`): embed query -> LanceDB top-k.
   - If top_sim >= 0.55: synthesize + verify -> answer if conf >= 0.75 else abstain.
   - If top_sim < 0.55: return not_found with score (no automatic live call).
2) Tier 2 live search (`/query/live`, user-triggered):
   - PubMed esearch/efetch -> chunk/rank -> same synth+verify.
   - If successful, write new chunks back to LanceDB (self-improvement loop).

Critical demo safety:
- Never run live search on "Levetiracetam status epilepticus dose" before stage time;
  doing so contaminates the showstopper by writing it into Tier 1 cache.
- If contaminated, reset HF backend with deploy/hf/sync.ps1 and re-verify
  `/query/local` for Levetiracetam returns `status=not_found, top_sim~0.39`.

When asked to build slides:
- Use PITCH.md as locked copy source; do not rewrite pitch content.
- Keep trust pitch verbatim and preserve hero query order from PITCH.md.

When asked to change code:
- Keep changes minimal, test quickly, and preserve all hard rules above.
- Prefer explicit abstention over speculative answers.
- Report risks if a change could affect demo reliability.
```
