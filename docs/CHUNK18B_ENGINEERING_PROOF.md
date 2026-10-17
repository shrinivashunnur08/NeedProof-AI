# NeedProof AI — Chunk 18B: Offline Engineering and Hypothetical Economics

**Baseline: `37c324c`** · No changes to existing React, FastAPI, security controls or decision engine.

## Objective

Measure the *actual local Python execution* and compare it fairly with the already-existing 17F deterministic comparator rules on the 18A authored fictional test set. Do not claim superiority over the strong rules baseline, true independent validation, or a real merchant pilot.

## What the report measures

- 47 **author-created fictional** 18A cases: 37 accepted inputs tested against four policies and 10 intentionally invalid inputs checked at the Pydantic boundary.
- The existing actual `evaluate_fresh_journey_17c` pipeline, including 14A orchestration, 17D Evidence Passport, and 17E verification queue.
- Three existing 17F rule comparators **on the same** 18A structured inputs: price-only, stock+budget, strong structured evidence rules.
- 3 conflict and 2 revision scenarios rerun after withholding a fictional input signal. This tests **signal sensitivity**, NOT the independent internal contribution of individual modules. Because input information changes, never report it as a controlled same-input removal of a component.
- Safety contract checks: false purchase flag; no stock verification, merchant contact, database write or Gemini call; consistent passport/queue snapshot fingerprint; five-stage trace.
- Local CPU/Python elapsed time per engine call (no browser/network/model/cloud/database), median and empirical nearest-rank p95.
- An explicitly **hypothetical, user-editable** USD model. Inputs are **invented arithmetic placeholders**, not Google prices, observed spend, savings or ROI.

## Run, Windows CMD

```bat
cd /d D:\AiBuilderCup\needproof-ai
scripts\verify_chunk18b.cmd
notepad qa_reports\18b\engineering_report.md
notepad qa_reports\18b\engineering_results.json
notepad qa_reports\18b\hypothetical_economics.json
```

Also run the full 17G frontend/build regression separately before staging:

```bat
scripts\verify_chunk17g.cmd
```

## Acceptance boundaries

- All case rows retained, including comparator mismatches.
- Dataset provenance states fictional and all external validation fields remain zero/null.
- The strong structured-rules comparator is fairly represented even if tied with the full engine.
- Model-level rejection tests are **not** hosted API identity authorization tests. Existing 17G gates cover some local source/endpoint guards, but live Firebase Auth/App Check + Cloud Run IAM are still unverified.
- Real merchant and user feedback from 18A is still pending until consented observation occurs.
- A release-ready product requires real integration proof and opt-in cost/quota safeguards (18C). Do not enable cloud or paid integrations to satisfy this offline gate.

## Artifact hygiene

Commit the new 18B source and docs only. Exclude `qa_reports`, payload ZIP/installer, `.env`, credential files, and private user/merchant study observations. Do not use `git add .`, `git clean -fd` or `git reset --hard`.
