# NeedProof AI — fixed development scope and judge outcome gates

> Working plan for the global AI Builder Cup. The goal is a globally competitive, evidence-based prototype. **95+/100 is an internal stretch goal, not a measured official judging score and not a shortlisting assurance.**

## Competing evaluation perspectives

Technical jury: Does Google GenAI actually execute for a fresh input? Does a real backend recompute after evidence changes? Can code, credentials, and provenance be audited? Do controlled tests show meaningful advantage over simpler methods? Does security work when an attacker sends unauthorized calls?

Senior retail/product manager: Whose expensive problem is this? How often does it occur? Why would shoppers switch? Why would merchants respond? How long does an evidence update take? Who pays? What is cost per useful decision? How does this differ from existing local inventory and AI shopping products?

## Primary positioning and wedge

Target **urgent, specification-sensitive local electronics shopping** first. Use a 65W USB-C PD charger (budget <= INR 1000) as one coherent product journey. Store discovery alone is common; NeedProof's defensible claim is **evidence provenance + conflict detection + next-best verification + safe decision revision**. Discovery listings are not stock confirmation. A merchant's own report is a reported claim, not independently verified physical stock.

Support longer-term retail forecasting, segmentation, inventory uncertainty and business intelligence, but keep them secondary to the core buyer-to-proof story. No new algorithm dashboard just to increase feature count.

## Ten locked work chunks

| Chunk | Engineering outcome | Technical acceptance | Business acceptance |
|---|---|---|---|
| 17A | Read-only source reality audit, local FastAPI trace | Actual Python execution + report differentiating replay, local HTTP, hosted path, model calls | Specific customer wedge, merchant incentives, hypotheses, seven defined KPIs and open risks |
| 17B | Fresh Google Gemini structured intent with safe schema and provenance | New prompt actually generates verified schema output; invalid cases rejected. Local mocks precede any approved paid calls | Shopper can describe need quickly; clarify ambiguous device/spec and budget |
| 17C | Connected React -> secured FastAPI -> real Python replan -> React | One newly entered piece of evidence causes actual recomputation and log trace | Faster, actionable 'what next' decision, not static scorecards |
| 17D | Evidence Passport: source, claim type, timestamp, contradictions and freshness | No undocumented claim promoted to verified status; citation and conflict tests | Shopper can understand which evidence to trust and why |
| 17E | Next-Best-Proof, merchant ownership & revision history | Explainable EVSI verification; unauthorized modifications denied; stockout reroutes safely | Low-friction merchant participation and useful leads are tested, not assumed |
| 17F | Fair baseline evaluation, 30–50 cases | Measure unsupported advice, correct abstention and usable decision rate; publish failures | Evidence-driven argument for prevented wasted visits, not inflated synthetic claims |
| 17G | Unified primary journey, accessibility, security and hosted release | Full browser acceptance, cost controls, rollback and auth boundaries | Boardroom-ready 2-minute customer narrative and efficient UX |
| 18A | Small opt-in user/merchant pilot and adversarial edge cases | Reproducible pilot protocol and failure-case results | Actual usability and workflow-effort feedback; sample limitations declared |
| 18B | Latency, cost, resilience and ablations | Quantified timing, per-request spend where measurable and graceful degraded modes | Realistic unit-economics sensitivity and merchant viability narrative |
| 18C | Code freeze, architecture, public demo, deck/PDF, recording, Q&A | Evidence-backed live/demo distinctions and reproducibility | Crisp differentiation, measured impact, credible business model assumptions |

## Strict acceptance rubric

1. No claims of real cloud behavior from static source markers or prerecorded JSON.
2. Fresh Gemini inputs must be observed and schema validated before 'live' is claimed.
3. Unverified evidence can never authorize a purchase or inventory confirmation.
4. Baselines must be evaluated under equivalent inputs and include negative cases.
5. Pilots require prior consent and must not invent merchant collaboration.
6. Real business numbers require an evidence source and proper sample-size caveats.
7. Any cloud calls, deployments, changes to Cloud Run/Firestore/Places, or new spend require explicit approval. Local unit tests/emulators first.
8. The existing hosted site remains unchanged unless approved; preserve rollback readiness.
9. Finish relevant regressions and UX checks before each commit; don't use `git add .`.
10. After 18C: stop feature expansion, finalize presentation and video.

## Which technologies are needed?

Use Google Gemini meaningfully for requirement interpretation/evidence, and existing Firebase Hosting + Cloud Run where authorized. Firebase Auth/App Check/Firestore and Places are integrations to validate—not props to enable just for brand-name appeal. ADK and Agent Platform are optional when genuinely beneficial and should not trigger an unnecessary rewrite.

## What does 17A prove right now?

The audit lists source-level integrations, logs local Python stage transitions, uses FastAPI TestClient with an explicitly TEST-ONLY identity override, and writes a sanitized business hypotheses report. It does **not** verify a public authenticated Cloud Run request or a fresh Gemini model call. Those are 17B/17C milestones after approval.
