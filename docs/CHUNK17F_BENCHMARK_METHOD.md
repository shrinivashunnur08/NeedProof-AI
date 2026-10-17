# Chunk 17F — Synthetic, reproducible comparative benchmark

## Purpose

The objective is to test whether NeedProof's 17E evidence workflow implements expected policies on a fixed dataset, and to make failures and comparison with simpler baselines visible. **This benchmark does not establish market impact, independent model superiority or validated merchant data.**

## Inputs

- `backend/fixtures/benchmark17f_cases.json`: 40 frozen fictional examples across eight families: unverified offers, matched fictional excerpts, contradictions, stockouts, over-budget reports, missing merchants, restocks and stock-out revisions.
- All expected decisions and first checks were **authored by the builders** based on stated policy requirements. They are **not independently annotated ground truth**. This is not a blind holdout or field study.
- All four systems receive the same Pydantic-validated, structured fields. None sees expected labels during inference; none makes cloud requests.
- No real merchant, manufacturer, shopper or location is queried. Factual correctness of listings and stock cannot be assessed here.

## Comparators

1. `NEEDPROOF_17E` — Actual local Python decision engine, 14A.3 replan, 17D Passport, 17E verification queue and hypothetical 14A.1 EVSI. Purchase always denied.
2. `PRICE_ONLY` — Ignores stock and conflicting documents; selects an in-budget fictional offer provisionally. It is a basic straw-man pricing heuristic, **not** a proxy for Google Shopping.
3. `STOCK_AND_BUDGET` — Requires a positive fictional stock report and in-budget price but ignores contradictions.
4. `STRUCTURED_EVIDENCE_RULES` — **Strong** rule-based competitor that sees the same structured conflict and revision tags and is designed to recognize these synthetic patterns. It may tie NeedProof. Such parity must be reported, not concealed.

**There is NO genuine LLM-only baseline** because a real controlled Gemini/other LLM experiment would require explicit cloud approval and controlled prompts, tokens, costs, repeats and fairness. Running a heuristic and calling it "LLM-only" would be misleading.

## Metrics

- *Decision state correctness* — Matches authored expected workflow state / 40.
- *Next verification correctness* — Matches authored expected first human verification action / 40.
- *False provisional selection* — Final decision proposes a provisional offer in a case authored as not provisionally eligible. A candidate retained in an internal conflict-blocked replan stage is not counted as a final selection.
- *Missed provisional selection* — Final decision refuses a fictional offer in a case authored as eligible for provisional consideration.
- *Unauthorized purchase* — Every policy in this comparison must remain `purchase_allowed=False`. **Zero violations are necessary, but are not evidence of real purchase security.**
- *Local elapsed time* — Microbenchmark of the local Python call on that computer. Model, HTTP, storage, network, human checks and user interface are excluded. Comparisons should not be extrapolated to production performance.

**Not measured:** actual wasted store visits, revenue, conversion rate, merchant response rate, acquisition costs, calibrated probability, actual stock precision/recall, real user time savings and cost per cloud Gemini call. These require 18A/18B validation and controlled budgets.

## Reproduce

```cmd
cd /d D:\AiBuilderCup\needproof-ai
scripts\verify_chunk17f.cmd
```

Or just regenerate the reports:

```cmd
backend\.venv\Scripts\python.exe scripts\run_chunk17f_benchmark.py --repeat 3
```

Open `qa_reports\17f\benchmark_dashboard.html` locally in the browser, or inspect `benchmark_report.md`, `benchmark_results.json`, and `case_comparison.csv`. All files generated under `qa_reports` are untracked and **not to be staged**.

The `semantic_results_sha256` excludes nonreproducible timings. Dataset/source changes must update the report and rerun every case. Mismatches are printed, not dropped.

## How to interpret a tie

If the strong `STRUCTURED_EVIDENCE_RULES` baseline matches NeedProof's score, this demonstrates that sophisticated GenAI is **not required to solve these specific synthetic structured scenarios**. It does not invalidate NeedProof's broader product hypothesis, but it weakens any claim of superiority from this benchmark alone. Future independent, naturally phrased, ambiguous customer/merchant evidence is needed.

## Jury-facing claim discipline

Safe statement: "In 40 authored fictional cases, our local engine showed [actual metric] against three open deterministic baselines, with all assumptions and failures published. Real merchant and shopper testing remains future work."

Unsafe statement: "We proved 100% retail accuracy, prevented wasted trips, beat Google Shopping or reduced costs by 80%." 
