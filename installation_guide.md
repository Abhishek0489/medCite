# MedCite Installation Guide

This guide is for judges/reviewers to run or verify the project quickly.

## 1) Tech Stack

- Frontend: `Next.js 16` (App Router, JavaScript) + `Tailwind CSS 4` + `shadcn/ui`
- Backend: `FastAPI` + `LanceDB` + `sentence-transformers` (`all-MiniLM-L6-v2`)
- Synthesizer LLM: `Google Gemini 2.5 Flash-Lite`
- Verifier LLM: `Llama 3.3 70B` via `Groq` (different vendor from synthesizer)
- Data source: `PubMed E-utilities API`
- Optional desktop demo frontend: `Flutter` (`frontEndapp/`)
- Deployment:
  - Frontend: Vercel
  - Backend: Hugging Face Spaces (Docker)

## 2) Deployed Project Links (No local build required)

If you only want to evaluate functionality, use the hosted version:

- App (Frontend): [https://abhi04-medcite.vercel.app](https://abhi04-medcite.vercel.app)
- Backend API: [https://Tony0489-MedCite-api.hf.space](https://Tony0489-MedCite-api.hf.space)
- Health check: [https://Tony0489-MedCite-api.hf.space/health](https://Tony0489-MedCite-api.hf.space/health)

Note: You do not need to rebuild ingestion data to use the deployed app.

## 3) Run Locally (Optional)

### Prerequisites

- Python `3.12+`
- Node.js `22 LTS` + `npm`
- (Optional) Flutter SDK for Windows desktop demo

### Environment Variables (Required for local backend)

Create a root `.env` file at:

- `e:\Development\jubiliant hackathon\.env`

You can copy from template:

```powershell
cd "e:\Development\jubiliant hackathon"
Copy-Item .env.example .env
```

Add these values in `.env`:

```env
GOOGLE_API_KEY=your_google_ai_studio_key
GROQ_API_KEY=your_groq_key
NCBI_API_KEY=your_ncbi_key_optional
NCBI_EMAIL=your_email@example.com
```

Where to get keys:

- Google Gemini key (`GOOGLE_API_KEY`): [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
- Groq key (`GROQ_API_KEY`): [https://console.groq.com/keys](https://console.groq.com/keys)
- NCBI key (`NCBI_API_KEY`, optional but recommended): [https://www.ncbi.nlm.nih.gov/account/settings/](https://www.ncbi.nlm.nih.gov/account/settings/)

Notes:

- `NCBI_API_KEY` is optional; without it, PubMed still works but with lower rate limits.
- Never commit `.env` or `frontend/.env.local` to git.

### Backend (Terminal 1, PowerShell)

```powershell
cd "e:\Development\jubiliant hackathon\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Backend (Terminal 1, Git Bash)

```bash
cd "/e/Development/jubiliant hackathon/backend"
python -m venv .venv
./.venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (Terminal 2)

```powershell
cd "e:\Development\jubiliant hackathon\frontend"
npm install
```

### Frontend (Terminal 2, Git Bash)

```bash
cd "/e/Development/jubiliant hackathon/frontend"
npm install
npm run dev
```

Create `frontend/.env.local` with:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then run:

```powershell
npm run dev
```

### Verify

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:8000/health`

## 4) Demo Prompts

Use the curated prompt set here:

- [`DEMO_PROMPTS.md`](./DEMO_PROMPTS.md)

Hero query set (judge demo order) is documented in:

- [`PITCH.md`](./PITCH.md)

## 5) Common Issues and Fix Commands

### Issue A: "Backend offline" in UI

Cause: backend not running, wrong API URL, or cold backend startup.

Fix:

```powershell
# confirm backend health
Invoke-RestMethod -Method GET -Uri http://localhost:8000/health
```

```bash
# confirm backend health
curl -s http://localhost:8000/health
```

Also verify `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then restart frontend:

```powershell
cd "e:\Development\jubiliant hackathon\frontend"
npm run dev
```

### Issue B: Missing API key error (`GOOGLE_API_KEY` / `GROQ_API_KEY`)

Cause: `.env` missing backend secrets.

Fix:

1. Copy `.env.example` to `.env` at repo root.
2. Fill required keys.
3. Restart backend server.

### Issue C: LanceDB table not found

Cause: local vector index not initialized.

Fix:

```powershell
cd "e:\Development\jubiliant hackathon\backend"
.\.venv\Scripts\Activate.ps1
python -m ingestion.embedder
```

```bash
cd "/e/Development/jubiliant hackathon/backend"
./.venv/Scripts/activate
python -m ingestion.embedder
```

### Issue D: PowerShell blocks `sync.ps1` ("running scripts is disabled")

Cause: Execution policy restriction.

Fix (current session only):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then run your sync command again.

### Issue E: Port already in use (`8000` or `3000`)

Fix (example using alternate ports):

```powershell
# backend
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

```bash
# backend
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

```env
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8001
```

Then restart frontend.

## 6) Optional Flutter Desktop Demo

```powershell
cd "e:\Development\jubiliant hackathon\frontEndapp"
flutter pub get
flutter run -d windows --dart-define=MEDCITE_BASE_URL=https://Tony0489-MedCite-api.hf.space
```

## 7) Repository

- GitHub: [https://github.com/Abhishek0489/medCite](https://github.com/Abhishek0489/medCite)

