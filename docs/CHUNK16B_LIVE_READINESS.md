# Chunk 16B — Identity, Evidence and Demo Readiness (no-cost offline gate)

**Baseline:** `f490ddd` (Chunk 16A merged). **Delivery scope:** `16B.1` local verification only. 16B.2 live verification requires separate explicit approval before any billable cloud deployment or configuration changes.

## What is implemented

- A local-only source SHA256 and configuration preflight, with Windows CRLF normalization. It refuses source drift and checks that the `firestore.rules` browser rules still contain deny-listing and deny-all defaults.
- 20 tests that invoke the *actual* `require_firebase_client()` dependency using controlled Firebase Admin SDK responses (not FastAPI dependency overrides), checking Auth + App Check both required, exact App Check app ID, absent/invalid UID, token rejection, log redaction and no-purchase invariant. These are **mocked SDK** tests, not genuine live token verification.
- Full backend regressions, real Firestore **local emulator** integration (the pre-existing 13B suite), and frontend Vite/TypeScript build.
- No code modification to the existing API, frontend, IAM, Firestore, or cloud resources; no environment flags changed.

## How to run on Windows CMD

Extract the ZIP to `D:\AiBuilderCup\needproof-ai` (merge paths; keep tracked source files intact). **Do not deploy.**

```cmd
cd /d D:\AiBuilderCup\needproof-ai
call backend\.venv\Scripts\activate.bat
python scripts\preflight_chunk16b.py --check
scripts\verify_chunk16b.cmd
git diff --check
git status --short
```

The verification script runs the 16B focused tests, the complete backend test suite, the existing Firestore emulator E2E suite, and the frontend build. It may download a Firestore emulator JAR on the first run. Use Java 21+ with Firebase CLI; the user has already installed these. No Firebase project login is needed for demo-project emulator tests.

**If verification passes**, commit only the four named files:

```cmd
git add backend/tests/test_cloud_16b_security_gate.py scripts/preflight_chunk16b.py scripts/verify_chunk16b.cmd docs/CHUNK16B_LIVE_READINESS.md
git diff --cached --check
git diff --cached --stat
git commit -m "Complete Chunk 16B1 offline identity and evidence release gate"
git push origin main
git log -1 --oneline
```

Do not use `git add .`: previous abandoned Cloud SQL experiment files, 13B emulator utilities, backups, and generated reports remain untracked. Your `f490ddd` HEAD can be a descendant on subsequent reruns; the source fingerprints still prevent silent changes to security-critical files.

## Real live gate — not performed by this package

1. **Provider cost/scope approval:** Obtain explicit approval if running Cloud Build, Artifact Registry, Cloud Run new revisions, Places, Vertex AI or any potentially billed resource. Existing `needproof-ai` project has billing enabled; budget alerts are not a hard spend cap. Set effective quotas and backend request limits where supported.
2. **Confirm account configuration read-only:** Firebase showcase Auth anonymous and merchant sign-in settings, App Check registration/enforcement, correct web app ID, Cloud Run service identity, CORS allowlist, and Firestore database project. Do not print/commit token values, service account keys, client secrets or environment dumps.
3. **Cross-project Firestore:** Previously granted conditional `roles/datastore.user` to `needproof-decisions@needproof-ai.iam.gserviceaccount.com` in `needproof-ai-showcase` is not proof of connectivity. Test least-privilege access and correct project/database with approved test-only identities. Firestore client rules protect browsers, **not service-account IAM**; the backend must enforce ownership and merchant grant checks.
4. **Tagged preview must not shift public traffic:** Build from `backend/` (not repository root). `--no-traffic` avoids moving normal service traffic but a tagged URL may still be reachable and may incur runtime charges. Require authentication, guard access, constrain instances/calls and obtain explicit approval first. No preview automatically initiated here.
5. **Real browser test:** Use actual Firebase Auth ID token **and** actual App Check token generated in the authorized browser, through the deployed UI, without exposing tokens. Check valid call 200 only for enabled protected endpoint and authorized user; missing/wrong app token 401; wrong user rejected; CORS from correct Hosting origin; no token in logs.
6. **Evidence test:** With operator-approved fictional merchant/test identities, verify customer inquiry ownership, merchant grants, denied cross-merchant access, append-only revisions, and stock-out replan against the correct Firestore project. Never treat a report as independent stock verification or purchase approval.
7. **Rollback:** Preserve last known good revision, allow zero-traffic preview removal / feature flag off, confirm customer path unchanged. Have a stop procedure and eventual decommission plan when the demo period ends.

**Current judge-facing status:** 16A is a high-fidelity **fictional** decision walkthrough demonstrated locally. New 13B/13C/14A/14B tools are not proven production-accessible by this package. A Cloud Run revision / Firebase Hosting push is never implied by a GitHub push.
