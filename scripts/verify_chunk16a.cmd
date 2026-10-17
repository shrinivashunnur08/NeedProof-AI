@echo off
setlocal
cd /d "%~dp0.."
set "PYTHON=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo STOP: Expected backend virtual environment missing.
  exit /b 1
)
"%PYTHON%" scripts\apply_chunk16a.py --check
if errorlevel 1 exit /b 1
pushd backend
"%PYTHON%" -m pytest -q tests\test_cloud_16a.py tests\test_benchmark_15b.py tests\test_cloud_15a.py tests\test_cloud_14b4.py tests\test_cloud_14b3.py tests\test_cloud_14b2.py tests\test_cloud_14b1.py tests\test_cloud_14a3.py tests\test_cloud_14a2.py tests\test_cloud_14a1.py tests\test_cloud_13c2.py tests\test_cloud_13c1.py tests\test_cloud_decision_api.py tests\test_cloud_13b.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13b3.py
if errorlevel 1 (popd & echo STOP: Backend integration and regression suite failed. & exit /b 1)
popd
pushd frontend
call npm run build
if errorlevel 1 (popd & echo STOP: Frontend build failed. & exit /b 1)
popd
echo PASS: NeedProof 16A guided journey API, existing regressions, auth gating, and frontend build.
echo No live cloud deployment or feature flags changed.
endlocal
