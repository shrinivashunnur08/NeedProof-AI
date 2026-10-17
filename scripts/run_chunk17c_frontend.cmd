@echo off
cd /d "%~dp0..\frontend"
if not exist node_modules (echo Missing node_modules. Run: npm ci & exit /b 1)
set "VITE_PUBLIC_SHOWCASE=true"
set "VITE_NP17C_LOCAL_DEV=true"
set "VITE_NP17C_CLOUD_ENABLED=false"
echo LOCAL ONLY: http://127.0.0.1:5173 - press Ctrl+C to stop.
call npm run dev -- --host 127.0.0.1
