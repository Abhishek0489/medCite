# MedCite — Pitch & Demo Reference

> One-page-per-section reference for building the hackathon pitch deck. Everything here is verified against `PROJECT_SPEC.md` and the live system as of end-of-Day-2 (commit `706b6ef`). Use this to fill slides — don't paste it as-is.

---

## 1. The 30-second elevator pitch

> **MedCite is a clinical Q&A tool for doctors that never hallucinates.** A doctor types a question, and gets a 3-sentence answer with clickable PubMed citations in under 5 seconds — or an honest "no reliable answer found." We built it on a simple idea: **ChatGPT starts with the LLM and asks it to remember sources. We start with PubMed and ask the LLM to summarize what's actually there.**

That's the line you say if you have time for one sentence. Memorize it.

---

## 2. The problem (one slide)

- Doctors are time-starved and need **fast, trustworthy** medical answers at the point of care.
- ChatGPT and general LLMs **hallucinate citations** — fake DOIs, made-up authors, papers that don't exist. Documented and unsafe for clinical decisions.
- Live PubMed search returns 200 results and no synthesis — doctors have to read everything themselves.
- Existing "AI doctor" tools are chatbots optimized for engagement. Doctors don't want a conversation; they want **a tool: one question, one answer, with receipts.**

**The gap:** there's no product that combines (a) the speed and synthesis of an LLM with (b) the auditability of a real literature search.

---

## 3. What MedCite does (one slide, with screenshot)

A single search box. Doctor types `"Does empagliflozin reduce cardiovascular mortality in HFpEF?"`. In ~3 seconds:

- A **2–4 sentence answer**, every claim tagged `[1] [2] [3]`.
- Five **source cards** below, each showing:
  - Title, journal, year, authors
  - **Evidence-level badge** (RCT / Meta-analysis / Review / Guideline)
  - The exact **quoted passage** the LLM used
  - Clickable **PubMed link** + clickable **DOI link**
- A **green confidence meter** (verifier confidence ≥ 0.75)
- A **"Verified KB"** badge (or "Live multi-AI" if escalated)

If the cache has nothing: an **honest abstention screen** — *"closest match scored 0.53, below the safety threshold. We won't guess."* — with a button to escalate to live PubMed.

---

## 4. The 7 hard rules (the actual differentiator)

These are the lines that make the trust pitch real. Put them on a slide as a bulleted "What we will never do" list.

1. **LLMs never write URLs.** URLs are built from PubMed IDs in our database; the LLM only outputs `[1] [2]`. The backend stitches the real links in.
2. **LLMs never answer from memory.** The synthesizer prompt explicitly forbids using prior knowledge — it answers from retrieved chunks only, or returns `INSUFFICIENT_EVIDENCE`.
3. **A different vendor verifies.** The synthesizer is Google Gemini. The verifier is Meta's Llama 3.3 70B (via Groq). Same-vendor verification is a no-op; we use genuinely different models.
4. **Confidence below 0.75 → abstain.** No low-confidence guesses. Ever.
5. **The doctor controls the live search.** Local cache runs automatically. Live PubMed runs only when the doctor clicks the button.
6. **Every citation includes the quoted passage.** Doctors verify at a glance.
7. **The UI is a clinical tool, not a chatbot.** No chat history, no "I'd be happy to help!" — one question, one answer card.

---

## 5. Architecture (one slide, with diagram)

Four components, two tiers:

```
                    Doctor types a query
                            │
                            ▼
                  ┌─────────────────────┐
                  │  TIER 1: Pre-indexed│   ~3 seconds
                  │  PubMed cache       │
                  │  (LanceDB, 17,456   │
                  │   chunks, curated)  │
                  └──────────┬──────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
         Found? Yes                    Found? No
              │                             │
              ▼                             ▼
     ┌────────────────┐         Doctor clicks "Search live"
     │ Gemini synth   │                     │
     │      ↓         │                     ▼
     │ Llama verifies │            ┌─────────────────┐
     │      ↓         │            │ TIER 2: Live    │  ~20 sec
     │ Confidence ≥   │            │ PubMed E-util   │
     │ 0.75? → answer │            │ + same synth /  │
     │   else abstain │            │ verify pipeline │
     └────────────────┘            │ + write back to │
                                   │ cache (self-    │
                                   │ improvement)    │
                                   └─────────────────┘
```

**Component breakdown:**

| Component | What it does | Tech |
|---|---|---|
| 1. Ingestion (one-time, Day 1) | Pull ~10K PubMed abstracts (Diabetes + Cardiology, 2015+, English, has-abstract). Chunk → embed → store. | PubMed E-utilities, sentence-transformers MiniLM-L6-v2, LanceDB |
| 2. Pre-indexed retriever (every query) | Embed query, cosine search top-5. If top similarity < 0.55 → "not found". | LanceDB cosine search |
| 3. Live fallback (on click) | PubMed esearch → efetch top-10 → chunk → rank → same synth/verify pipeline → **write new articles back into the cache** | PubMed E-utilities, embedder, LanceDB |
| 4. Synth + Verify (shared) | Synth: Gemini 2.5 Flash-Lite, strict prompt, citations only. Verify: Llama 3.3 70B (Groq), JSON output `{confidence, unsupported_claims}`. | Google AI Studio, Groq |

---

## 6. The trust pitch (memorize verbatim)

> **"Every other AI tool starts with the LLM and asks it to remember sources. We start with PubMed and ask the LLM to summarize what's actually there. The LLM is never allowed to invent a citation, never allowed to answer from memory, and a second model from a different company verifies every claim before the doctor ever sees it. If it can't reach 75% confidence — it says so. That's the difference between a chatbot and a clinical tool."**

That's four sentences. ~25 seconds spoken. This is the whole pitch.

---

## 7. The five hero queries (memorize all five)

These are the demo. Practice each transition.

| # | Query | What it shows | Demo line |
|---|---|---|---|
| 1 | *"Side effects of SGLT2 inhibitors in elderly patients"* | Tier-1 hit, **Meta-analysis** evidence badge, conf 0.80 | *"Three seconds. Five sources. Every one is a real PubMed paper."* |
| 2 | *"Does empagliflozin reduce cardiovascular mortality in HFpEF?"* | Tier-1 hit, top sim 0.82, **RCT + Review** badges, conf 0.80 | *"Notice the badges — RCT and Review. We surface the evidence level so you know what kind of study this is."* |
| 3 | *"First-line treatment for drug-resistant tuberculosis 2024"* | **Self-improvement story.** Was a Tier-1 miss yesterday. Today scores top sim 0.80 because Day-1 live escalation wrote 21 articles back. | *"Yesterday this missed locally and we used the live fallback. Today it's instant — every doctor's question makes the next doctor's faster. The system actually learns."* |
| 4 | *"Levetiracetam status epilepticus dose"* | **Live-multi-AI showstopper.** Out of corpus (no neurology specialty) → `NotFoundScreen` → click *Search live* → 3-stage progress (PubMed → Gemini → Llama) → cited answer + "Added N articles to KB" chip | *"Watch what happens when our cache doesn't have it. PubMed → Gemini synthesizes → Llama verifies. ~20 seconds, fully cited, and now in the cache for next time."* |
| 5 | *"Is acetaminophen safe in third trimester pregnancy?"* | **Abstention.** Top sim 0.53, below 0.55 threshold → amber screen *"closest match scored 0.53, below the safety threshold. We won't guess."* | *"This is what makes us different. ChatGPT would have given you a confident answer. We tell the doctor: we don't know, and here's why."* |

**CRITICAL:** Do **NOT** click query #4 before stage time. The moment you do, write-back absorbs the articles into the cache and the showstopper animation is gone for that container's lifetime. Backup if contaminated: *"H. pylori first-line eradication 2024"* — was the prior #4, contaminated mid-session by the backup-demo recording, but a `deploy/hf/sync.ps1` rebuild resets it. Verified hero #4 phrasing: PubMed returns 169 PMIDs, full live pipeline returns `status=found, conf=0.80, top_sim=0.8054, 5 sources, 26 articles written back`.

**Why terse medical phrasing for #4:** PubMed's E-utilities `esearch` is a keyword matcher, not a question-answering search. Long natural-language phrasings with grammatical filler — e.g. *"Best first-line antibiotic for community-acquired pneumonia in adults 2024"* — used to return **0 PMIDs** and dead-end the live demo. The Day-3 PM polish (commit `e2ca547`) added a stop-word-stripped retry that mostly rescues this, but the safest demo phrasings remain terse medical terms (drug or condition + topic + optional year). The Tier-1 hero queries (#1, #2, #3) and the abstention query (#5) are unaffected — those go through LanceDB semantic embeddings locally, not PubMed's keyword index, so any natural-language phrasing works there.

---

## 8. Demo script — 2 minutes flat

Total time budget: 120 seconds. Practice with a stopwatch.

| Time | What you say + do | Slide / screen |
|---|---|---|
| 0:00–0:15 | **The problem.** "Doctors need fast trustworthy answers. ChatGPT hallucinates citations. PubMed gives 200 results and no synthesis. We built MedCite." | Title slide → problem slide |
| 0:15–0:30 | **The trust line.** "Every other tool starts with the LLM and asks it to remember sources. We start with PubMed and ask the LLM to summarize what's actually there." | Architecture diagram |
| 0:30–0:50 | **Hero query #2** (empagliflozin/HFpEF). Type, hit Ask, point at: 3-second response, RCT badge, quoted passage, clickable PubMed link, confidence meter. | Live app |
| 0:50–1:10 | **Hero query #3** (TB). "Yesterday this missed. Today it's instant — the system learns from every escalation." Show top similarity 0.80. | Live app |
| 1:10–1:35 | **Hero query #4** (Levetiracetam status epilepticus dose). Show NotFoundScreen → click Search Live → 3-stage progress → cited answer. "20 seconds, fully cited, and now in the cache." | Live app |
| 1:35–1:50 | **Hero query #5** (acetaminophen pregnancy). Land on abstention screen. "We tell the doctor we don't know, and here's why. ChatGPT would have lied." | Live app |
| 1:50–2:00 | **Close.** "Cited, verified, honest. The 7 hard rules on the screen are the architecture, not marketing. That's MedCite." | The 7 hard rules slide |

---

## 9. Anticipated Q&A (rehearse answers)

### "Why not just use GPT-4 with web search? It cites sources too."
GPT-4 with web search **cites sources to justify what it already wrote**. We do it backwards: we retrieve sources first, then ask the LLM to summarize *only* those sources. Our LLM is structurally incapable of citing something it didn't read. There's a difference between "trust the LLM and verify after" and "constrain the LLM at generation time."

### "What stops the LLM from making things up about the sources you give it?"
Two things. (1) The synthesizer prompt explicitly forbids it; if a source isn't relevant, it's required to output `INSUFFICIENT_EVIDENCE`. (2) A **separate model from a different vendor** (Llama 3.3 70B from Meta, via Groq) reads the answer and the sources and outputs a structured JSON: `{confidence: 0–1, unsupported_claims: [...]}`. If confidence is below 0.75 — we abstain. The doctor never sees a low-confidence guess.

### "Why two LLMs from different vendors?"
Same-model verification is a no-op — a model is bad at catching its own hallucinations because they look correct to it. Cross-vendor verification catches errors that intra-vendor agreement misses. Google's training data, Meta's training data, different RLHF — different blind spots.

### "What's in the knowledge base? How big? How current?"
17,456 chunks from ~10,000 PubMed abstracts across Diabetes and Cardiology, 2015+. **The corpus grows itself** — every successful live escalation writes its sources back, so popular queries become instant on the next ask. We could trivially scale to 6 specialties × 7,500 articles each in an afternoon — bottleneck is PubMed download speed, not our infra.

### "How do you handle out-of-scope questions?"
Three behaviors depending on context. (1) Cache miss + doctor escalates → live PubMed fallback. (2) Cache miss + cache had something close-but-not-confident-enough → abstention screen with the closest similarity score shown. (3) Live search also fails verification → still abstain. We never make something up to fill silence.

### "What's the latency?"
Tier-1 (cache hit): 2–5 seconds. Tier-2 (live escalation): 15–25 seconds, dominated by PubMed's E-utilities API which is government infrastructure. The 2-tier architecture exists *because* live PubMed is too slow to be the default.

### "What about cost? Can hospitals afford to run this?"
Per query: 1 Gemini Flash-Lite call (~$0.0001) + 1 Groq Llama call (free tier, $0.0005 paid). At 1,000 queries/day, that's under $1/day in inference. The expensive part — sentence-transformers embeddings — runs locally on CPU; no API cost. Compare with hospital subscriptions to UpToDate at thousands of dollars per seat per year.

### "What about HIPAA / patient data?"
Right now MedCite answers *literature* questions, not patient-specific questions. We never see PHI. If we extended to chart-aware queries, the deployment story changes — Gemini and Groq both have BAA-eligible enterprise tiers, and the cache architecture means patient data could stay on a hospital's own infrastructure with the LLM calls being the only network hop.

### "Why JavaScript and not TypeScript? You're at a hackathon, not in production."
Exactly because we're at a hackathon. Three days, a 1-person team, the type system isn't paying for itself in that timeframe. shadcn/ui supports JS via `tsx: false`. We made the call to spend the type-system hours on the actual differentiator — the cross-vendor verifier and the 7 hard rules.

### "Is this just RAG?"
Yes — and "just RAG" is the *correct* architecture for this problem. The novelty isn't the retrieval. The novelty is (a) the cross-vendor verifier as a hard safety gate, (b) the self-improvement write-back loop, and (c) the explicit abstention behavior. Most "RAG" demos still let the LLM speak when the retrieval was weak. We don't.

### "What's next if you win?"
Three things, in order. (1) Add 4 more specialties (infectious disease, oncology, nephrology, neurology) — already specced, ~30 minutes of ingestion. (2) Pilot with a teaching hospital — the abstention behavior is exactly what residents need when they're uncertain. (3) Add UpToDate-style topic pages built from the same retrieval pipeline.

---

## 10. The numbers (memorize, drop into slides)

- **17,456** chunks in the pre-indexed cache
- **~10,000** PubMed abstracts ingested (Diabetes + Cardiology)
- **2** specialties live, **6** more designed in
- **2 LLM vendors** (Google + Meta) for cross-verification
- **0.75** confidence threshold to surface an answer
- **0.55** similarity threshold to consider the cache "hit"
- **2–5 seconds** for a cache-hit answer
- **15–25 seconds** for a live escalation (dominated by PubMed API)
- **3-day build**, 1 person
- **Zero** invented citations across all hero queries (verified manually)
- **$0.001** approximate per-query LLM cost at production volume
- **21** articles added to the cache yesterday by a single live escalation (the TB self-improvement story)

---

## 11. Tech stack (one slide, table)

| Layer | Technology | Why this choice |
|---|---|---|
| Frontend | Next.js 16 (App Router) + JavaScript + Tailwind 4 + shadcn/ui | Clinical look out of the box; JS over TS to ship faster; App Router for clean routing |
| Backend | FastAPI + Python 3.12 | Best Python framework for ML APIs; async + Pydantic; deploys anywhere |
| Vector DB | LanceDB (persistent, on-disk) | Pure Rust, no MSVC build hell on Windows, scales to millions of chunks on a laptop |
| Embeddings | sentence-transformers MiniLM-L6-v2 (384-dim) | Free, CPU-runnable, strong on biomedical text |
| Synthesizer | Google Gemini 2.5 Flash-Lite (primary) + Flash (fallback) | Tight reasoning, no thinking-token truncation, deterministic at temperature=0 |
| Verifier | Meta Llama 3.3 70B via Groq | Different vendor (rule #3), 500 tok/s inference, free tier sufficient for demo |
| Article source | PubMed E-utilities API | Free, no auth needed for low-volume; NCBI key bumps to 10 req/s |
| Frontend hosting | Vercel | Free tier, auto-deploy from GitHub, instant cold start |
| Backend hosting | Cloudflare Tunnel (demo) → Render/Railway (prod) | Free for demo; $5–7/mo for production |

---

## 12. What's in this repo (so you know what to point at)

- `PROJECT_SPEC.md` — the source of truth, 571 lines, every decision documented with rationale
- `backend/` — FastAPI app, 4 components, ~1,200 LOC of Python
- `frontend/` — Next.js app, 6 components, all `.jsx`, ~800 LOC
- `data/lancedb/` — 53.5 MB of pre-indexed PubMed chunks (gitignored)
- This file (`PITCH.md`) — the deck reference

---

## 13. The closing line

If you only get one sentence at the end:

> **"This isn't a chatbot. It's a clinical tool. It cites every claim, it verifies with a second model from a different company, and when it doesn't know — it says so. That's the only safe way to put an LLM in front of a doctor."**

Land that, smile, take questions.

---

## 14. Master query sets — verification & demo

Two query sets you'll run on presentation day. Keep them separate; never mix.

- **Set A — Verification.** Run ~30 minutes before the judge demo. Confirms Tier-1 cache, Tier-2 live escalation, write-back, abstention, and the showstopper hero are all healthy — **without** contaminating any judge-facing query.
- **Set B — Judge demo.** The five hero queries from §7. The homepage chips are pre-populated in the order below.

### Set A — pre-demo verification (5 steps, ~3 min total)

| # | Query | Channel | Expected | Why this query |
|---|---|---|---|---|
| A1 | Open <https://abhi04-medcite.vercel.app> and wait for the green "backend healthy" indicator (warming chip clears within ~30 s if HF Space is cold) | UI | Green dot, hero chips visible | Confirms HF Space is awake and frontend ↔ backend health check works |
| A2 | *"Metformin contraindications in chronic kidney disease"* | UI — type & Ask | Tier-1 hit, conf ≥ 0.75, ~3 sec, 5 source cards with quoted passages | Real diabetes query, almost certainly in corpus → confirms synth (Gemini) + verify (Llama) pipeline end-to-end. **Not a hero query** — won't taint the demo. |
| A3 | *"First-line therapy for ulcerative colitis"* | UI — type, Ask, then click *Search live* | NotFoundScreen → click → ~20 sec → cited answer + *"Added N articles to KB"* chip | Out of corpus (gastroenterology). Confirms Tier-2 PubMed → synth → verify pipeline AND write-back. **Sacrificial** — never used in the demo, so contaminating it is fine. |
| A4 | *"Is acetaminophen safe in third trimester pregnancy?"* | UI — type & Ask, do **not** escalate | Amber abstention screen showing closest sim ≈ 0.45, *"below the safety threshold. We won't guess."* | Confirms the abstention threshold still fires at 0.55. **Read-only** — abstention writes nothing to LanceDB, so asking it now does not contaminate hero #4 (acetaminophen) in the actual demo. |
| A5 | `POST /query/local` body `{"query":"Levetiracetam status epilepticus dose"}` against <https://Tony0489-MedCite-api.hf.space> — do **not** open this in the UI | API only | `status=not_found`, `top_sim ≈ 0.39` (well below 0.55) | **Critical.** Proves the live-multi-AI showstopper hero is still uncontaminated. **Never click "Search live" on this query before the judge demo** — write-back would absorb the articles into Tier 1 and the showstopper animation is gone. |

PowerShell one-liner for A5:

```powershell
Invoke-RestMethod -Method POST -Uri https://Tony0489-MedCite-api.hf.space/query/local -ContentType 'application/json' -Body '{"query":"Levetiracetam status epilepticus dose"}'
```

**If A5 fails** (returns `status=found` or `top_sim > 0.55`): the showstopper is contaminated. Reset the bundled image (~90 s):

```powershell
.\deploy\hf\sync.ps1 -HfUser Tony0489 -HfSpace MedCite-api -HfToken hf_***
```

Then re-run A5 to confirm `top_sim ≈ 0.39` before going on stage.

### Set B — judge demo (the 5 hero queries)

Order matches the homepage chips left-to-right. Full demo lines + what each query proves are in §7.

| Demo # | Chip label / typed query | Tier | Proves |
|---|---|---|---|
| 1 | *"Does empagliflozin reduce cardiovascular mortality in HFpEF?"* | Tier 1 | Speed + RCT/Review evidence badges + clickable PubMed |
| 2 | *"First-line treatment for drug-resistant tuberculosis 2024"* | Tier 1 | Self-improvement — yesterday missed, today instant (sim 0.80) |
| 3 | *"Levetiracetam status epilepticus dose"* | Tier 2 → write-back | **Showstopper:** PubMed → Gemini → Llama, "Added 26 articles" chip |
| 4 | *"Is acetaminophen safe in third trimester pregnancy?"* | Abstain | Honest abstention — *"closest match scored 0.45"* |
| 5 | *"Side effects of SGLT2 inhibitors in elderly patients"* | Tier 1 | **Backup** if any of #1–4 misbehaves — Meta-analysis badge |

**Hard rules during the live demo:**

1. Demo queries 1–4 in order. Query 5 is held in reserve.
2. Do **not** click "Search live" on demo #4 (Levetiracetam) until you're at the showstopper moment.
3. If demo #4 has been contaminated (top_sim > 0.55 in A5), the backup phrasing for the same showstopper is *"H. pylori first-line eradication 2024"* — but a `deploy/hf/sync.ps1` rebuild is the cleaner fix.
4. The abstention on demo #4 (acetaminophen) is the feature, not a bug — do not escalate it on stage.

---
