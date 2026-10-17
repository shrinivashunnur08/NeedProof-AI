@echo off
cd /d "%~dp0.."
if not exist "backend\.venv\Scripts\python.exe" (echo Missing backend venv & exit /b 1)
set "ENVIRONMENT=development"
set "NEEDPROOF_17C_LOCAL_ENABLED=true"
set "NEEDPROOF_CLOUD_PREVIEW=false"
echo LOCAL ONLY: http://127.0.0.1:8000 - press Ctrl+C to stop.
"backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
