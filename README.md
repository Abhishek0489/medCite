# MedCite

Medical Q&A for doctors — fast, cited, trustworthy.

**Full project spec:** see [`PROJECT_SPEC.md`](./PROJECT_SPEC.md).

**Live app (Vercel):** [https://abhi04-medcite.vercel.app](https://abhi04-medcite.vercel.app)  
**Working demo video:** [medCite_demoVid.mp4 (Google Drive)](https://drive.google.com/file/d/1RpnZBwDC35FC8sJzAMw3Q8RK4z3PcS1n/view?usp=sharing)

## What it does

Doctor types a medical question. System:

1. Searches a local curated knowledge base of PubMed articles (Diabetes + Cardiology).
2. If found → returns a short answer with clickable PubMed citations in ~3 seconds.
3. If not found → doctor can escalate to a live multi-AI search (PubMed API + Gemini + Llama via Groq).
4. If confidence is low → system honestly says "No reliable answer found".

Every citation is real. LLMs never invent URLs.

## Quick start

Run locally with two terminals: backend on `:8000`, frontend on `:3000`.

### Prerequisites

- Python 3.12
- Node.js 22 LTS + npm

### Terminal 1 — Backend (PowerShell)

```powershell
cd "e:\Development\jubiliant hackathon\backend"

# One-time setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run API
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 1 — Backend (Git Bash alternative)

```bash
cd "/e/Development/jubiliant hackathon/backend"
python -m venv .venv
./.venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2 — Frontend

```bash
cd "/e/Development/jubiliant hackathon/frontend"
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then run:

```bash
npm run dev
```

### Verify locally

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:8000/health`

If the UI shows `Backend offline`, confirm `NEXT_PUBLIC_API_URL` is set to `http://localhost:8000`, then restart the frontend dev server.

## Quick run (Flutter Windows frontend)

Run the Windows desktop frontend from `frontEndapp`:

```powershell
cd "e:\Development\jubiliant hackathon\frontEndapp"
flutter pub get
flutter run -d windows
```

Use Hugging Face backend directly:

```powershell
flutter run -d windows --dart-define=MEDCITE_BASE_URL=https://Tony0489-MedCite-api.hf.space
```

For full Flutter setup details, see `frontEndapp/README.md`.

## Stack

- **Frontend:** Next.js 16 (App Router, JavaScript) + Tailwind 4 + shadcn/ui
- **Backend:** FastAPI + LanceDB + sentence-transformers (MiniLM-L6-v2)
- **LLMs:** Google Gemini 2.5 Flash-Lite (synthesizer) + Meta Llama 3.3 70B via Groq (verifier)
- **Data:** PubMed E-utilities API

## Status

See section 12 in [`PROJECT_SPEC.md`](./PROJECT_SPEC.md) for current progress.
