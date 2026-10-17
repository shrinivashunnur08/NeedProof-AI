@echo off
setlocal
cd /d "%~dp0.." || exit /b 1
set "PYTHON=backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (echo STOP: Missing backend virtual environment. & exit /b 1)
"%PYTHON%" scripts\apply_chunk16c4.py --check || exit /b 1
pushd backend
.venv\Scripts\python.exe -m pytest -q tests\test_chunk16c4_route_split.py
if errorlevel 1 (popd & exit /b 1)
popd
rem Re-check the existing local acceptance gate, including the initial build.
call scripts\verify_chunk16c3.cmd || exit /b 1
rem Build the PUBLIC judge showcase explicitly; does not deploy it.
pushd frontend
set "VITE_PUBLIC_SHOWCASE=true"
call npm run build
if errorlevel 1 (popd & exit /b 1)
popd
"%PYTHON%" scripts\apply_chunk16c4.py --report || exit /b 1
"%PYTHON%" scripts\apply_chunk16c4.py --check || exit /b 1
echo PASS: 16C.4 route split, 16C.3 QA, PUBLIC frontend build and entry-size report.
echo NO cloud deployment or hosted Auth/Firestore checks. Complete browser QA manually.
exit /b 0
