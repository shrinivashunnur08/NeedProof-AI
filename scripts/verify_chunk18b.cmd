@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONPATH=%CD%\backend"
echo ============================================================
echo NEEDPROOF 18B - ENGINEERING / ECONOMICS GATE - OFFLINE
echo ============================================================
if not exist backend\.venv\Scripts\python.exe (echo ERROR: Backend virtual environment missing & exit /b 1)
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_chunk18b_engineering.py
if errorlevel 1 exit /b 1
backend\.venv\Scripts\python.exe scripts\run_chunk18b_analysis.py
if errorlevel 1 exit /b 1
backend\.venv\Scripts\python.exe scripts\run_chunk18b_cost_model.py
if errorlevel 1 exit /b 1
call scripts\verify_chunk18a.cmd
if errorlevel 1 exit /b 1
echo PASS: Chunk 18B offline engineering study + 18A/17G local source regressions.
echo REMAINS: hosted security, actual Gemini/Cloud Run spend and independent merchant validation.
exit /b 0
