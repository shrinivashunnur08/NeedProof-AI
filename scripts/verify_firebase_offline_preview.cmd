@echo off
setlocal
cd /d "%~dp0.."
if not exist backend\.venv\Scripts\python.exe (
  echo ERROR: Missing backend virtual environment.
  exit /b 1
)
backend\.venv\Scripts\python.exe scripts\apply_firebase_offline_preview.py --check || exit /b 1
pushd backend
.venv\Scripts\python.exe -m pytest -q tests\test_firebase_offline_preview.py
if errorlevel 1 (popd & exit /b 1)
popd
pushd frontend
call npm run build
if errorlevel 1 (popd & exit /b 1)
popd
echo PASS: Offline Firebase UX contracts and frontend build. No cloud calls or deployments.
endlocal
