# Chunk 17B — Genuine Gemini Intent Intelligence / Secure Integration

Baseline: audited Git commit `7db48ca`. This package edits **only** four existing Python files and adds new tests/tools. No browser UI, Firebase hosting, Cloud Run config or GCP deployment is touched.

## Existing code reused
- `backend/app/services/intent_service.py` already calls Google GenAI SDK with `vertexai=True`, Gemini `gemini-2.5-flash` by default, `response_schema=ExtractedIntent` and `status=extracted_unverified`.
- `backend/app/api/intent.py` already exposes a local testing route; that *legacy* route must not be used as a public paid-model route.
- `backend/app/cloud_decision_api.py` already implements real Firebase Auth + App Check verification. 17B adds a **new protected, feature-flagged** intent endpoint.
- `frontend/src/FreeShowcase.tsx` independently uses Firebase AI Logic when configured. Its genuine live behavior is not verified by this backend test. 17C will unify browser-to-Python execution.

## Code / HTTP change
`POST /api/v1/ai/intent/extract` (on isolated Cloud Run FastAPI app):
- Requires valid Auth ID token **AND** App Check; absent/invalid => HTTP 401.
- `NEEDPROOF_INTENT_17B_ENABLED` defaults to **false**; even with valid credentials => HTTP 503 unless deliberately enabled.
- Body `{ "text": "Need 65W USB-C charger under ₹1000 in Thane today" }`.
- Mocked success => HTTP 200, `status=extracted_unverified`, explicit missing device details and `compatibility_needs_verification=true`.
- Schema/grounding error => HTTP 502; missing live Vertex configuration => HTTP 503; invalid input => 422.
- The old `app.main` `/api/intent/extract` route now refuses HTTP requests in `ENVIRONMENT=production` (HTTP 403).

## What the guard validates and what it cannot
- Enforces explicit numeric budgets (including INR, Rs, rupees), literal location if present, explicitly stated numeric specifications, and compatible products remain unverified.
- Caps model output tokens and structured response sizes, and avoids logging raw SDK exceptions/user text.
- Conservative validation can reject legitimate multilingual paraphrases or number words. Those are known limitations, not secretly corrected by a heuristic. We will test them and refine only on evidence.
- **This is not proof against all hallucinations**. Product-brand identity, merchant stock and product-document citations must be corroborated in later chunks.
- No new Firestore state, merchant contact, purchases or shopper tracking.
- This chunk does not provision per-user distributed rate-limiting, quotas or billing caps. **DO NOT enable this new paid endpoint on a public deployment before a separate spending/security review and explicit approval.**

## 17B tests/expected outcomes
Run `scripts\\verify_chunk17b.cmd` on Windows after applying. Offline mocks guarantee no real Gemini/network request. Expect original intent regression tests to pass, new service tests to pass, plus cloud security and 15A tests. It writes `qa_reports\\17b\\mocked_intent_trace.json` labeled `MOCKED_GENAI_SDK_NO_NETWORK`.

## Business-judge scope
Primary example: urgent 65W USB-C PD charger ≤ ₹1000 near Thane. The value proposition is less effort to describe requirements and targeted clarification about compatibility. 17B cannot claim faster purchases, prevented wasted journeys, merchant validation, or accuracy improvement; these require measurements in 17F and 18A. For business acceptance, document ambiguity handling on English and Indic-language inputs.

## Controlled live follow-up (NOT part of offline verification)
Once you explicitly authorize live Google charges, agree on a hard budget/quotas, determine which existing auth path to use, and complete the production security review, we can run a few controlled Vertex requests and log redacted result/timing/token totals. The mocked trace is not a live demonstration.
