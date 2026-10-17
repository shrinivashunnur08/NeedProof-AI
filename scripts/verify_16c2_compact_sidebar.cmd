@echo off
setlocal
cd /d "%~dp0.."
if errorlevel 1 exit /b 1
if exist "backend\.venv\Scripts\python.exe" (
  set "PY=backend\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)
"%PY%" scripts\apply_16c2_compact_sidebar.py --check
if errorlevel 1 exit /b 1
"%PY%" -m pytest -q backend\tests\test_compact_sidebar_16c2.py
if errorlevel 1 exit /b 1
pushd frontend
call npm run build
if errorlevel 1 (
  popd
  echo STOP: Frontend build failed. Do not commit.
  exit /b 1
)
popd
"%PY%" scripts\apply_16c2_compact_sidebar.py --check
if errorlevel 1 exit /b 1
echo PASS: Compact desktop sidebar, navigation, mobile preservation and frontend build.
echo NO Firebase, Cloud Run, Firestore, Places, Gemini or billing settings changed.
exit /b 0
