@echo off
setlocal
cd /d "%~dp0.."
set "PYTHON=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
 echo STOP: Required backend virtual environment missing.
 exit /b 1
)
"%PYTHON%" scripts\preflight_chunk16b.py --check
if errorlevel 1 exit /b 1
pushd backend
"%PYTHON%" -m pytest -q tests/test_cloud_16b_security_gate.py
if errorlevel 1 (popd & echo STOP: Auth/App Check offline contract tests failed. & exit /b 1)
"%PYTHON%" -m pytest -q tests\test_cloud_16a.py tests\test_benchmark_15b.py tests\test_cloud_15a.py tests\test_cloud_14b4.py tests\test_cloud_14b3.py tests\test_cloud_14b2.py tests\test_cloud_14b1.py tests\test_cloud_14a3.py tests\test_cloud_14a2.py tests\test_cloud_14a1.py tests\test_cloud_13c2.py tests\test_cloud_13c1.py tests\test_cloud_decision_api.py tests\test_cloud_13b.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13b3.py
if errorlevel 1 (popd & echo STOP: Full backend regression failed. & exit /b 1)
popd
call scripts\run_13b_emulator_e2e.cmd
if errorlevel 1 (echo STOP: Real Firestore emulator integration checks failed. & exit /b 1)
pushd frontend
call npm run build
if errorlevel 1 (popd & echo STOP: Frontend build failed. & exit /b 1)
popd
echo PASS: Chunk 16B offline identity and application security contract tests.
echo REAL Firebase token verification and deployed Firestore IAM are still UNVERIFIED.
echo No production Firebase, Cloud Run, Firestore or billing changes.
endlocal
