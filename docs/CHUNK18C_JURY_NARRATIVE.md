# NeedProof AI — Jury narrative and technical defense (truthful prototype)

## 20-second hook

"An AI shopping recommendation isn't helpful if the shop doesn't actually have the product or if the charger is incompatible. NeedProof AI is a decision-intelligence layer that keeps claims separate from proof, detects missing or contradictory evidence, and says what to verify before anybody treats a suggestion as confirmed."

## The urgent customer story

A shopper needs a 65W USB-C PD laptop charger, with a budget below ₹1,000 and a same-day requirement. A map listing is only *business discovery*, not inventory proof. A hypothetical merchant says three units are in stock; the engine labels that report **unverified**. The shopper then sees the Evidence Passport, the unresolved compatibility check, and the Next-Best-Proof action. When the fictional stock changes to zero, a fresh backend evaluation revises the state instead of silently approving a purchase. A conflicting fictional USB-PD excerpt produces research conflict. In every authored demo, `purchase_allowed=false`.

## Why it matters

- **Trust:** a provenance trail makes it harder to confuse reports with verification.
- **Safety:** explicit incomplete evidence prevents false purchase authorization.
- **Workflow:** the assistant explains the next concrete proof request rather than only providing an opaque ranking.
- **Potential operational benefit:** fewer wasted inquiries, improved handling of stock uncertainty, and potentially faster decisions; these have **not** yet been demonstrated with real users.

## Technical contribution

React/Vite UI; local FastAPI deterministic decision pipeline; structured Gemini integration code (not a live-call proof); Google Places business discovery integration (not stock verification); claimed evidence history; per-claim provenance/conflict handling; hypothetical EVSI verification planner and policy-based orchestration. The live public, token-authenticated Cloud Run and Gemini workflow must only be described as verified if separately tested end to end.

## 18B measured claims (authored fictional data, not field observations)

| Policy | Correct states in 37 authored valid cases | Unsafe provisional classifications |
| --- | ---: | ---: |
| NeedProof | 37/37 | 0 |
| Strong structured evidence rules | 37/37 | 0 |
| Price-only | 25/37 | 12 |
| Stock + budget | 34/37 | 3 |

No superiority over the strong structured-rules baseline was established. The five signal-withholding counterfactuals indicate sensitivity to information availability, **not** a separately isolated contribution of a model or component. 18B measured local Python execution, not deployed service latency.

## Judges' challenging questions

**Why AI instead of rules?** Natural-language requirements and unstructured documents motivate model-assisted extraction and grounding; the current audited decisions are largely deterministic. Our strong rules comparator ties NeedProof on these structured authored examples. AI incremental value in unstructured live cases remains to be measured.

**Where is the real inventory?** Business discovery, merchant reports and independent inventory verification are distinct. We do not have externally authenticated stock verification from a live merchant pilot yet.

**Are provenance hashes proof of truth?** No. They bind displayed stages to the same evaluated snapshot, not to an authentic third-party source.

**What does the EVSI score represent?** Hypothetical expected value of information under illustrative uncalibrated response/utility assumptions; it is not a learned likelihood of real stock.

**What did you actually validate?** 17F and 18A/18B fictional scenario harnesses and local frontend/backend integrity. Independent shopper/merchant outcomes, live model and hosted Auth/App Check/IAM remain separate unverified work.

**What would real deployment require?** Authenticated merchant ownership, consent and deletion handling, quota/billing caps, live model and Places quality tests, live site accessibility, isolated secret/IAM review, and field validation before commercial claims.

## Closing statement

"NeedProof doesn't promise certainty where the evidence is missing. It makes uncertainty visible, preserves a trace of the decision, and gives shoppers and merchants a concrete next step to resolve it."
