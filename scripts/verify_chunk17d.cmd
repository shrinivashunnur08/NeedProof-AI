@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONPATH=%CD%\backend"
set "PYTHONDONTWRITEBYTECODE=1"
echo =============================================================
echo NEEDPROOF 17D - EVIDENCE PASSPORT / FICTIONAL INPUT ONLY
echo =============================================================
if not exist "backend\.venv\Scripts\python.exe" (
  echo ERROR: backend Python environment is missing
  exit /b 1
)
"backend\.venv\Scripts\python.exe" -m pytest -q backend\tests\test_chunk17d_passport.py backend\tests\test_chunk17c_fresh.py backend\tests\test_chunk17c_routes.py backend\tests\test_cloud_13c2.py backend\tests\test_cloud_14a3.py backend\tests\test_chunk17b_cloud.py backend\tests\test_cloud_16a.py
if errorlevel 1 exit /b 1
"backend\.venv\Scripts\python.exe" scripts\trace_chunk17d_offline.py
if errorlevel 1 exit /b 1
if not exist "frontend\node_modules" (
  echo ERROR: Missing frontend node_modules. Install frontend dependencies before verification.
  exit /b 1
)
pushd frontend
call npm run build
set "BUILD_RESULT=%ERRORLEVEL%"
popd
if not "%BUILD_RESULT%"=="0" exit /b 1
echo PASS: 17D Python + cloud-auth regression tests + frontend build.
echo NOTE: NO live Gemini, no real inventory, no hosted auth, no paid cloud requests.
exit /b 0
