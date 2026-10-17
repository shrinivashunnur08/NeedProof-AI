@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo STOP: backend virtual environment missing.
  exit /b 1
)
cd /d "%ROOT%" || exit /b 1
"%PY%" scripts\check_chunk15b.py --check || goto :fail
"%PY%" scripts\run_benchmarks15b.py --repeat-verify || goto :fail
echo PASS: Offline synthetic benchmark finished. Review benchmark_reports\15b\report.md.
exit /b 0
:fail
echo STOP: 15B benchmark did not complete. No production change was made.
exit /b 1
