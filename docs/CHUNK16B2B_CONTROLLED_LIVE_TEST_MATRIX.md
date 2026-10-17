# NeedProof 16B.2B — Production Verification Matrix (not executed)

**Baseline:** `5c8f5f2` or descendant. **Status:** Offline preparation only, zero cloud requests. No real Firebase tokens, no live Cloud Run calls, no Firestore reads/writes, no deployment.

## Decision: What can actually be demonstrated now?

- **Offline verified:** 16A guided journey, synthetic orchestration, purchase safety, offline Auth/App Check contracts, Firestore emulator persistence, 15B synthetic benchmarks.
- **Previously hosted, not newly verified:** Firebase Hosting and existing Cloud Run endpoints; deployed revision may be older than current GitHub main.
- **Not production-proven:** 16A, new analytics modules, deployed merchant Firestore IAM, real merchant authorization, real Auth/App Check exchange across Hosting and Cloud Run.

## Safe local default

```cmd
cd /d D:\AiBuilderCup\needproof-ai
call backend\.venv\Scripts\activate.bat
python scripts\check_chunk16b2b.py --check
scripts\verify_chunk16b2b.cmd
python scripts\check_chunk16b2b.py --plan
```

This emits no credentials and never runs `gcloud` or `firebase deploy`.

## Only after explicit approval for possible usage charges

1. Record the public-serving revision, environment flag *names only*, minimum/maximum instances, traffic allocation and service account. Do not dump full environment values or secrets into chat/logs.
2. Confirm budget **alerts**, effective API quotas, operator-approved synthetic identities, max requests, rollback plan, data cleanup and stop conditions. Budget alerts **are not a financial hard cap**.
3. With a dedicated test identity, use the **existing hosted UI** to request **real** Firebase ID and App Check tokens. Do not print, copy, upload, screenshot or store tokens. Browser DevTools network inspection should redact sensitive headers.
4. Check positive authorization to an **existing enabled protected** endpoint; public `/health` proves nothing. Independently check unauthorized/missing Auth, missing App Check and incorrect app id. Browser CORS must allow only intended origins. Do not disable CORS or App Check to make tests pass.
5. If a new Cloud Run preview is *separately* authorized, deploy from `backend/`, with no public traffic shift and no extra min instances, after confirming its total provider costs and a way to delete the preview. A tagged zero-traffic URL can still receive requests and incur charges.
6. Only after live Firestore evidence mode is enabled and independently approved, test: inquiry owner access; different customer's denial; merchant without grant denied; merchant with exact approved place grant allowed; revision append-only; stock-out update; audit/retention cleanup; `purchase_allowed=false`. One IAM role binding alone doesn't establish these properties.
7. Save **only** sanitized pass/fail outcomes, no tokens or real customer data. Disable preview and new flags upon completion. Confirm production traffic stays on its known-good revision.

## Stop conditions

- Any 401/403 unexpectedly bypassed, wrong customer data accessible, wrong merchant grant, no App Check, broad CORS, actual token visible in logs, unexpectedly enabled feature flag, provider quota missing, potential billing beyond owner approval, or production traffic unexpectedly shifted.
- In the strict zero-new-cloud-spend path **do not perform any steps above**. Proceed directly to Chunk 16C offline UI/demo polish; do not claim live verification.
