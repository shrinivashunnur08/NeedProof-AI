# Chunk 16C.2 — Judge-facing local React integration

## Demonstration (2 minutes)

Open the NeedProof React showcase (`VITE_PUBLIC_SHOWCASE=true`) locally. At the top, show the **Start guided demo** navigation item. The green-accented card is labeled **OFFLINE REPLAY · FICTIONAL DATA**. No API tokens or account data are needed for this component.

1. **Merchant claim:** start with a fictional merchant reporting one charger. Explain the decision is provisional, never an independent stock verification.
2. **Stock-out:** click **Now remove reported stock**. The displayed result changes to `MORE_EVIDENCE_NEEDED` from the original `PROVISIONAL_VERIFICATION_NEEDED`, using stored outputs generated from the Python engine.
3. **Conflicting sources:** select conflicting evidence; `RESEARCH_CONFLICT` blocks progression.
4. **No candidates:** select no merchants; `DISCOVERY_NEEDED` is shown rather than inventing store supply.
5. **Trace:** step through five computation stages (merchant evidence, product documents, hypothetical verification, independent synthetic basket, safety boundary). Open provenance disclosures and note BI context is independent and fictional.

## Checklist before hosted demo

- [ ] Responsive UI checked at 390px, 768px, and 1440px browser widths; no clipped stages/buttons
- [ ] Keyboard tab through scenario selector and five stage buttons
- [ ] `scripts\verify_chunk16c2.cmd` passes and React showcase can be viewed locally
- [ ] Confirm `frontend/src/generated/needproof16cReplay.json` matches committed 16C.1 HTML output
- [ ] Real browser Auth/App Check, deployed CORS, cross-project Firestore IAM and merchant access remain explicitly unverified
- [ ] Check any cloud deployment and cost/quota change separately; **this chunk does not deploy**

## Cost and trust rules

This React component imports static JSON from the repository and makes **zero Google API calls itself**. It does not disable existing page-level Firebase initialization or other live features. Do not claim zero total hosted application costs or real product stock, real sales uplift, or actual merchant response. Any hosted deploy is an independently approved release step.

## Next stage

Only after local usability review should you decide whether to publish a hosting-only public walkthrough and whether to authorize live authenticated Cloud Run/Firestore tests. Neither occurs in 16C.2.
