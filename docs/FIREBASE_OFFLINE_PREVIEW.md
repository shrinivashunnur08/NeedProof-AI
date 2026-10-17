# NeedProof — Offline Firebase preview fix

**Baseline:** `f765eff` plus applied Chunk 16C.4 route split. The installer fingerprints only `frontend/src/FreeShowcase.tsx` and `frontend/src/lib/cloudDecisions.ts`.

## Why

The showcase automatically calls `loadJourney()` on page mount. `firebaseShowcaseClients()` requires four Vite `VITE_` values (Firebase project, API key, web app ID, App Check reCAPTCHA Enterprise site key). When absent it throws the misleading `.env.production.local` error during `npm run dev` (dev mode reads `.env.local`, not `.env.production.local`).

## What changes

Only those **two tracked TS/TSX** files change. Local unconfigured Firebase becomes clearly labeled an offline preview; the three Firestore save/restore/delete buttons and live Gemini extraction are disabled; no automatic Firestore Auth, App Check, or Firestore read is attempted when config absent. The checked-in four-case 16C.2 replay remains visible. When all four values exist, the previous Firebase logic remains in place and genuine network errors remain visible; merely supplying values does not prove Firebase works. Cloud Run opt-in and backend security remain unchanged. No localStorage impersonates Firestore.

## Commands from repo root (after extracting ZIP)

```cmd
cd /d D:\AiBuilderCup\needproof-ai
backend\.venv\Scripts\python.exe scripts\apply_firebase_offline_preview.py --check
backend\.venv\Scripts\python.exe scripts\apply_firebase_offline_preview.py --apply
scripts\verify_firebase_offline_preview.cmd
```

Preview in a second CMD:

```cmd
cd /d D:\AiBuilderCup\needproof-ai\frontend
set VITE_PUBLIC_SHOWCASE=true
npm run dev
```

Refresh the local browser; header reads "Offline preview" and Firestore shows a calm explanatory message, no red missing-configuration error. Save/restore/delete and live Gemini are disabled until real configuration is provided.

## How to use LIVE Firebase **only if you want it**

In `frontend/.env.local` (local only, **never commit**), add the actual project config values supplied by *your* Firebase Web App console:

```
VITE_FIREBASE_PROJECT_ID=YOUR_ACTUAL_PROJECT_ID
VITE_FIREBASE_API_KEY=YOUR_ACTUAL_FIREBASE_WEB_API_KEY
VITE_FIREBASE_APP_ID=YOUR_ACTUAL_WEB_APP_ID
VITE_FIREBASE_AUTH_DOMAIN=YOUR_ACTUAL_AUTH_DOMAIN
VITE_FIREBASE_MESSAGING_SENDER_ID=YOUR_ACTUAL_SENDER_ID
VITE_APPCHECK_SITE_KEY=YOUR_ACTUAL_RECAPTCHA_ENTERPRISE_SITE_KEY
```

The values above are **examples only**. Never add a service-account JSON, admin SDK key, or private secret to Vite `VITE_` variables. Re-start Vite after changing env values. Check allowed Firebase Auth domains, anonymous Auth, App Check site/domain registration, and Firestore rules **without enabling new paid services**. Real network calls and charges are possible; do not configure or test these until you approve the live path. Any `VITE_CLOUD_DECISION_API_URL` enables opt-in live backend requests; leave it unset for an isolated preview. Do **not** disable App Check to work around token failures.

## Staging after verification

```cmd
git add frontend/src/FreeShowcase.tsx frontend/src/lib/cloudDecisions.ts scripts/apply_firebase_offline_preview.py scripts/verify_firebase_offline_preview.cmd backend/tests/test_firebase_offline_preview.py docs/FIREBASE_OFFLINE_PREVIEW.md
git diff --cached --check
git diff --cached --stat
```

Also stage the pending 16C.4 files **separately** as previously instructed, if that commit hasn't been pushed. Ignore `backup_firebase_offline_preview/`, qa reports, old untracked experiments. Do not use `git add .`.
