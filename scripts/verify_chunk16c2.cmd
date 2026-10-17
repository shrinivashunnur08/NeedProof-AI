@echo off
setlocal
cd /d "%~dp0.."
if not exist "backend\.venv\Scripts\python.exe" (echo STOP: Missing backend virtual environment.& exit /b 1)
backend\.venv\Scripts\python.exe scripts\apply_chunk16c2.py --check
if errorlevel 1 exit /b 1
pushd backend
.venv\Scripts\python.exe -m pytest -q tests\test_chunk16c2_replay.py
if errorlevel 1 (popd & echo STOP: 16C.2 focused tests failed. & exit /b 1)
popd
call scripts\verify_chunk16b2b.cmd
if errorlevel 1 (echo STOP: Security/regression/emulator/frontend build failed. & exit /b 1)
echo PASS: Chunk 16C.2 integrated React replay, 16B security gate, Firestore emulator and Vite build.
echo All demo data fictional. Live Auth, Cloud Run, hosted rollout and paid calls remain UNVERIFIED.
endlocal
