@echo off
setlocal
cd /d "%~dp0.."
echo ==========================================================
echo  NEEDPROOF 17A - FRESH TECHNICAL + BUSINESS STARTER
echo  OFFLINE AUDIT / BACKEND TESTCLIENT / NO CLOUD REQUESTS
echo ==========================================================
if not exist "backend\.venv\Scripts\python.exe" (
 echo ERROR: Missing backend\.venv\Scripts\python.exe
 exit /b 2
)
if not exist "scripts\audit_chunk17a.py" (
 echo ERROR: Extract the ZIP into D:\AiBuilderCup\needproof-ai
 exit /b 2
)
"backend\.venv\Scripts\python.exe" "scripts\audit_chunk17a.py" --check
if errorlevel 1 exit /b 1
"backend\.venv\Scripts\python.exe" "scripts\business_chunk17a.py" --check
if errorlevel 1 exit /b 1
"backend\.venv\Scripts\python.exe" -m pytest -q "backend\tests\test_chunk17a_audit.py" "backend\tests\test_chunk17a_business.py"
if errorlevel 1 exit /b 1
"backend\.venv\Scripts\python.exe" "scripts\audit_chunk17a.py" --report
if errorlevel 1 exit /b 1
"backend\.venv\Scripts\python.exe" "scripts\business_chunk17a.py" --report
if errorlevel 1 exit /b 1
"backend\.venv\Scripts\python.exe" "scripts\trace_chunk17a_backend.py" --all --save "qa_reports\17a\backend_trace.json"
if errorlevel 1 (
 echo ERROR: Local backend trace could not finish. Share the traceback; do not weaken Auth/App Check.
 exit /b 1
)
echo.
echo PASS: 17A offline source audit + business hypotheses + local Python backend trace.
echo REPORT 1: qa_reports\17a\reality_audit.md
echo REPORT 2: qa_reports\17a\business_readiness.md
echo REPORT 3: qa_reports\17a\backend_trace.json
echo UNVERIFIED: real Gemini, hosted Auth/App Check, cross-project IAM, merchant inventory.
echo No application files, cloud configurations, or deployments were changed.
endlocal
