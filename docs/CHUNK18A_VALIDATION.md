# Chunk 18A — Offline synthetic scenario validation and real research protocol

## Scope
Adds only new files. Calls real local `app.fresh_journey_17c` Python orchestration; no cloud invocation, no authentication bypass, no paid services, no existing source rewrite. Authored test cases are **not** independent merchant/user validation. Sample changes affect only the fictional scenario engine. The full road map still requires real participants and merchant feasibility observations where practical.

## Windows CMD
```bat
cd /d D:\AiBuilderCup\needproof-ai
backend\.venv\Scripts\python.exe scripts\run_chunk18a_validation.py
scripts\verify_chunk18a.cmd
notepad qa_reports\18a\fictional_validation.json
```

Optionally, run a real participant study using `validation/18a/RESEARCH_PROTOCOL.md` and `scripts/record_chunk18a_feedback.py`. This appends anonymized metrics to a local-only, untracked file. Do not stage participant records.

## Method
Each independently authored but **not truly blind** case has explicit expected workflow states and original user wording. Uses direct Pydantic validation and real Python 17C decision path. Covers budget thresholds, zero inventory, no merchants, contradictory opt-in fictional documents, time-invariant safety, consent validation for the simulation and forged verification fields. Tests binding of Evidence Passport and Next-Best-Proof to the workflow hash. Zero real Gemini calls, zero merchant calls, zero database writes, zero purchases.

Run `scripts\verify_chunk17g.cmd` separately to verify prior full frontend build / 17F report. Its outcome should be recorded honestly. The 18A script does not assert any superiority over the strong rules benchmark.

## Exit criteria
1. 18A tests and report pass, including zero purchase approvals.
2. Real participant feedback evidence recorded if available; otherwise sample size explicitly zero.
3. Limitations and failures remain visible; no invented claims of merchant adoption or improved conversion.
4. Existing 17G gate still passes.
