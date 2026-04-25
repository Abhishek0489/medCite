# Sync MedCite backend + LanceDB cache to a Hugging Face Docker Space.
# Run from the repo root:
#
#     .\deploy\hf\sync.ps1 -HfUser Tony0489 -HfSpace MedCite-api -HfToken hf_xxx
#
# Idempotent. Safe to re-run after backend code edits — it rebuilds the
# sibling deploy dir from scratch each time, then force-pushes.

[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$HfUser,
    [Parameter(Mandatory)] [string]$HfSpace,
    [Parameter(Mandatory)] [string]$HfToken,
    [string]$CommitMessage = "deploy: sync backend + lancedb to HF Space",
    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"

$repoRoot   = Resolve-Path "$PSScriptRoot\..\.."
$deployDir  = Resolve-Path "$repoRoot\..\" | Join-Path -ChildPath "medcite-hf-space"

Write-Host "Repo root  : $repoRoot"
Write-Host "Deploy dir : $deployDir"

# --- Sanity checks on source files ---
$dockerfile = Join-Path $repoRoot "deploy\hf\Dockerfile"
$dockerignore = Join-Path $repoRoot "deploy\hf\.dockerignore"
$backendDir = Join-Path $repoRoot "backend"
$lanceDir   = Join-Path $repoRoot "data\lancedb"

foreach ($p in @($dockerfile, $dockerignore, $backendDir, $lanceDir)) {
    if (-not (Test-Path $p)) { throw "Missing required source: $p" }
}

$lanceSize = (Get-ChildItem $lanceDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("LanceDB cache size: {0:N1} MB" -f $lanceSize)
if ($lanceSize -lt 1) { throw "LanceDB cache looks empty -- aborting." }

# --- Prepare deploy dir (always start with a clean .git so LFS attrs apply
# to a fresh history; pushing to HF Spaces uses --force anyway) ---
if (Test-Path $deployDir) {
    Get-ChildItem $deployDir -Force | Remove-Item -Recurse -Force
} else {
    New-Item -ItemType Directory -Path $deployDir | Out-Null
}

Copy-Item $dockerfile   (Join-Path $deployDir "Dockerfile")
Copy-Item $dockerignore (Join-Path $deployDir ".dockerignore")

# Initialise git + LFS BEFORE copying any binary content so that the
# .gitattributes filter is in place when the lance files first get added.
Push-Location $deployDir
try {
    git init -q
    git checkout -q -b main
    git lfs install --local | Out-Null
    # HF Spaces' pre-receive hook rejects binary files unless they go through
    # XET / LFS. The .lance file format is a columnar binary container; the
    # _versions and _transactions trees also contain binary manifests.
    git lfs track "data/lancedb/**" | Out-Null
    git lfs track "*.lance"          | Out-Null
    git lfs track "*.manifest"       | Out-Null
    git lfs track "*.txn"            | Out-Null
}
finally { Pop-Location }

# Backend code (excluding venv + caches).
$backendDest = Join-Path $deployDir "backend"
robocopy $backendDir $backendDest /MIR /NFL /NDL /NJH /NJS /NP `
    /XD .venv __pycache__ .pytest_cache `
    /XF "*.pyc" | Out-Null

# LanceDB cache (the whole tree is needed at runtime).
$lanceDest = Join-Path $deployDir "data\lancedb"
robocopy $lanceDir $lanceDest /MIR /NFL /NDL /NJH /NJS /NP | Out-Null

# Minimal README so the Space page renders something useful.
$readme = @"
---
title: MedCite Api
emoji: 🩺
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# MedCite backend

Cited medical Q&A over a local PubMed knowledge base with live-search fallback.
See https://github.com/Abhishek0489/medCite for the full project.
"@
Set-Content -Path (Join-Path $deployDir "README.md") -Value $readme -Encoding UTF8

# --- Git operations (continue in deploy dir; init already done above) ---
Push-Location $deployDir
try {
    git add -A | Out-Null
    if ((git status --porcelain).Length -eq 0) {
        Write-Host "No changes to commit."
    } else {
        git -c user.email="deploy@medcite.local" -c user.name="medcite-deploy" `
            commit -m $CommitMessage -q | Out-Null
        Write-Host "Committed."
    }

    if ($SkipPush) { Write-Host "Skipping push (per -SkipPush)."; return }

    $remoteUrl = "https://${HfUser}:${HfToken}@huggingface.co/spaces/${HfUser}/${HfSpace}"
    if ((git remote) -contains "space") {
        git remote remove space | Out-Null
    }
    git remote add space $remoteUrl

    Write-Host "Pushing to HF Space (force) ... this also uploads the 53 MB lancedb cache."
    git push space main --force
    Write-Host ""
    Write-Host "Pushed. Build will start automatically."
    Write-Host "Watch:    https://huggingface.co/spaces/${HfUser}/${HfSpace}?logs=build"
    Write-Host "App URL:  https://${HfUser}-${HfSpace}.hf.space"
}
finally {
    Pop-Location
}
