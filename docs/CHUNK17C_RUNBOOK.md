# NeedProof Chunk 17C — Fresh Python decisions with visible what-if evidence

Baseline: tracked commit `68f1670`. This package has no Firebase or Google Cloud deployment instructions and never enables paid AI services.

## Purpose

- Fresh product/budget and explicitly *fictional* merchant evidence go from React through an actual HTTP request to Python's `orchestrate_decision_14a3`.
- The reported offer, stock-out, and no-merchant cases are recomputed on every request. Stock-out comparison uses *hypothetical* previous state, NOT stored merchant history.
- Five-stage trace contains `NOT_PROVIDED` for stages lacking evidence; never mark document review, Bayesian EVSI or basket solving as executed when not supplied.
- Real merchant inventory, discovery by location, historical records, Gemini calls, Firebase production auth and hosted integration are NOT proven in 17C.

## Security

- **Local development:** `/api/v1/demo/fresh-journey` under `app.main` returns HTTP 403 by default; only accepts local 127.0.0.1 / ::1 clients, when `ENVIRONMENT=development` and `NEEDPROOF_17C_LOCAL_ENABLED=true`. Uvicorn script binds `127.0.0.1` only.
- **Cloud Run app:** same endpoint in `cloud_decision_api` requires `require_firebase_client` (ID token + App Check) and an explicit `FRESH_JOURNEY_17C_ENABLED=true`; otherwise HTTP 401 or 503. Do not enable cloud route until cost, operational and security reviews. No tests override production auth.
- **Frontend:** public showcase uses offline replay as before. The new fresh panel becomes usable in local dev when Vite launches with `VITE_NP17C_LOCAL_DEV=true`. Cloud mode additionally requires explicit `VITE_NP17C_CLOUD_ENABLED=true`, a nonempty API URL and Firebase client configuration. `import.meta.env.DEV` guards local bypass from production builds.

## Windows CMD (use separate windows)

1. `cd /d D:\AiBuilderCup\needproof-ai`
2. `backend\.venv\Scripts\python.exe scripts\apply_chunk17c.py --check` — DRY RUN; stops if tracked source drifted or staged targets changed.
3. `backend\.venv\Scripts\python.exe scripts\apply_chunk17c.py --apply` — backs up existing files in `.git\needproof_patch_backups\17c`; doesn't touch existing untracked files.
4. `scripts\verify_chunk17c.cmd` — expects backend regressions, trace, and a Vite build. If frontend node_modules is absent run `cd frontend && npm ci` only if you're comfortable fetching packages, then `cd ..` and retry.
5. In **CMD Window A**: `scripts\run_chunk17c_backend.cmd` — leave running. It binds only `127.0.0.1:8000`.
6. In **CMD Window B**: `scripts\run_chunk17c_frontend.cmd` — leave running. Open `http://127.0.0.1:5173` and find **Chunk 17C — Fresh decision execution** below Judge Replay.

## Manual acceptance

1. Check fictional evidence acknowledgement and press **Execute fresh Python decision** with product `65W USB-C PD charger`, budget `1000`, fictional price `720`, `reported_offer`. Expect `PROVISIONAL_VERIFICATION_NEEDED`, five trace rows, purchase NO.
2. Change merchant report to `stockout`, submit again. Expect `MORE_EVIDENCE_NEEDED`, hypothetical change event `CLIENT_EVIDENCE_CHANGED`, no selected store.
3. Change merchant report to `no_merchants`, submit. Expect `DISCOVERY_NEEDED`.
4. Set report to `reported_offer` again and change budget to `300`, submit. Expect `MORE_EVIDENCE_NEEDED` because the 720 INR fictional report exceeds budget.
5. Change product to `45W USB-C charger`, price to `250`, budget `600`, submit. Expect fresh calculation and different `Snapshot SHA-256`. Location field is a note only, NOT Places discovery.
6. Ensure public hosted Firebase URL and deployed API are unchanged. No cloud spend introduced by this patch.

## After green verification

Stage **only** the new application files and regression artifacts from this chunk, never `git add .`. One-time installer and `chunk17c_payload` stay untracked and should not be pushed. Re-run `scripts\verify_chunk17c.cmd` after committing.

## Business acceptance

The customer can correct a request and see the consequence immediately; simulated stock changes are reflected in decisions rather than frozen presentation JSON. This is **not** empirical evidence of merchant adoption, saved shopping time, accurate stock, monetary savings or live Gemini connectivity. Those stay on the locked 17D–18C roadmap.
