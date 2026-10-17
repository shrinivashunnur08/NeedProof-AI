@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONPATH=%CD%\backend"
echo ============================================================
echo NEEDPROOF 18C - FINAL OFFLINE RELEASE EVIDENCE GATE
echo ============================================================
if not exist backend\.venv\Scripts\python.exe (echo ERROR: Python venv missing & exit /b 1)
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_chunk18c_release.py
if errorlevel 1 exit /b 1
call scripts\verify_chunk18b.cmd
if errorlevel 1 exit /b 1
call scripts\verify_chunk17g.cmd
if errorlevel 1 exit /b 1
backend\.venv\Scripts\python.exe scripts\audit_chunk18c_release.py
if errorlevel 1 exit /b 1
echo PASS: Final offline code, documentation, benchmarks, and frontend build gate.
echo NOT CERTIFIED: live cloud, real merchants, real inventory, actual cost, independent participant outcomes or production release.
exit /b 0
