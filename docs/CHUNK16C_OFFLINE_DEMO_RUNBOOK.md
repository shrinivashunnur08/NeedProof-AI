# NeedProof AI — Chunk 16C Offline Demo Runbook

**Purpose:** An attractive, self-contained, judge-facing *offline replay* of four scenarios generated using the real 16A Python orchestration engine. This does **not** verify a live merchant, Firebase token, Firestore IAM, Google Places listing, or hosted deployment. The replay is engineered to make the existing models comprehensible, not prove independent real-world gains.

## Five-minute demo narrative

1. Open `demo\needproof16c\offline-demo.html` directly in Chrome or Edge. Confirm the **OFFLINE REPLAY** label. The CSP blocks outgoing connections.
2. Begin with **Reported offer**. Explain why a merchant's claim is provisional rather than an inventory guarantee. Step through the five distinct orchestration stages.
3. Change to **Stock-out**. Explain the changed evidence event and how the decision becomes **MORE_EVIDENCE_NEEDED**. Point to the next verification action.
4. Choose **Conflicting excerpts**. Demonstrate **RESEARCH_CONFLICT** and why product source contradiction must be reconciled.
5. Choose **No merchant evidence**. Demonstrate **DISCOVERY_NEEDED** instead of inventing stores. Show the separate, clearly fictional retail BI context, and close with **No purchase authorized**.

## Build and verify, Windows CMD

```cmd
cd /d D:\AiBuilderCup\needproof-ai
call backend\.venv\Scripts\activate.bat
python scripts\build_chunk16c_demo.py --check
python scripts\build_chunk16c_demo.py --verify
scripts\verify_chunk16c.cmd
start "" "demo\needproof16c\offline-demo.html"
```

To rebuild the deterministic HTML from the committed Python algorithms:

```cmd
python scripts\build_chunk16c_demo.py --generate
python scripts\build_chunk16c_demo.py --verify
```

## Explicit boundaries

- No user account, Firebase token, network request, browser local storage, external JS, or third-party font required.
- Scenarios and pricing/stock/documents/BI aggregates are explicitly fictional; the original Python decision code is actually evaluated when generating the replay.
- Values are static *replays* until `--generate` is rerun. The HTML **does not** invoke Python at viewing time, nor does it call the protected live API.
- Feature flags in the hosted application are untouched. The original Cloud Run service may incur charges separately from this offline replay.
- The existing frontend main bundle remains large; no performance claim is made for the hosted app.
- Live 16B.2B matrix remains open, and an eventual 16C hosting decision will require a separate explicit approval for possible cloud costs.

## Quick UX checks

- Desktop: at approximately 1366×768, all four scenario controls and the stepper are usable.
- Mobile: at 375×812 and 390×844, controls wrap, no unintended horizontal page scrolling.
- Keyboard: Tab moves through scenario/trace controls, arrow keys can traverse the five stages; focus indicators are visible.
- Accessibility: semantic headings, `aria-pressed` states, `aria-current`, focus indicators, reduced motion respect.
- Failure handling: if the static payload safety contract is invalid, it refuses to render instead of pretending purchase approval.

## Later public demo integration

This standalone offline file is **not** automatically deployed to Firebase Hosting and not linked into `App.tsx`. To deliver a hosted, authenticated judge experience, separately verify real Firebase Auth/App Check/CORS/IAM and explicitly approve a cost-controlled deployment and rollback strategy. Do not present this replay as a live merchant verification.
