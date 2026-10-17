# Chunk 17G — Judge Journey and Published Evidence Gate

**Target exact baseline:** `4874ff7`. **Deployment:** none. **Cost:** offline only.

## Scope

Add a concise, optional-extended judge narrative to the existing React Showcase and surface the published 17F authored benchmark summary. The new panel is **not** a live performance or retail metrics dashboard. Existing Judge Replay, Fresh Decision, Evidence Passport, Next Best Proof, cloud feature flags, authentication, and Python policy rules remain unchanged.

### Testable claims

- The 17F benchmark compares NeedProof, price-only, stock+budget, and strong structured evidence rules across **40 authored fictional scenarios**.
- Strong structured rules **tie NeedProof 40/40**. This is not evidence of superiority over them or a live LLM.
- A Python gate reruns 17F reporting and ensures the React JSON matches the regenerated dataset hash, semantic results hash, counts, unsafe provisional picks, and explicit unverified flags.
- The compact React panel is keyboard-usable (`button` with `aria-expanded`) and names simulation vs verified functionality.

## Manual acceptance / demo

1. Run `scripts\verify_chunk17g.cmd` in project root: expect prior 17F tests/build, 17G tests, exact published summary verification.
2. Start `scripts\run_chunk17c_backend.cmd` and `scripts\run_chunk17c_frontend.cmd` in two CMD windows; open http://127.0.0.1:5173.
3. Find **Evidence-led retail decisions · Judge journey**. Confirm it shows request → fictional change → next best proof.
4. Expand **Inspect measured synthetic comparison**. Confirm 40/40 for NeedProof and **structured evidence rules**, not a fabricated lead.
5. Navigate to **Try fresh local Python decision**, test 1→0 stock revision and a document contradiction; ensure result/purchase safety/Passport still work.
6. Try a mobile viewport and keyboard navigation. Note any clipping, focus or scrolling problems.
7. Verify no new cloud deployments and no public activation of experimental endpoint occurred.

## Remains pending before marking entire 17G complete

- Mobile accessibility and performance profiling across the full unified interface, including the existing ~512 kB lazy-loaded FreeShowcase chunk.
- Production Auth/App Check/cross-project IAM verification, secrets redaction, guarded deployment and rollback planning. **Never lower auth requirements to pass tests.**
- Controlled real Gemini execution if owner explicitly authorizes cloud costs, and corresponding accurate mode labels.
- Security/regression review of merged changes from other developers.

## Collaboration / parallel changes

**Frontend owner:** coordinate any edits to `frontend/src/FreeShowcase.tsx` before installing this patch; the guard refuses edited shared source. Prefer separate `feature/17g-ux` PRs. **Backend owner:** preserve 17F methods, evidence provenance, and security boundaries; don't repurpose synthetic scores as real business KPIs. Merge using PR review and rerun the Windows suite.
