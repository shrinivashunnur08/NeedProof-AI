@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: Expected Python virtual environment: %PY%
  exit /b 1
)
cd /d "%ROOT%"
"%PY%" scripts\apply_chunk13c1.py --check || goto :fail
cd /d "%ROOT%\backend"
"%PY%" -m pytest -q tests\test_cloud_13c1.py tests\test_cloud_decision_api.py tests\test_cloud_13b.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13b3.py || goto :fail
cd /d "%ROOT%\frontend"
call npm run build || goto :fail
cd /d "%ROOT%"
git diff --check || goto :fail
echo PASS: Chunk 13C.1 local verification. Cloud services unchanged.
exit /b 0
:fail
echo STOP: Validation failed. Do not deploy or activate features.
exit /b 1
