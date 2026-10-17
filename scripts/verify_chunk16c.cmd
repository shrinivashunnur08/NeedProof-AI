@echo off
setlocal
cd /d "%~dp0.."
set "PY=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo STOP: Required backend Python virtual environment missing.
  exit /b 1
)
"%PY%" scripts\build_chunk16c_demo.py --check
if errorlevel 1 exit /b 1
"%PY%" scripts\build_chunk16c_demo.py --verify
if errorlevel 1 exit /b 1
pushd backend
"%PY%" -m pytest -q tests\test_chunk16c_demo.py tests\test_cloud_16a.py
if errorlevel 1 (
  popd
  echo STOP: Chunk 16C local tests failed
  exit /b 1
)
popd
echo PASS: Chunk 16C standalone offline replay and 16A engine integration.
echo Offline file: demo\needproof16c\offline-demo.html
echo OPTIONAL full regressions: scripts\verify_chunk16b2b.cmd
echo No production services, APIs, credentials or billing settings modified.
endlocal
