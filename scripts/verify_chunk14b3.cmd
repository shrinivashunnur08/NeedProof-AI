@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo STOP: Backend Python virtual environment is missing.
  exit /b 1
)
cd /d "%ROOT%"
"%PY%" scripts\apply_chunk14b3.py --check || goto :fail
cd /d "%ROOT%\backend"
"%PY%" -m pytest -q tests\test_cloud_14b3.py tests\test_cloud_14b2.py tests\test_cloud_14b1.py tests\test_cloud_14a3.py tests\test_cloud_14a2.py tests\test_cloud_14a1.py tests\test_cloud_13c2.py tests\test_cloud_13c1.py tests\test_cloud_decision_api.py tests\test_cloud_13b.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13b3.py || goto :fail
cd /d "%ROOT%\frontend"
call npm run build || goto :fail
cd /d "%ROOT%"
git diff --check || goto :fail
echo PASS: NeedProof 14B.3 inventory intelligence, prior tests and frontend build.
echo No Cloud Run, Firebase, Firestore, Places, Gemini or IAM resources were modified.
exit /b 0
:fail
echo STOP: 14B.3 verification failed. Do NOT commit, push, deploy or enable cloud flags.
exit /b 1
