@echo off
setlocal
cd /d "%~dp0.."
if not exist "backend\.venv\Scripts\python.exe" (
  echo ERROR: backend\.venv\Scripts\python.exe not found.
  exit /b 1
)
set "PYTHONPATH=%CD%\backend"
echo NEEDPROOF 17B - MOCKED GEMINI ONLY - NO CLOUD REQUESTS
rem The 17B installer guard is intentionally tied to pre-install Git HEAD 7db48ca.
rem After a verified installation, repeatable tests must not depend on that old HEAD.
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_intent_service.py backend\tests\test_intent_api.py backend\tests\test_chunk17b_service.py backend\tests\test_chunk17b_cloud.py backend\tests\test_cloud_16b_security_gate.py backend\tests\test_cloud_15a.py
if errorlevel 1 exit /b 1
backend\.venv\Scripts\python.exe scripts\trace_chunk17b_offline.py
if errorlevel 1 exit /b 1
echo.
echo PASS: Chunk 17B offline validation completed. LIVE GEMINI REMAINS UNVERIFIED.
exit /b 0
