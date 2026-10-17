@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONPATH=%CD%\backend"
if not exist "backend\.venv\Scripts\python.exe" (
 echo ERROR: Missing backend virtual environment.
 exit /b 1
)
echo ===== CHUNK 18A AUTHOR-CREATED FICTIONAL VALIDATION =====
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_chunk18a_independent_validation.py
if errorlevel 1 exit /b 1
backend\.venv\Scripts\python.exe scripts\run_chunk18a_validation.py
if errorlevel 1 exit /b 1
if exist "scripts\verify_chunk17g_local.cmd" (
 call scripts\verify_chunk17g_local.cmd
 if errorlevel 1 exit /b 1
)
echo PASS: Chunk 18A local fictional validation; no cloud/network performed.
echo NOTE: Actual user/merchant research is NOT yet completed.
exit /b 0
