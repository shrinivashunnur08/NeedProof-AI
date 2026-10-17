# NeedProof AI — Chunk 17D Evidence Passport (offline-first)

## Why this matters to judges
NeedProof should not merely recommend a local charger: it should explain why an option is **provisional**, what evidence is missing, and how contradictory documents change the conclusion. A business jury can see proof gaps without understanding Bayesian EVSI. A technical jury can inspect the exact Python source links, local 13C.2 document-review calls, SHA-256 content fingerprints, and fail-closed policy boundary.

## Scope and limits

17D **extends the existing 17C fresh request**, it does not replace the 17B Gemini extraction service, 17C routes, or 14A.3 orchestrator. The Python engine emits an additive `evidence_passport` in `/api/v1/demo/fresh-journey`. The React component displays sources, claims, evidence status, contradictions, and missing verification steps. The new `synthetic_documents` optional field defaults to `not_submitted` for backward compatibility.

**Three document modes:** `not_submitted` (no 13C.2 execution), `matching_fixture` (actual 13C.2 retrieval + conditional review of a server-written fictional USB-PD excerpt), and `conflicting_fixtures` (actual 13C.2 conflicting review and 14A.3 `RESEARCH_CONFLICT`). The two document modes are specifically restricted to illustrative charger requests; they are not a general product catalog or remotely retrieved specifications.

Every source is FICTIONAL. `captured_at` is fixture creation time, **not an observed merchant timestamp**. A SHA-256 fingerprint proves only the exact fixture bytes shown; it does **not** prove that a product spec, merchant, or stock report is authentic. A quotation is a source locator, not a verified product claim. No model confidence percentage is fabricated.

The 17C merchant stock-out is still an illustrative before/after scenario, **not immutable historical evidence**. Do not claim merchant calls, store stock validation, geosearch, real production Firebase Auth/App Check, Firestore IAM, or live Gemini verified in this chunk.

The API routes keep exactly the **existing** auth and feature boundaries. Local-only test on `127.0.0.1`; cloud route remains disabled unless explicitly enabled through prior mechanisms. No paid model, network, storage, or deployment changes.

## Developer sequence (Windows CMD)

```cmd
cd /d D:\AiBuilderCup\needproof-ai
backend\.venv\Scripts\python.exe scripts\apply_chunk17d.py --check
backend\.venv\Scripts\python.exe scripts\apply_chunk17d.py --apply
scripts\verify_chunk17d.cmd
```

Then start the existing 17C local backend and Vite with `scripts\run_chunk17c_backend.cmd` and `scripts\run_chunk17c_frontend.cmd` in separate CMD windows. Open `http://127.0.0.1:5173` and locate the fresh Python decision panel.

**Browser tests:**

1. Fictional stock=1; documents=`No specification documents` -> `PROVISIONAL_VERIFICATION_NEEDED`, Passport has missing compatibility proof.
2. Keep stock=1; documents=`Matching fictional USB-PD excerpt` -> remains provisional, document trace `EVALUATED`, Passport shows specimen source/citations; purchase still NO.
3. Keep stock=1; documents=`Two contradictory fictional USB-PD excerpts` -> `RESEARCH_CONFLICT`, source A/B quoted, proof reconciliation first; purchase NO.
4. Set documents back to none; stock-out -> `MORE_EVIDENCE_NEEDED`, candidate None; purchase NO.
5. Choose no merchants -> `DISCOVERY_NEEDED`, no fictional merchant source promoted.

**Technical exit:** tests pass, local trace file generated, React build passes, all five browser scenarios make actual local API calls. Never present these as real merchant validation.

**Business exit:** Can the viewer say within 30 seconds "I can see where the price/stock claim came from, what is missing, and why contradictory specs stopped the recommendation"? That is our Evidence Passport differentiator. Metrics and real user/merchant pilots remain for 17F/18A.

**Next: 17E** will implement the specific next-best-proof agent/merchant evidence workflow with consent and genuine provenance, rather than granting trust to these fictional examples.
