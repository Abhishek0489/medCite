# Flutter Windows Frontend - New Chat Prompt

Paste the prompt below into a new chat when you want an assistant to build a
Flutter Windows frontend for MedCite without backend changes.

---

## Copy-Paste Prompt

```text
You are building a new Flutter Windows frontend for an existing backend project called MedCite.

Goal:
- Build a production-quality Flutter app (Windows desktop) that consumes the existing MedCite FastAPI backend.
- Do NOT modify backend code or API contracts.
- Replicate the core user experience of the current web frontend: one-question clinical tool, not a chatbot.

Read these files first (in this exact order):
1) PROJECT_SPEC.md (full file)
2) backend/main.py (endpoint + response contract)
3) frontend/lib/api.js (how current frontend calls backend)
4) frontend/app/page.jsx (state-machine UX behavior)
5) PITCH.md sections 4, 6, 7, 8 (trust rules + hero queries + demo flow)

Non-negotiable product rules (must be preserved in UI behavior):
1. LLMs never write URLs (backend stitches PubMed/DOI links).
2. No answers from model memory; source-grounded only.
3. Cross-vendor verification is mandatory (already in backend).
4. Confidence < 0.75 => abstain UI.
5. Live PubMed search runs only when user explicitly clicks (never auto-triggered).
6. Every source card shows quoted passage + PubMed + DOI.
7. UI is clinical-tool style: one question, one answer card (not chat threads).

Backend API contract (do not change):
- GET /health
- POST /query/local    body: {"query":"..."}
- POST /query/live     body: {"query":"..."}

Response shape:
{
  "status": "found" | "not_found" | "insufficient_evidence",
  "tier": "local" | "live",
  "answer": string,
  "confidence": number,
  "sources": [
    {
      "citation_number": number,
      "title": string,
      "journal": string,
      "year": string,
      "authors": string,
      "publication_type": string,
      "url": string,
      "doi_url": string,
      "quoted_passage": string
    }
  ],
  "reasoning": {
    "queries_searched": string[],
    "top_similarity": number,
    "verifier_unsupported_claims": string[],
    "articles_added_to_kb": number | null,
    "write_back_error": string | null
  }
}

Flutter implementation requirements:
- Use Dart null safety.
- Use clean structure:
  - lib/models/
  - lib/services/
  - lib/screens/
  - lib/widgets/
  - lib/state/
- HTTP client: Dio or http package (your choice, justify briefly).
- Environment config for backend base URL:
  - local: http://localhost:8000
  - prod:  https://Tony0489-MedCite-api.hf.space
- Include robust error handling and request timeout behavior.

Required UI screens / states:
1) Home screen:
   - Query input + Ask button
   - Hero query chips (same order as web app)
   - Backend status chip (online / warming / offline)
   - Refresh button (hard reload behavior equivalent)
2) Loading state (local query in progress)
3) NotFound state:
   - show top similarity
   - show "Search live" button
   - show "Rephrase" action
4) Live progress state:
   - show 3-step pipeline labels
5) Answered state:
   - answer text
   - confidence meter
   - source cards with PubMed + DOI links
   - badge indicating local verified KB vs live multi-AI
6) Abstain state:
   - clear no-reliable-answer panel
   - show reason and rephrase option
7) Error state:
   - request failure details + retry action

State machine behavior (must mirror web app):
- idle -> loading -> answered | notfound | abstain | error
- notfound -> live -> answered | abstain | notfound | error
- Submitting a new query resets previous result (one-question workflow).

Hero queries to include (same order):
1. Does empagliflozin reduce cardiovascular mortality in HFpEF?
2. First-line treatment for drug-resistant tuberculosis 2024
3. Levetiracetam status epilepticus dose
4. Is acetaminophen safe in third trimester pregnancy?
5. Side effects of SGLT2 inhibitors in elderly patients

Critical demo safety warning to preserve in docs/comments:
- Do NOT run live search on Levetiracetam before stage time if preserving showstopper behavior is required; it writes back and can convert it into Tier-1 hit.

Deliverables expected from you:
1) A concrete Flutter project structure.
2) All Dart model classes for API parsing.
3) API service layer implementation.
4) State management implementation (provider/riverpod/bloc - pick one and justify).
5) Main screen + widgets code.
6) README section: how to run on Windows.
7) A short test checklist for manual verification against local backend.

Constraints:
- Keep backend untouched.
- No speculative API shape changes.
- No extra features that change clinical workflow.

When done, provide:
- Files created/updated
- Run commands
- Known limitations
- Next suggested improvement (optional)
```

---

## Quick Notes

- Backend is Python/FastAPI and already production-running. Treat it as fixed.
- Preserve the state-machine UX and explicit live-search click gate.
- If the assistant suggests backend edits, reject and re-anchor to this file.
