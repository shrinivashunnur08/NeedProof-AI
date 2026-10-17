# Chunk 17B repeatable offline verifier — post-install correction

The guarded patch installer correctly requires pre-install Git commit `7db48ca`. The previously supplied `scripts/verify_chunk17b.cmd` also called that installer, meaning the verification runner would stop after a successful Git commit. This minor fix removes that **installation-only** check from the reusable test runner. The original guard remains available locally for pre-install audits, and production Firebase Auth/App Check, Gemini flags and API routes are not changed.

Run from the root of NeedProof:

```cmd
backend\.venv\Scripts\python.exe scripts\fix_chunk17b_postcommit_verifier.py --check
backend\.venv\Scripts\python.exe scripts\fix_chunk17b_postcommit_verifier.py --apply
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_chunk17b_postcommit_verifier.py
scripts\verify_chunk17b.cmd
```

**Expected:** one postcommit-runner test passes and all previous 17B offline tests pass. No live Gemini calls or cloud activity.

After verification, commit **application source, tests, reusable trace/verification scripts, and runbooks**, not one-time installers or copied patch payloads. Avoid `git add .` because older backup and experimental files may be present.
