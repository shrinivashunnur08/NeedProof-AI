@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo STOP: Missing local backend Python virtual environment.
  exit /b 1
)
cd /d "%ROOT%"
"%PY%" scripts\apply_chunk15a.py --check || goto :fail
cd /d "%ROOT%\backend"
"%PY%" -m pytest -q tests\test_cloud_15a.py tests\test_cloud_14b4.py tests\test_cloud_14b3.py tests\test_cloud_14b2.py tests\test_cloud_14b1.py tests\test_cloud_14a3.py tests\test_cloud_14a2.py tests\test_cloud_14a1.py tests\test_cloud_13c2.py tests\test_cloud_13c1.py tests\test_cloud_decision_api.py tests\test_cloud_13b.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13b3.py || goto :fail
cd /d "%ROOT%\frontend"
call npm run build || goto :fail
cd /d "%ROOT%"
git diff --check || goto :fail
echo PASS: 15A streamed-body guard, auth and regressions, security response headers, lazy-loaded optional components, Vite build.
echo No Google Cloud, Firebase, Places, Firestore, Gemini or billing configuration was changed.
exit /b 0
:fail
echo STOP: 15A verification failed. Do not commit, push, deploy or enable new flags.
exit /b 1
