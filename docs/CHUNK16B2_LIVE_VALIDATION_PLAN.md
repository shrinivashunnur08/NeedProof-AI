# NeedProof AI — 16B.2 Readiness and Live-Validation Plan

**Commit prerequisite:** `e71f91e` or descendant, with the 16B.2A offline release gate passing.  
**Scope today:** offline audit only. No deploy, new revision, live token request, new Firestore writes, new IAM permission, or Gemini/Places usage.

## Why this gate exists

The 16B.1 tests exercise the real `require_firebase_client` dependency with *mocked Firebase Admin SDK responses* and validate Firestore persistence with a local emulator. That **does not** validate real browser-issued Firebase ID tokens, reCAPTCHA Enterprise App Check tokens, cross-project service-account access, hosted CORS, user access boundaries in the live database, or live functionality of the new feature-gated endpoints. The final 16B.2 stage will establish those properties **only with explicit approval** for potential cloud charges.

The current `needproof-ai` Cloud Run/Places project is billing-enabled. `needproof-ai-showcase` hosts a Firestore `(default)` database with free-tier eligibility, but Firestore free-tier allowances are not proof that unrelated billable resources are cost-free. **Cloud budgets are alerts, not hard stops.** A tagged `--no-traffic` Cloud Run revision can still receive traffic and potentially incur costs. `git push` does not deploy.

## Gate 0: no-cost source preflight (run now)

```cmd
cd /d D:\AiBuilderCup\needproof-ai
call backend\.venv\Scripts\activate.bat
python scripts\preflight_chunk16b2.py --check
scripts\verify_chunk16b2.cmd
python scripts\preflight_chunk16b2.py --print-live-plan
git diff --check
```

Do not run `gcloud run deploy`, `firebase deploy`, `gcloud projects add-iam-policy-binding`, or enable `MERCHANT_EVIDENCE_ENABLED` as part of this gate. The old Cloud SQL files, emulator scripts, and benchmark reports must remain untracked unless independently audited.

## Gate 1: explicit approval before making real service calls

The owner must explicitly decide whether **any possible additional use-based charges** are acceptable. If the requirement is **strictly no additional cloud charges**, do not run the live gate; retain a clearly labeled local-only 16A demo and continue with 16C local visual/demo polish.

If potential usage charges are approved, first inspect (read-only) the current Cloud Run configuration, Firebase project/app settings, effective provider quotas and budgets, Firestore database location and permissions, and the ability to roll back. Never put credentials, OAuth tokens, Firebase ID tokens, App Check tokens, or service-account keys in a CMD transcript, Git file, or chat. Do not use service-account key files.

## Gate 2: existing hosted app, real token flow (separately approved)

Use a dedicated synthetic test account *inside the existing authorized hosted UI*. The existing client `frontend/src/lib/cloudDecisions.ts` signs in through Firebase Auth, obtains `user.getIdToken()` and `getToken(appCheck)`, and sends both headers. The API `require_firebase_client` checks the ID token, App Check token, and exact `FIREBASE_WEB_APP_ID`.

Verify, without copying token values: (1) intended Hosting origin; (2) correct authorized API response to a currently live, protected, low-cost endpoint, such as the existing `/api/v1/decision/replan`; (3) missing/invalid Auth and missing App Check each rejected with 401; (4) App Check app mismatch rejected; (5) non-allowed origin rejected by browser CORS; (6) no tokens logged or persisted. Do not export browser HAR files with Authorization headers. Public `/health` alone proves none of these. If browser CORS blocks a localhost origin, do not weaken the production origin allowlist to make the test work.

The production revision previously identified as `needproof-decision-api-00003-mx8` might no longer be the current revision; determine the actual ready and serving revision before testing. **Do not claim new 16A/14B endpoints are live:** their release flags are still off and newer Git commits do not deploy them.

## Gate 3: real database + merchant controls (separately approved)

After role/identity checks and a very small synthetic dataset with explicit retention/cleanup, verify: customer inquiry ownership; cross-user 404; operator-approved merchant grant only for the exact place; cross-merchant denial; append-only revisions; stock-out replan; no purchase authorization; and correct Firestore `(default)` project. Browser Firestore rules do **not** restrict service-account Firestore writes; backend authorization remains essential. Conditional `roles/datastore.user` binding alone is not evidence of working database access. No real merchants should be contacted.

## Gate 4: controlled new revision (separately approved)

If a new image is genuinely necessary, deploy from `backend/` *only* after approval for possible Cloud Build, Artifact Registry, Cloud Run runtime and ancillary costs. Preserve original env, service account, auth controls, ingress, allowed origins, traffic and ready revision. Use a zero-traffic tagged revision for restricted smoke validation; verify public traffic never shifts until explicitly authorized. Set min instances to zero where compatible and enforce supported per-service provider quotas. Roll back by removing preview access and disabling new flags; verify serving revision remains healthy.

## Gate 5: actual demo and shutdown

The hostable judge walkthrough should show the source of each claim, distinguish reported from verified and synthetic from real data, present failures cleanly, and not promise stock, savings or accuracy from hand-authored benchmark fixtures. Test on desktop/mobile, include failure/latency footage and one recovery path, then document all resources to be disabled when the 3–4 month evaluation period ends.

**Decision at end of 16B.2A:** OFFLINE GATE ONLY. Live real-token & deployed Firestore validation remain open until separately authorized, executed and reported.
