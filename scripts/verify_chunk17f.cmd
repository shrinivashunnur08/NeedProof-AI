@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONPATH=%CD%\backend"
set "PYTHONDONTWRITEBYTECODE=1"
echo ===============================================================
echo NEEDPROOF 17F - FAIR SYNTHETIC BENCHMARKS / OFFLINE ONLY
echo ===============================================================
if not exist "backend\.venv\Scripts\python.exe" (
 echo ERROR: Missing backend Python virtual environment
 exit /b 1
)
"backend\.venv\Scripts\python.exe" -m pytest -q backend\tests\test_chunk17f_benchmark.py backend\tests\test_chunk17e_verification.py backend\tests\test_chunk17d_passport.py backend\tests\test_chunk17c_fresh.py backend\tests\test_cloud_14a3.py
if errorlevel 1 exit /b 1
"backend\.venv\Scripts\python.exe" scripts\run_chunk17f_benchmark.py --repeat 3
if errorlevel 1 exit /b 1
if not exist "frontend\node_modules" (
 echo ERROR: Missing existing frontend node_modules
 exit /b 1
)
pushd frontend
call npm run build
set "BUILD_STATUS=%ERRORLEVEL%"
popd
if not "%BUILD_STATUS%"=="0" exit /b 1
echo PASS: 17F scenario suite + baseline comparison + report generation + frontend build.
echo NOTE: All simulated; not field validation; no real Gemini or merchant access.
exit /b 0
