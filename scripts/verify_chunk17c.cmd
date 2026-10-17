@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%CD%\backend"
echo =============================================================
echo NEEDPROOF 17C - LOCAL PYTHON + SECURITY REGRESSION (NO CLOUD)
echo =============================================================
if not exist "backend\.venv\Scripts\python.exe" (
  echo ERROR: backend\.venv\Scripts\python.exe missing
  exit /b 1
)
"backend\.venv\Scripts\python.exe" -m pytest -q backend\tests\test_chunk17c_fresh.py backend\tests\test_chunk17c_routes.py backend\tests\test_cloud_16a.py backend\tests\test_chunk17b_service.py backend\tests\test_chunk17b_cloud.py
if errorlevel 1 exit /b 1
"backend\.venv\Scripts\python.exe" scripts\trace_chunk17c_offline.py
if errorlevel 1 exit /b 1
if not exist "frontend\node_modules" (
  echo ERROR: Missing frontend\node_modules. Install dependencies in frontend first.
  exit /b 1
)
pushd frontend
call npm run build
set "BUILD_RESULT=%ERRORLEVEL%"
popd
if not "%BUILD_RESULT%"=="0" exit /b 1
echo PASS: Chunk 17C Python + local HTTP security tests + frontend build.
echo NOTE: no real Gemini, no hosted Cloud Run, no real merchant.
exit /b 0
