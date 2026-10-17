@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONPATH=%CD%\backend"
echo ============================================================
echo NEEDPROOF 17G - JUDGE EXPERIENCE / SYNTHETIC CLAIMS GATE
echo ============================================================
call scripts\verify_chunk17f.cmd
if errorlevel 1 (
  echo ERROR: Prior 17F benchmark / frontend verification failed.
  exit /b 1
)
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_chunk17g_jury_evidence.py
if errorlevel 1 exit /b 1
backend\.venv\Scripts\python.exe scripts\verify_chunk17g_evidence.py
if errorlevel 1 exit /b 1
echo PASS: 17G evidence panel + benchmark truth gate + full frontend build.
echo NOTE: Still synthetic. No live Gemini, hosted Auth, or real merchant data verified.
exit /b 0
