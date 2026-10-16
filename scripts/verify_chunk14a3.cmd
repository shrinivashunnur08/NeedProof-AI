@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo STOP: Backend virtual environment not found.
  exit /b 1
)
cd /d "%ROOT%"
"%PY%" scripts\apply_chunk14a3.py --check || goto :fail
cd /d "%ROOT%\backend"
"%PY%" -m pytest -q tests\test_cloud_14a3.py tests\test_cloud_14a2.py tests\test_cloud_14a1.py tests\test_cloud_13c2.py tests\test_cloud_13c1.py tests\test_cloud_decision_api.py tests\test_cloud_13b.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13b3.py || goto :fail
cd /d "%ROOT%\frontend"
call npm run build || goto :fail
cd /d "%ROOT%"
git diff --check || goto :fail
echo PASS: NeedProof Chunk 14A.3 local integration, regression tests and Vite build.
echo Cloud Run, Firebase, Places, Gemini and Firestore were not deployed or modified.
exit /b 0
:fail
echo STOP: Local 14A.3 validation failed. Do not commit, push or deploy.
exit /b 1
