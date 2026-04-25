# MedCite — Hugging Face Spaces deploy

This folder holds the artifacts that ship to the HF Space backend. The actual
push happens from a sibling directory (`..\medcite-hf-space\`) so the 53 MB
LanceDB cache never lands in the GitHub repo.

## One-time prerequisites

1. HF account with a Docker Space created (CPU Basic, Public).
2. Four Space Secrets set in the Space settings UI: `GOOGLE_API_KEY`,
   `GROQ_API_KEY`, `NCBI_API_KEY`, `NCBI_EMAIL`.
3. HF write-scoped access token from
   <https://huggingface.co/settings/tokens>.

## Deploy

```powershell
# From the repo root:
.\deploy\hf\sync.ps1 `
    -HfUser   <your-hf-username> `
    -HfSpace  <your-space-name> `
    -HfToken  hf_xxx
```

The script:

1. Creates a sibling deploy dir `..\medcite-hf-space\`.
2. Copies in `Dockerfile`, `.dockerignore`, the entire `backend/` tree, and
   the prebuilt `data/lancedb/` cache.
3. Initialises a fresh git repo (or reuses an existing one).
4. Force-pushes to `https://huggingface.co/spaces/<HfUser>/<HfSpace>` on the
   `main` branch.

HF then triggers a remote Docker build (~10 min first time, 2-3 min on
incremental changes thanks to layer caching). Watch progress at:
`https://huggingface.co/spaces/<HfUser>/<HfSpace>?logs=build`.

Once the build is "Running", smoke-test:

```powershell
$base = "https://<HfUser>-<HfSpace>.hf.space"
Invoke-RestMethod "$base/health"

$body = @{ query = "Does empagliflozin reduce cardiovascular mortality in HFpEF?" } | ConvertTo-Json
Invoke-RestMethod "$base/query/local" -Method Post -Body $body -ContentType 'application/json'
```

## Notes

- The Dockerfile pre-downloads `sentence-transformers/all-MiniLM-L6-v2` at
  build time so the first user query is not a 90 MB cold-cache fetch.
- HF Spaces auto-sleeps after 48 h of no traffic on the free tier; first
  request after a sleep takes ~30 s to spin up. Pin the URL with UptimeRobot
  if you need bone-stable warm latency.
- The 2 vCPU / 16 GB free tier is comfortable for sentence-transformers +
  LanceDB (we use ~1 GB), but encode is on a shared CPU pool — expect ~6 s
  total query latency vs ~3 s on a dedicated laptop.
