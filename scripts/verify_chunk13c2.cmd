@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo STOP: Expected backend virtual environment missing: %PY%
  exit /b 1
)
cd /d "%ROOT%"
"%PY%" scripts\apply_chunk13c2.py --check || goto :fail
cd /d "%ROOT%\backend"
"%PY%" -m pytest -q tests\test_cloud_13c2.py tests\test_cloud_13c1.py tests\test_cloud_decision_api.py tests\test_cloud_13b.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13b3.py || goto :fail
cd /d "%ROOT%\frontend"
call npm run build || goto :fail
cd /d "%ROOT%"
git diff --check || goto :fail
echo PASS: Chunk 13C.2 local code, source retrieval, regression tests, and frontend build.
echo Cloud Run, Firestore, Gemini flags, and Firebase Hosting unchanged.
exit /b 0
:fail
echo STOP: 13C.2 validation failed; do not commit or deploy until fixed.
exit /b 1
