@echo off
setlocal
cd /d "%~dp0.."
set "PY=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo STOP: backend virtual environment not present.
  exit /b 1
)
"%PY%" scripts\check_chunk16b2b.py --check
if errorlevel 1 exit /b 1
pushd backend
"%PY%" -m pytest -q tests\test_release_gate_16b2b.py
if errorlevel 1 (
  popd
  echo STOP: Chunk 16B.2B offline tests failed.
  exit /b 1
)
popd
call scripts\verify_chunk16b2.cmd
if errorlevel 1 (
  echo STOP: Existing 16B.2A integration verification failed.
  exit /b 1
)
echo PASS: Chunk 16B.2B local release gate. Real cloud integration is NOT verified.
endlocal
