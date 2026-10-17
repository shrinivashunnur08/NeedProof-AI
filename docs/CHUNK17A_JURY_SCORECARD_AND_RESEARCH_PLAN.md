# NeedProof AI — Jury Scorecard and Validation Research Plan

**Scope:** internal decision framework, not an official review. No actual shortlisting probability can be derived from this plan.

## Weighted review rubric (as previously identified in the AI Builder Cup materials)

| Dimension | Weight | What our prototype must actually demonstrate | Evidence to present |
|---|---:|---|---|
| Technical merit / GenAI | 40% | Fresh meaningful Gemini input, schema validation, traceable Python replan, secure endpoints, graceful failure | Recorded API trace, real prompt/response with privacy protection, full regression results |
| Impact / problem alignment | 25% | Well-defined electronics shopper problem, merchant value, measurements of time, unsupported decisions, cost | Clearly labeled pilot findings, baseline metrics, constraints, unit economics |
| Innovation | 25% | Evidence Passport, provenance, next-best verification, safe contradiction handling, advantage beyond cheapest-offer rules | Side-by-side comparison showing changed decision when evidence changes, fair benchmarks |
| Experience / integration | 10% | Customer journey clear within first minute, accessible responsive UI, no fake stock claims | Public walkthrough, manual desktop/mobile matrix, user usability observations |

**High score condition:** don't self-award 95+/100 before measuring and reviewing every category. Prior internal score estimates are planning judgments, not official or empirical measurements.

## Business-focused jury challenges and proposed demonstrations

| Jury question | Incomplete answer (avoid) | Better answer (only after proving) |
|---|---|---|
| Who is the customer? | Everyone shopping locally | Urgent, compatibility-sensitive buyer; describe one verifiable purchase scenario |
| Why not Google Shopping or existing retail discovery? | Our AI is more powerful | Evidence quality/contradiction and next-check actions beat specific simpler baselines |
| Where does inventory data come from? | Google Maps shows stores | Store listing is discovery only; merchant submissions are labeled self-reported, with timestamps |
| How do merchants benefit? | Merchants get more sales | Measure qualified leads, submission effort, response cadence, trust and incentives |
| What is the business ROI? | AI saves 50% of the time | Show measured distribution for elapsed time, cost, useful decisions and limitations |
| Is it scalable? | Cloud Run scales automatically | Quantify per-request model/API cost, rate limits, failure recovery, data freshness and merchant onboarding |
| Is the recommendation safe? | AI confidence is high | Show provenance, unresolved questions, contradictions and explicit no-purchase safety boundary |

## Evidence to gather in later chunks

**17B–17C:** a fresh prompt, response schema, Cloud Run/FastAPI request identifier (redacted), actual decision state, and changed result when evidence changes. Test local first; any actual cloud call requires the user's cost approval.

**17D–17E:** provenance, timestamps, verification status, merchant authorship, who may amend a claim, stale evidence behavior and why next check is selected. Merchant report is not independent physical stock verification.

**17F:** 30–50 new cases partitioned by compatible/incompatible hardware, stock-outs, contradictory docs, stale stock, missing requirements and no merchants. Run cheapest-price, simple rules, NeedProof with identical inputs. Include failures. Track both refusal accuracy and useful-decision coverage so an always-refuse algorithm cannot win trivially.

**18A:** optional consent-based micro-pilot with 1–2 merchants and several shoppers, documenting sample limitations; don't claim partnership if no actual participation. Measure whether updates are understood and how long they take.

**18B:** latency p50/p95, error rate, per-request unit cost, model call count, quota behavior, recovery and optimistic/pessimistic unit economics. Don't assume Firebase Spark guarantees no costs on separate billing-enabled Cloud Run.

**18C:** a single flagship demo rather than fifteen modules; public URL, reproducible repo, honest architecture, deck/PDF, 3-minute video or current organizer-specified duration, and prepared technical/business Q&A.

## Acceptance plan for this first chunk

- [ ] Technical audit prints PASS without downgrading Auth/App Check.
- [ ] Four deterministic Python states and their five-stage traces match source-level expectations.
- [ ] TestClient verifies unauthenticated 401, test-only authorized 200.
- [ ] All seven business KPIs explicitly say NOT MEASURED, not zero and not made-up results.
- [ ] Customer and merchant personas, merchant incentive risk, business baselines and open assumptions reviewed.
- [ ] Real model/service integration remains correctly labeled UNVERIFIED until later controlled testing.
- [ ] No production files, settings, paid services or deployed site changed.

## Development discipline

Only proceed from 17A to 17B after reviewing source wiring and reports. Any failures are findings, not obstacles to circumvent. The roadmap is fixed; defects discovered during later chunks are addressed within their corresponding scope instead of expanding chunk count indefinitely.
