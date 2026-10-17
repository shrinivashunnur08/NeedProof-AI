# NeedProof AI — Engineering Handoff / Current Status

**As of 17 October 2026** · Current pushed main: **`4874ff7`** (`Add Chunk 17F reproducible competitive benchmarks`)  
**Repository:** `https://github.com/shrinivashunnur08/NeedProof-AI` · **Local Windows checkout:** `D:\AiBuilderCup\needproof-ai`  
**Purpose:** Align parallel contributors on the actual verified state, unfinished work, business case, and nonnegotiable evidence/safety requirements.

## Product position

**NeedProof AI: evidence-driven local commerce decision intelligence.** Core user: a buyer needing an urgent, specification-sensitive product (example: a compatible 65W USB-C PD charger, below ₹1,000, in Thane). Instead of treating store listings as proof of stock, NeedProof records the origin and verification status of claims, detects contradictions, recommends what to verify next, and revises the decision when the supplied evidence changes. Merchant-facing forecasting, segmentation, inventory and BI are supplementary modules.

## Starting point (before Chunk 17A)

The repository already had a React/Vite showcase, FastAPI/Python decision architecture, Gemini integration code, local Places discovery, merchant-evidence routes, 13C grounded document retrieval, 14A Bayesian EVSI and basket/orchestration engines, 14B retail intelligence, security testing, lazy loading and a scenario-based offline Judge Replay. Firebase Hosting was published, but the public replay was based on checked-in earlier engine results; hosted end-to-end Gemini → Auth/App Check → Cloud Run → persistent merchant evidence was **not verified**. These earlier features were **not implemented from scratch** by 17A–17F.

## Completed upgrade chunks (all pushed to `main`)

| Chunk | Latest commit | What was built / verified |
| --- | --- | --- |
| **17A — Reality & business audit** | `7b04ca4` and `7db48ca` | Source audit; explicit target-customer/merchant hypotheses, KPIs and baseline plan; offline Python/FastAPI trace; auth TestClient 401/200; Windows socket guard repair. |
| **17B — Structured Gemini intent safety** | `68f1670` | Stronger structured intent schemas, output grounding/validation, authenticated **disabled-by-default** model endpoint, legacy route protection; 57 offline tests. **Live Gemini was not called.** |
| **17C — Fresh React → Python** | `1a27376` | Manual customer input to local FastAPI and real Python orchestration, fictitious stock-out replan and five-stage trace; browser verified; 63 tests and Vite build. |
| **17D — Evidence Passport** | `8f22481` | Per-claim provenance/fingerprints, missing evidence, fictional document contradictions, research conflict display; 96 tests and Vite build. |
| **17E — Next-Best-Proof** | `11c5e01` | Verification priority queue, hypothetical uncalibrated EVSI from existing 14A.1, fictional merchant stock-out/restock and replanning; 125 tests and Vite build. |
| **17F — Competitive synthetic benchmarks** | **`4874ff7`** | 40 hand-authored fictional cases × 4 policies; CSV/JSON/Markdown/local HTML; 91 tests, 160 first-pass evaluations and Vite build after commit. |

**Current benchmark (authored fixture, not external ground truth):** NeedProof 40/40 correct states and 0 unsafe provisional selections; price-only 25/40 and 15 unsafe selections; stock+budget 33/40 and 7 unsafe selections; **strong structured evidence rules 40/40 and 0 unsafe selections (tie)**. No measured superiority over the strong rules baseline. No actual trips saved, conversion lift, live LLM-only comparison or field cost savings established. Local microsecond timings exclude model/network and cannot represent production request latency.

## What the 17A–17F code really does today

- A locally running React app sends fresh, user-entered product/budget values plus **fictional** merchant states to FastAPI and gets freshly computed Python decisions. Stock-out and contradiction scenarios were demonstrated in a browser.
- Evidence Passport labels source claims as fictional/unverified and displays conflicts; content hashes are fingerprints **not proof of authenticity**.
- Next-Best-Proof prioritizes safety-first verification actions; associated EVSI values use **illustrative, uncalibrated assumptions**; no actual merchant gets contacted.
- A standalone local benchmark report is generated from reproducible authored data. The dashboard is **not yet integrated** into the public React judge-facing journey.
- Local tests and production frontend builds pass, but hosted live invocation of Gemini, Cloud Run, Firebase Auth/App Check and cross-project IAM remains unverified.
- Git pushes do **not** deploy the updated frontend or backend; Firebase Hosting last publication predates these new upgrades.

## Pending: locked roadmap (four chunks)

| Priority | Chunk | Acceptance focus |
| --- | --- | --- |
| **NOW** | **17G — Unified judge experience, safety & release quality** | One coherent narrative, visible separation of live/mocked/synthetic status, benchmark comparison with honest caveats, accessibility/mobile/performance, Auth/App Check and error-state regression, release checklist. Integrate without rewriting working algorithms. |
| Next | **18A — Realistic user/merchant validation** | Obtain consent and actual feedback if feasible; diverse unseen and adversarial shopping cases; measure participant effort and merchant workflow feasibility. If no real pilot, clearly report limitation. |
| Next | **18B — Engineering and economic proof** | Ablations (evidence engine vs rules and key features), latency/cost per genuine run if explicitly approved, error rates, identity authorization and resilience; present real vs simulated metrics separately. |
| Final | **18C — Competition deliverables & code freeze** | Proven deployed journey if approved, security readiness, reproducible repo, architecture, presentation/PDF, truthful demo video and rehearsed technical + business defense. |

## Critical blockers to world-class judge readiness

1. **Real Google GenAI:** structured extraction integration exists but no controlled live Gemini execution proof (cost approval and credentials required).
2. **Hosted connected experience:** local React/FastAPI verified, production browser → secured Cloud Run with Auth/App Check and database IAM **not verified**. Never silently enable public paid routes.
3. **Real retailer/customer validation:** no authenticated merchants, measured stock accuracy, verified products, observed shopper outcomes or merchant adoption yet.
4. **Strong-baseline tie:** controlled benchmark shows NeedProof ties structured rules on authored cases. Need *unseen* cases, meaningful ablations and practical workflow advantages; don't cherry-pick.
5. **Judge UX:** fragmented feature surfaces and a >500 kB `FreeShowcase` bundle warning; prioritize comprehensibility, accessibility and measured performance.
6. **Cost controls:** no paid cloud services, model calls, Firestore operations or deployments without explicit approval and safeguards.

## Suggested collaboration split

- **Owner A — Core backend/evidence/security:** 17G integration contracts, Python integrity/tests, Auth/App Check tests and feature flags. Do not weaken production authentication to make local demos pass.
- **Owner B — UX and performance:** responsive layout, accessibility, presentation-quality unified journey and frontend performance. Work in `feature/17g-ux` (or equivalent) and preserve existing 17C–17E request/response types; coordinate any edits to `frontend/src/FreeShowcase.tsx` before applying guarded installers.
- **Joint review:** benchmark claims, external-data provenance, regression suite, merged PR and screenshots. Keep 17F dataset and reporting readable; don't delete inconvenient baseline failures.

**Coordination protocol:** start from `main` commit `4874ff7`; use separate branches and PRs, reserve touching shared files until agreed; run the scoped verification commands plus the React build before merging; keep `.env`, credentials, generated `qa_reports`, backups and patch payloads out of Git. Never `git add .` or `git reset --hard` on the working checkout.

## Verification / developer startup

```cmd
cd /d D:\AiBuilderCup\needproof-ai
git log -1 --oneline
scripts\verify_chunk17f.cmd
```

Local React/FastAPI (two separate CMD windows):

```cmd
scripts\run_chunk17c_backend.cmd
```

```cmd
scripts\run_chunk17c_frontend.cmd
```

Open `http://127.0.0.1:5173`. Enter a fictional merchant report of 1 unit and then 0 units; check that state changes from `PROVISIONAL_VERIFICATION_NEEDED` to `MORE_EVIDENCE_NEEDED`, the purchase gate stays false, and the Evidence Passport/Next Best Proof explain why. Choose conflicting fictional USB-PD excerpts and check `RESEARCH_CONFLICT`. A demo is not evidence of real stock.

## Short team summary

**NeedProof is past the “UI concept only” stage.** We now have tested, locally executable fresh decisions, an evidence provenance and contradiction layer, a safety-first verification queue, and reproducible synthetic comparison reporting. **We do not yet have proven live Gemini execution, hosted secure end-to-end integration, or real commercial validation.** The priority is not more disconnected features; it is a cohesive, truthful judge journey plus measurable independent value and reliable deployment.
