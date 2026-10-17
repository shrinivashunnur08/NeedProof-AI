@echo off
setlocal
cd /d "%~dp0.." || exit /b 1
set "PYTHON=backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo STOP: Missing backend Python virtual environment.
  exit /b 1
)
"%PYTHON%" scripts\audit_chunk16c3.py --check || exit /b 1
pushd backend
.venv\Scripts\python.exe -m pytest -q tests\test_chunk16c3_release_qa.py
if errorlevel 1 (popd & exit /b 1)
popd
pushd frontend
call npm run build
if errorlevel 1 (popd & exit /b 1)
popd
"%PYTHON%" scripts\audit_chunk16c3.py --report || exit /b 1
echo PASS: 16C.3 local static checks, safety tests, and frontend build.
echo NOTE: Visual QA and real Auth/App Check/Firestore verification remain outstanding.
echo NO cloud resources were deployed or modified.
exit /b 0
