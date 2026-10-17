# NeedProof 17A — Windows Local Socket Guard Fix

Your Chunk 17A offline source audit (18 checks) passed, and Git commit `7b04ca4` was pushed. The full backend trace failed on Windows because Python's asyncio ProactorEventLoop uses `socket.socketpair()` via **127.0.0.1**, but the old trace monkey-patch denied ALL socket connections.

This change is only for the local developer trace. It does **not** modify the deployed app, backend service, Firebase credentials, authentication, feature flags, or billing.

## Extract

Download ZIP to Downloads, then in Windows CMD:

```cmd
cd /d D:\AiBuilderCup\needproof-ai
powershell -NoProfile -Command "Expand-Archive -LiteralPath '%USERPROFILE%\Downloads\NeedProof_17A_Windows_Loopback_Trace_Fix.zip' -DestinationPath 'D:\AiBuilderCup\needproof-ai' -Force"
```

## Verify and patch

```cmd
backend\.venv\Scripts\python.exe scripts\fix_chunk17a_windows_loopback.py --check
backend\.venv\Scripts\python.exe scripts\fix_chunk17a_windows_loopback.py --apply
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_chunk17a_windows_socket_guard.py
scripts\verify_chunk17a.cmd
```

### Expected

1. Audited source hashes pass; only `scripts/trace_chunk17a_backend.py` and `backend/tests/test_chunk17a_audit.py` are patched. Local `.bak` backups are created.
2. 2 new guard tests pass: Python's internal loopback works, while non-loopback TCP is rejected.
3. The full verifier runs 18 existing tests and the actual local FastAPI route, expecting unauthenticated HTTP 401 and test-only-identity HTTP 200.
4. The report file `qa_reports\17a\backend_trace.json` is created. Real Gemini, Cloud Run Auth/App Check and Firestore are **still not verified**.

The guard blocks ordinary external TCP connection attempts while allowing numeric loopback addresses (127.0.0.1 and ::1). It is **not** an OS-level network isolation boundary; run only as a local trace, with no cloud credentials required.

## Commit only if all checks pass

```cmd
git add scripts/trace_chunk17a_backend.py backend/tests/test_chunk17a_audit.py scripts/fix_chunk17a_windows_loopback.py backend/tests/test_chunk17a_windows_socket_guard.py docs/CHUNK17A_WINDOWS_LOOPBACK_FIX.md
git diff --cached --check
git diff --cached --stat
git commit -m "Fix Chunk 17A Windows local FastAPI trace socket guard"
git push origin main
git log -1 --oneline
```

Do not run `git add .`. Backups and QA reports remain untracked. If the source hash check rejects local drift, do not use `--force` or paste private config files; share the exact error.
