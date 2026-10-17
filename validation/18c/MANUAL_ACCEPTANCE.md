# 18C human-operated release acceptance — NOT completed automatically

These checklist items are deliberately **unchecked**. Only the operator can complete them with observed evidence; a green offline CI gate never marks them passed.

- [ ] Run local React -> live localhost FastAPI journey in browser and screen-record stock=1, stock=0, conflicting docs, no-merchants, and 422 safety paths.
- [ ] Verify evidence passport, fingerprint and next-proof display changes after new inputs, without any unauthorized purchase.
- [ ] Confirm keyboard-only navigation, screen-reader labels, 375px mobile layout, and 1366×768 desktop; document visible overflow/contrast issues.
- [ ] Review JS performance warning (`FreeShowcase` measured at ~512kB minified in previous build); capture performance profile on target device.
- [ ] Validate browser error handling when API is offline. No silent switch from API failure to synthetic success.
- [ ] Security review: no credentials/ID tokens in repo, logs, UI screenshots, or deployment; independently review dependencies and secrets.
- [ ] If approved to test live: verify authenticated Firebase ID tokens + App Check from browser to Cloud Run, correct IAM/CORS/origin restrictions, and unauthorized merchant edits denied. Record exact deployed revision, user role and date; redact tokens.
- [ ] If approved and capped: perform controlled Gemini + Google Places request and record true provenance, quota, latency, costs and failures. Do not confuse Places listings with stock.
- [ ] Collect genuinely consented, anonymized shopper and merchant research if available; otherwise declare `n=0` and no adoption proof.
- [ ] Verify any Google Cloud spending against actual billing information before changing slides/claims. Current $3.70 model is illustrative arithmetic.
- [ ] Record, play back, caption and rehearse actual demo video, with no edits that imply external responses were real.
- [ ] Confirm final README, repository commit ID, architecture, slide/story content, and exact evidence limitations.

**Gate policy:** If these remain unchecked, label the artifact `OFFLINE_JUDGE_DEMO_ONLY`, not verified commercial release, hosted end-to-end pilot, or merchant-backed inventory platform.
