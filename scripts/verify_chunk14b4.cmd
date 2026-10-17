@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo STOP: Missing local backend virtual environment.
  exit /b 1
)
cd /d "%ROOT%"
"%PY%" scripts\apply_chunk14b4.py --check || goto :fail
cd /d "%ROOT%\backend"
"%PY%" -m pytest -q tests\test_cloud_14b4.py tests\test_cloud_14b3.py tests\test_cloud_14b2.py tests\test_cloud_14b1.py tests\test_cloud_14a3.py tests\test_cloud_14a2.py tests\test_cloud_14a1.py tests\test_cloud_13c2.py tests\test_cloud_13c1.py tests\test_cloud_decision_api.py tests\test_cloud_13b.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13b3.py || goto :fail
cd /d "%ROOT%\frontend"
call npm run build || goto :fail
cd /d "%ROOT%"
git diff --check || goto :fail
echo PASS: NeedProof 14B.4 aggregate BI command center, API regression tests and frontend build.
echo Production Cloud Run, Firestore, Firebase, Gemini, Places, IAM and billing remain unchanged.
exit /b 0
:fail
echo STOP: 14B.4 verification failed. Do not commit, push, deploy or enable cloud flags.
exit /b 1
