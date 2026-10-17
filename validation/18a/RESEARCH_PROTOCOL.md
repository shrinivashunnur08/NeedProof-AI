# 18A — Real participant validation protocol (no participants recruited by this code)

The authored fictional scenario suite **does not constitute independent user research**. `qa_reports/18a/fictional_validation.json` records only developer-created tests. A real-person observation may be recorded only after voluntary, informed consent and actual task completion. Never fabricate participants, responses, merchants, prices, or stock confirmations.

## Suggested tasks (5 or more varied people if practical; label actual sample size)

- **T1:** Read a fictional charger offer, identify whether there is verified inventory, and state whether NeedProof authorizes a purchase. Track correct interpretation and completion time.
- **T2:** Trigger fictional stock-out, explain what changed and what to verify next. Track decision interpretation and completion time.
- **T3:** Read contradictory fictional USB PD excerpts, identify which evidence conflicts and how to resolve it. Track interpretation and completion time.

For merchants, adapt T1–T3 to reporting claims and checking evidence status; **never** request real merchant credentials or store inventory for this exercise. If no merchant participates, label merchant sample as zero.

Explain upfront that all merchant examples are synthetic, no store was contacted, the app does not offer checkout, and the study is about comprehension, not product availability.

Ask participant consent, use generated anonymous codes, avoid collecting names/emails/phones, permit refusal or stopping, and securely retain or delete local records in accordance with consent. Use `backend/.venv/Scripts/python.exe scripts/record_chunk18a_feedback.py` to append metrics only for observed sessions. Do not commit `qa_reports/18a/participants_local_only.csv`. No qualitative claims should be quoted without explicit permission.

## Interpret carefully

Report N per group, completion rate, time-to-task, understanding score, and observed confusion. Samples recruited from friends/teammates are convenience samples. Do not claim merchant adoption, conversion improvement, stock verification, generalizable accuracy, or significance from small N. Keep real-person statistics separate from synthetic scenario results.
