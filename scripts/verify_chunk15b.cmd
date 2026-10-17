@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo STOP: Missing local backend Python virtual environment.
  exit /b 1
)
cd /d "%ROOT%" || exit /b 1
"%PY%" scripts\check_chunk15b.py --check || goto :fail
cd /d "%ROOT%\backend" || exit /b 1
"%PY%" -m pytest -q tests\test_benchmark_15b.py tests\test_cloud_15a.py tests\test_cloud_14b4.py tests\test_cloud_14b3.py tests\test_cloud_14b2.py tests\test_cloud_14b1.py tests\test_cloud_14a3.py tests\test_cloud_14a2.py tests\test_cloud_14a1.py tests\test_cloud_13c2.py tests\test_cloud_13c1.py tests\test_cloud_decision_api.py tests\test_cloud_13b.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13b3.py || goto :fail
cd /d "%ROOT%\frontend" || exit /b 1
call npm run build || goto :fail
cd /d "%ROOT%" || exit /b 1
"%PY%" scripts\run_benchmarks15b.py --repeat-verify || goto :fail
git diff --check || goto :fail
echo PASS: 15B benchmark contracts, previous regressions, frontend, deterministic reports.
echo No production resource or feature flag changed.
exit /b 0
:fail
echo STOP: 15B verification failed. Do not commit, push, or deploy.
exit /b 1
