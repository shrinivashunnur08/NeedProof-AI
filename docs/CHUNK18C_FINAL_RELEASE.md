# Chunk 18C — Competition release-quality gate (offline edition)

**Purpose:** Turn tested NeedProof AI 17A–18B code into a reproducible, auditable *offline* judge demonstration, with a truthful technical pitch and explicit outstanding live-integration gates.

**Hard boundary:** This bundle **does not deploy**, call Gemini, touch GCP/Firebase billing, access actual merchant data, alter existing React/FastAPI, or complete human research. A green gate means *offline judge-demo evidence is internally consistent*; **not** production readiness or final external validation.

## Windows CMD (after guarded package installation)

```bat
cd /d D:\AiBuilderCup\needproof-ai
scripts\verify_chunk18c.cmd
notepad qa_reports\18c\local_release_audit.json
notepad docs\CHUNK18C_DEMO_RUN_OF_SHOW.md
notepad docs\CHUNK18C_JURY_NARRATIVE.md
```

The command runs: 11 18C assertion tests; 18B + 18A + 17G local safety regression; 17F comparative fixture tests; full React TypeScript/Vite production build; and an 18C **read-only** audit of Git-tracked credentials, reproducible JSON reports, and release-claim integrity. Reports are written to `qa_reports/18c` (untracked). It does not test public website usability or live authentication.

## Scope of automatic evidence

- 18A: 47 builder-authored fictional scenarios, including 10 intentionally invalid Pydantic inputs.
- 18B: 37 valid fictional cases × 4 policies; NeedProof and strong structured rules tie. Five counterfactual tests with omitted synthetic input signals; **not** isolated internal-module ablations.
- 17G: synthetic benchmark truth binding and frontend build; 17G local source gate enforces known fail-closed safety states.
- Secret scan: **Git-tracked files only**, sensitive names/extensions and common private-key markers; not comprehensive secret scanning. Does not authorize publication and cannot examine untracked private secrets.
- Frontend oversized JS chunks are warnings, not ignored; they remain open UX/performance review items.
- Economic figures are hypothetical editable assumptions, never actual provider prices, bills, customer savings or ROI.

## Evidence classes to use in demo

| Feature | What can be demonstrated truthfully | What is not proven |
| --- | --- | --- |
| Fresh 17C decisions | Local React→FastAPI dynamic recomputation when backend is running; fictional merchant states | Current merchant inventory or a hosted production transaction |
| 17D Evidence Passport | Claims, missing proof, disagreement, content fingerprints | Source authenticity or tamper-proof third-party origin |
| 17E Next-Best-Proof | Rules-guided verification order and hypothetical EVSI | Calibrated real merchant response or actual contact |
| 17F/18A/18B evaluation | Reproducible authored fixtures, controlled comparators and documented tie | Independent generalization, real-world win rates, Gemini accuracy |
| 18B economics | Transparent illustrative arithmetic | Live billing, verified prices, measured ROI |
| Gemini/Places/Firestore/Cloud Run | Architecture and pre-existing integration code, conditional on auth/flags | An approved live end-to-end workflow unless separately executed and evidenced |

## Manual acceptance (required before describing it as fully release-ready)

See `validation/18c/MANUAL_ACCEPTANCE.md`: operator screenshot/video, desktop/mobile keyboard use, backend disconnect, safe error states, HTTPS/Auth/App Check/CORS/IAM tests **only if expressly approved**, no public secrets, accessibility/performance review, deployment smoke checks if approved, real merchant and independent-user tests if obtainable, real Google pricing if cost claims are made, and a rehearsal of the exact submitted demo.

## Freeze protocol

- Preserve existing code and auth settings. Do not change baseline comparator outcomes or synthetic labels.
- Do not stage `qa_reports/`, generated files, old patch payloads, `.env` or consented research participant records.
- Stage only **nine new 18C deliverables** after review. Do not stage this installer or patch payload.
- Check `git diff --cached --check`, `git diff --cached --stat`, and `git status --short` before commit.
- Note the resulting Git commit as the release candidate in the video/pitch notes.

## Honest readiness assessment

The competitive advantage to demonstrate is **decision explainability, evidence provenance, detection of incompatible/conflicting information, re-evaluation and prioritized next verification**. The test set has not established greater classification accuracy than strong structured rules. Real shopper value, seller engagement and operational ROI are **hypotheses awaiting proof**, not field findings.
