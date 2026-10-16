@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo STOP: activate or create the existing backend Python virtual environment.
  exit /b 1
)
cd /d "%ROOT%"
"%PY%" scripts\apply_chunk14a2.py --check || goto :fail
cd /d "%ROOT%\backend"
"%PY%" -m pytest -q tests\test_cloud_14a2.py tests\test_cloud_14a1.py tests\test_cloud_13c2.py tests\test_cloud_13c1.py tests\test_cloud_decision_api.py tests\test_cloud_13b.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13b3.py || goto :fail
cd /d "%ROOT%\frontend"
call npm run build || goto :fail
cd /d "%ROOT%"
git diff --check || goto :fail
echo PASS: Chunk 14A.2 backend, previous regression tests and frontend production build.
echo No Cloud Run, Firebase, Places or Gemini configuration changed.
exit /b 0
:fail
echo STOP: Chunk 14A.2 local verification failed. Do not commit or deploy.
exit /b 1
