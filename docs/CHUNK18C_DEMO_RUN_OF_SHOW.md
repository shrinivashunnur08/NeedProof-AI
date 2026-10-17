# NeedProof AI — 3:30–4:00 judge demonstration storyboard

**Record actual UI output on your own checkout; no fabricated product responses.** If network-dependent features do not work, show the local offline lane and explicitly label it. Do not edit footage to suggest Gemini or merchants were queried when they were not.

| Approx time | Scene | Real operator action | Honest narration |
| --- | --- | --- | --- |
| 0:00–0:25 | Problem and hook | Show opening title/judge dashboard | "A store listing is not evidence that a product is available or compatible." |
| 0:25–0:55 | User intent | Enter realistic 65W charger requirement under ₹1,000 | "This is a fictional scenario; live intent extraction runs only if separately authorized." |
| 0:55–1:25 | Provisional claim | Submit a fictional merchant with positive reported stock to the **running local** backend | "We have a fresh backend decision, not independently verified stock." |
| 1:25–1:55 | Evidence Passport | Highlight missing compatibility, verification status and source claims | "The passport records where claims came from; it doesn't authenticate them." |
| 1:55–2:20 | Next Best Proof | Show priority queue/why next step | "Verification priority uses illustrative assumptions; no merchant has been contacted." |
| 2:20–2:45 | Changing evidence | Change fictional stock to zero and re-run; then conflict preset if time | "The system revises its provisional decision and never authorizes checkout." |
| 2:45–3:15 | Honest evaluation | Display 17G/Jury Evidence panel plus 18B comparison | "We beat simpler baselines, but tie a strong structured-rules comparator on 37 crafted cases." |
| 3:15–3:45 | Engineering and next steps | Show trace and future validation matrix | "Local execution is tested; live Gemini, hosted security and real merchant inventory require independent proof." |

## Operator prep (offline/local)

1. `scripts\verify_chunk18c.cmd` passes before recording. Preserve the report.
2. In **CMD window 1**: `scripts\run_chunk17c_backend.cmd`. If port 8000 is already occupied by the correct app, do **not** start a duplicate process.
3. In **CMD window 2**: `scripts\run_chunk17c_frontend.cmd`. Open `http://127.0.0.1:5173`.
4. Record actual mouse/browser/network interactions; don't show secrets or tokens in devtools.
5. Use fictional inputs and call them fictional. Confirm `purchase_allowed=false` on every case and clear backend errors on disconnect.
6. Capture desktop at typical judge resolution and separately verify narrow mobile layout, keyboard controls, text contrast, and no clipped buttons.
7. If the 18B summary is not embedded in the user interface, show the generated report transparently as **a separate offline audit**, not an interactive real-world metric dashboard.
8. Never describe Git push as Firebase/Cloud Run deployment. If approved for deployment, verify the deployed revision and real browser requests separately.

## Prepare a resilient fallback

Keep a locally reproducible copy of the judge journey and test output. If the browser-to-backend request fails, **show the failure clearly and stop the claim of a live interaction**. A checked-in replay can be shown only with its replay/synthetic label.

## Submit-ready artifacts checklist

- Screen-recorded truthful walkthrough; narration and captions; no exposed credentials or real participant details.
- Link to reproducible commit and installation steps.
- Architecture diagram matching actual working paths and conditional services.
- Evidence report distinguishing fixture tests and missing external validation.
- Slide-ready story: problem, customer journey, algorithm/evidence trace, benchmark with tie, limitations, validation plan, commercial hypothesis.
