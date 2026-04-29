# MedCite Flutter Windows Frontend

This folder contains a Flutter Windows desktop frontend for MedCite.
It keeps the backend API contract unchanged and mirrors the web app's
one-question state machine:

- `idle -> loading -> answered | notfound | abstain | error`
- `notfound -> live -> answered | abstain | notfound | error`

## Why Riverpod + Dio

- **Riverpod**: simple, testable state machine with explicit phases and no hidden mutable globals.
- **Dio**: strong timeout controls and consistent HTTP error handling for desktop networking.

## Project Structure

- `lib/models/` API response models
- `lib/services/` backend config + HTTP service
- `lib/state/` query state + controller
- `lib/screens/` main screen and state rendering
- `lib/widgets/` reusable UI widgets (status chip, confidence meter, source card)

## Backend URL Configuration

Uses `--dart-define`:

- Local default: `http://localhost:8000`
- Production: `https://Tony0489-MedCite-api.hf.space`

Example:

```powershell
flutter run -d windows --dart-define=MEDCITE_BASE_URL=https://Tony0489-MedCite-api.hf.space
```

## Run on Windows

1. Install Flutter SDK and make sure `flutter doctor` is healthy for Windows desktop.
2. Enable desktop support:
   - `flutter config --enable-windows-desktop`
3. Enable Windows Developer Mode (required for plugin symlinks):
   - `start ms-settings:developers`
4. From this folder run:
   - `flutter create .`
   - `flutter pub get`
   - `flutter run -d windows`

If Flutter is not on PATH, run commands with full SDK path.

## Run Modes

### Local backend (default)

Use this when your FastAPI backend is running on `http://localhost:8000`:

```powershell
flutter run -d windows
```

### Hugging Face backend

Use this to connect the app to production backend:

```powershell
flutter run -d windows --dart-define=MEDCITE_BASE_URL=https://Tony0489-MedCite-api.hf.space
```

### Release build (Hugging Face backend)

```powershell
flutter build windows --dart-define=MEDCITE_BASE_URL=https://Tony0489-MedCite-api.hf.space
```

## Manual Test Checklist

- Home screen shows query input, Ask button, hero query chips, backend status chip, refresh button.
- Enter a known local-hit query (e.g., empagliflozin HFpEF) and confirm answer, confidence meter, source cards with PubMed/DOI.
- Enter a local miss query and confirm NotFound state shows top similarity and `Search live`.
- Click `Search live` and verify 3-step progress labels.
- Verify `insufficient_evidence` response renders abstain panel with rephrase action.
- Disable backend or point to bad URL and verify error state shows failure details and retry.

## Notes

- If you want Hugging Face every time, create a shell alias/function for the `--dart-define` command.
- Android SDK warnings in `flutter doctor` can be ignored for this Windows-only desktop app.
