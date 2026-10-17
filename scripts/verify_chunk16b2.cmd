@echo off
setlocal
cd /d "%~dp0.."
set "PYTHON=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
 echo STOP: Backend venv not found; use the existing environment.
 exit /b 1
)
"%PYTHON%" scripts\preflight_chunk16b2.py --check
if errorlevel 1 exit /b 1
pushd backend
"%PYTHON%" -m pytest -q tests/test_release_gate_16b2.py
if errorlevel 1 (popd & echo STOP: 16B.2A source-gate tests failed. & exit /b 1)
popd
call scripts\verify_chunk16b.cmd
if errorlevel 1 (echo STOP: Existing security/emulator/regression verification failed. & exit /b 1)
echo PASS: 16B.2A offline live-readiness gate. NO real tokens tested and NO cloud calls.
endlocal
