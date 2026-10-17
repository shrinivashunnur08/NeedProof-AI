# Chunk 17E — Next-Best-Proof / Hypothetical Merchant Revision

## What this implements

17E extends the existing 17C/17D fresh local scenario, without changing its protected routes or introducing a second commerce engine.

- **Deterministic verification queue** for missing compatibility, merchant identity, inventory and fulfillment proof. Document conflict outranks economic ranking; with no merchant the system calls for discovery; with a stock-out it calls for alternatives.
- **Actually evaluates the pre-existing 14A.1 EVSI engine**, separately from the five 14A.3 pipeline stages, using fixed illustrative prior=0.65, response probability=0.80, assumed ₹5 verification cost and 2-minute delay. These are NOT empirical or calibrated metrics; EVSI cannot override contradiction or a stock-out.
- **Fictional revision controls**: server-generated previous and current client what-if snapshots. Replan, Passport source content and queue are recomputed. No real merchant is enrolled, contacted, authorized or verified. No evidence is persisted, and no result permits purchase.
- **Business value hypotheses**, not measured impact: number of proposed verification actions, zero actual contacts and documented next-step rationales. Measuring time saved, conversion, actual adoption and actual merchants belongs in the later pilot.

## Windows CMD verification

```cmd
cd /d D:\AiBuilderCup\needproof-ai
scripts\verify_chunk17e.cmd
```

Run `scripts\run_chunk17c_backend.cmd` in one CMD window and `scripts\run_chunk17c_frontend.cmd` in a second; open `http://127.0.0.1:5173`, locate the Fresh Decision section, and execute with fictional acknowledgement checked.

| Scenario | Expected queue first action | Decision |
| --- | --- | --- |
| 1 unit, no specification docs | `CHECK_COMPATIBILITY` | `PROVISIONAL_VERIFICATION_NEEDED` |
| Contradictory USB-PD excerpts | `RECONCILE_CONFLICT` | `RESEARCH_CONFLICT` |
| 1 unit, then simulated 0-unit update | `REFRESH_ALTERNATIVES` | `MORE_EVIDENCE_NEEDED` |
| 0 units, then simulated 1-unit update | `CHECK_COMPATIBILITY` | `PROVISIONAL_VERIFICATION_NEEDED` |
| No merchants | `DISCOVER_MERCHANTS` | `DISCOVERY_NEEDED` |

For each case: `Purchase allowed: NO`, `NOT EXECUTED` for suggested proof actions. Open the EVSI details to inspect labelled hypothetical costs, priors, and the separate 14A.1 score (where applicable). The merchant revision is **user-controlled fictional input**.

## Security and live deployment boundary

The new `verification_queue_17e` is embedded within the existing protected fresh journey response. No new HTTP route, auth override or cloud enable flag is added. Existing Cloud Run fresh journey remains disabled by default. Offline model and Firebase tests cannot establish hosted Auth/App Check correctness.

## Later chunks

17F: fair comparative baselines and business outcome metrics. 17G: complete hosted authorized journey. 18A: real consenting merchant/user tests (separate approval and verification). Never turn fictitious evidence into certified inventory.
