# MedCite Pitch Deck

10-slide PowerPoint deck for the Jubilant Pharma hackathon presentation.
Content is sourced from `../PITCH.md` (do not edit slide copy here — edit
`PITCH.md` and regenerate).

## Output

- `MedCite_Pitch.pptx` — generated, 16:9 widescreen, opens in PowerPoint /
  Keynote / Google Slides / LibreOffice Impress.

## Regenerate

From the repo root:

```powershell
.\backend\.venv\Scripts\python.exe deck\build_deck.py
```

(`python-pptx` is installed in the backend venv. If you nuke the venv,
re-install with `pip install python-pptx`.)

## Slide map

| # | Slide | Source |
|---|---|---|
| 1 | Title — "MedCite — clinical Q&A that never hallucinates" | `PITCH.md` §1 |
| 2 | Problem | `PITCH.md` §2 |
| 3 | What we built (+ screenshot of answered query) | `PITCH.md` §3 |
| 4 | The trust pitch (4 sentences verbatim) | `PITCH.md` §6 |
| 5 | The 7 hard rules | `PITCH.md` §4 |
| 6 | Architecture (two-tier flow) | `PITCH.md` §5 |
| 7 | Live demo placeholder (+ abstention screenshot) | `PITCH.md` §7 + §8 |
| 8 | The numbers | `PITCH.md` §10 |
| 9 | Q&A teaser (top 3 anticipated questions) | `PITCH.md` §9 |
| 10 | Closing | `PITCH.md` §13 |

## Screenshots

The script auto-loads any PNG it finds in `deck/screenshots/`; otherwise
it draws a labeled placeholder. **Drop the files and re-run** —
no code changes needed.

| File | What to capture |
|---|---|
| `screenshots/hero2-empagliflozin.png` | Slide 3. Open <https://abhi04-medcite.vercel.app>, click hero #2 ("Does empagliflozin reduce cardiovascular mortality in HFpEF?"), wait for the answer card with RCT + Review badges, screenshot the answer + first 2 source cards. **Aspect ratio:** ~ 5.5 : 4.6 (slide slot is 5.5″ × 4.6″). |
| `screenshots/hero5-acetaminophen-abstain.png` | Slide 7. Open hero #5 ("Is acetaminophen safe in third trimester pregnancy?"). Wait for the amber abstention screen ("closest match scored 0.45"). Screenshot the full abstention card. **Aspect ratio:** ~ 4.5 : 4.2. |

If the backend is cold, expect the first hero query to take ~30 s while
HF Spaces wakes the container. The frontend will show "Backend warming…"
during this — wait it out, then re-click.

## Brand

Single accent color throughout: **`#0284c7`** (sky-600), pulled from
`frontend/public/icon.svg`. Matches the deployed app, so the deck visually
hands off to the live demo on slide 7.

## Editing tips

- All slide content is in `build_deck.py` as ordinary Python strings
  near the bottom of the file (`slide_1_title` … `slide_10_closing`).
- The 4-sentence trust pitch (slide 4) and the 7 hard rules (slide 5)
  are locked from `PITCH.md` §6 and §4 — don't paraphrase.
- The footer reads "X / 10" — if you add or remove a slide, update the
  footer label arg in each `add_footer()` call.
