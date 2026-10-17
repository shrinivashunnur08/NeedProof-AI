# Chunk 17A — Developer and Business Jury Walkthrough

## What we're establishing

We are not rebuilding NeedProof from scratch or installing more cloud services. Starting point: existing codebase at `c753fd6` or a descendant, which includes the deployed React judge showcase, offline four-case replay, the 16A Python guided-journey engine, forecasting, segmentation, inventory intelligence, and security contract/emulator tests.

**What this chunk changes:** only new audit, report-generation, test, guide, and runner files. No changes to `frontend/src`, `backend/app`, `firestore.rules`, `firebase.json`, Cloud Run, Firebase Hosting or `.env`.

## Technical terms for a developer

- **Static source wiring**: Code contains a client call, route, or verification function. It may not have run in production.
- **Offline replay**: React renders JSON computed from Python earlier. Selecting a card produces no new Python invocation.
- **Local engine execution**: Python recalculates a decision in memory from a controlled scenario.
- **In-process FastAPI TestClient**: Real application routing in a Python process, NOT an externally reachable deployment. Auth may be overridden in a test-only dependency, and does not demonstrate real Firebase verification.
- **Live hosted integration**: Requires valid ID/App Check tokens, live authorized Cloud Run response, accurate CORS and verified Firestore IAM. This chunk does not perform that test.

## Developer flow to trace

For `reported_offer`, the fixture reports a plausible charger candidate, then `evaluate_guided_journey_16a` runs five stages: merchant replanning, cited document retrieval, hypothetical evidence planning, synthetic basket optimization and final policy boundary. The state should be `PROVISIONAL_VERIFICATION_NEEDED`, with `purchase_allowed=false`.

For `stockout`, the report changes to zero stock and the decision should be `MORE_EVIDENCE_NEEDED`. For `document_conflict`, contradictory specifications yield `RESEARCH_CONFLICT`. For `no_merchants`, the engine returns `DISCOVERY_NEEDED`. No case contacts a real merchant, places an order, or invokes Gemini.

The trace runner also exercises one local FastAPI route: request without token should reject with HTTP 401; a separate test-only identity override should allow HTTP 200. This is **not** a production authentication check.

## Step-by-step local verification

1. `python scripts\audit_chunk17a.py --check`: read-only inspection of pre-existing source, four JSON replay scenarios, Auth/App Check source checks and hosting manifest (no env values read).
2. `python scripts\business_chunk17a.py --check`: validates the market hypothesis, merchant incentive, business questions, comparators, and seven unmeasured KPIs.
3. `scripts\verify_chunk17a.cmd`: runs focused tests, creates three reports, traces real local Python and FastAPI execution.
4. Open `qa_reports\17a\reality_audit.md`, `qa_reports\17a\business_readiness.md`, `qa_reports\17a\backend_trace.json` and inspect what is present versus unverified.

## 17A accepted business model (hypothesis only)

- **Customer:** user who urgently needs a *compatible* product locally (starting with laptop accessories).
- **Pain:** a wasted trip can occur if availability or compatibility is assumed without sufficient evidence.
- **Merchant:** can offer reported stock and evidence, but needs an incentive to keep claims current.
- **Value:** explain the credibility limits, flag contradictions, and select which missing fact to verify next.
- **Competitive moat to prove:** fewer unsupported recommendations *while still making useful decisions* compared with simple cheapest-only or rule-only baselines.
- **Revenue hypothesis:** merchant lead subscription/verification and analytics; not established demand or revenue.

## Test cases and expected outputs

| Test | How | Expected |
|---|---|---|
| T01 project source health | `audit_chunk17a.py --check` | PASS unless source changed; otherwise `NEEDS_INSPECTION` |
| T02 browser replay | Static source/replay audit | Four fictional scenarios and no purchase permission |
| T03 API Auth/App Check | Source check | Guard functions/headers present (not proof of real tokens) |
| T04 supplier claim | Local engine | `PROVISIONAL_VERIFICATION_NEEDED`, purchase false |
| T05 merchant stock-out | Local engine | `MORE_EVIDENCE_NEEDED`, purchase false |
| T06 contradictory specs | Local engine | `RESEARCH_CONFLICT`, purchase false |
| T07 no merchant reports | Local engine | `DISCOVERY_NEEDED`, purchase false |
| T08 unauthenticated local HTTP | FastAPI TestClient | HTTP 401 |
| T09 test-only local authenticated dispatch | TestClient with dependency override | HTTP 200, engine response, purchase false |
| T10 13C/14B real Python | Trace supplemental mode | Retrieval, forecast, cohorts, inventory, BI outputs produced from synthetic inputs |
| B01 defined primary shopper and merchant persona | Business preflight | Both exist, flagged as hypothesis |
| B02 competition comparator plan | Business preflight | Cheapest, basic rules, NeedProof modes present |
| B03 evidence metrics validation | Business preflight | 7 KPIs show `NOT_MEASURED`, no invented values |
| B04 fake benchmark number rejection | Unit tests | Unsupported metric values cause test failure |
| B05 business risk review | `business_readiness.md` | Merchant participation, false stock confidence, costs, biased evaluation listed OPEN |

## Interpreting expected output

`PASS: ...` means local source or execution contract passed; it does not mean that public Gemini or merchant data were validated. Any exception, mismatch, 200 when an unauthenticated request should get 401, or any purchase authorization from synthetic evidence is a blocker. Stop and share the exact output.

## Review competitive business readiness

Open `docs/CHUNK17A_JURY_SCORECARD_AND_RESEARCH_PLAN.md` before 17B. It converts the technical roadmap into proof obligations for both technical judges and experienced retail/product managers.

## What remains once 17A passes

17B needs a fresh validated Gemini call; 17C needs one new decision to actually reach the Python engine from React; 17D/E must expose provenance and useful verification; 17F/18A/18B must measure real comparative/customer/business value; 18C finalizes deck/video. No feature should be claimed 'live' merely because a frontend card displays output.
