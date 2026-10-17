@echo off
setlocal
cd /d "%~dp0.."
set "PYTHON=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (echo STOP: Activate/install backend venv first. & exit /b 1)
set GUIDED_JOURNEY_16A_ENABLED=true
pushd backend
"%PYTHON%" -m pytest -q tests/test_cloud_16a.py
set "EC=%ERRORLEVEL%"
popd
if not "%EC%"=="0" (echo STOP: 16A local smoke failed. & exit /b %EC%)
echo PASS: Authenticated synthetic API behavior was checked locally with test-only identity overrides.
echo Cloud project and services were not accessed or changed.
endlocal
