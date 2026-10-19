# Handoff: final submission (18 Oct 2026)

Use this to continue in a fresh session. Source of truth for content: `docs/SUBMISSION_KIT.md`.

## State
- Live app: https://needproof-822406860102.asia-southeast1.run.app (Cloud Run `needproof`, asia-southeast1, project `project-e191c6db-1912-4df5-acf`, min/max 1 instance). App data survives redeploys (Cloud Storage snapshot `gs://needproof-media-822406860102/state/commerce_loop.db`).
- Repo: https://github.com/shrinivashunnur08/NeedProof-AI. `feat/genai-commerce-loop` merged to `main` (PR #1, merge commit d4dbf2f). Later commits on the feature branch (INR sample photos, Gemini timeout/retry, shared live connection, price formatting, these docs) still need pushing and a second small PR.
- Deck: `NeedProof_AI_Builder_Cup.pptx` + `.pdf` (15 slides, official template, ~1.7 MB PDF). Built by a python-pptx script from the official template; screenshots are from the live app on 18 Oct.

## Presentation decisions
- One story: a shopper in Mumbai searches by photo for a navy floral shirt (size M, under ₹1500, near Wadala) → Gemini routes to clothing shops → two real shops reply (match at ₹1,299, conflict with a red check shirt at ₹999) → directions → shop's own demand → business routing + BigQuery ML/AI → Trust report.
- Claims kept honest: Firebase/Firestore not used; AlloyDB/Cloud SQL not used (SQLite + Cloud Storage snapshots); Looker = Looker Studio link only; sample shops labelled; evals small; benchmarks simulated.
- Cost slide: per-request list-price estimate, ≈ US$0.01/request at a 10k-request pilot (Places dominates).

## Still to do (user)
1. Fill slide 1 team name and team leader; slide 14 video link; re-export PDF (≤5 MB).
2. Record the video per `docs/SUBMISSION_KIT.md` §6 (reset data first; use "Reply as shop", never the WhatsApp button).
3. Make the repo public; push the remaining feature-branch commits and merge.
4. Paste the description (§1) in the form.
5. After judging: teardown and key rotation (§7).
