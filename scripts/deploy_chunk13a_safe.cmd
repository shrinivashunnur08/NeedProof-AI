@echo off
setlocal EnableExtensions
REM Run this script from anywhere; it resolves the NeedProof repo root itself.
cd /d "%~dp0.." || exit /b 1

echo === NeedProof 13A - predeployment verification ===
where python >nul 2>&1 || (echo ERROR: Python not found & exit /b 1)
where gcloud >nul 2>&1 || (echo ERROR: gcloud not found & exit /b 1)
where npm >nul 2>&1 || (echo ERROR: npm not found & exit /b 1)
python scripts\needproof_13a_guard.py preflight
if errorlevel 1 goto failed

pushd backend
python -m pytest -q tests\test_public_places.py tests\test_cloud_13a_routes.py
if errorlevel 1 (popd & goto failed)
popd

pushd frontend
call npm run build
if errorlevel 1 (popd & goto failed)
popd

echo === Deploy dedicated Cloud Run backend; preserve existing service config ===
REM IMPORTANT: --source backend uses backend/Dockerfile, NOT root Dockerfile.
REM No --set-env-vars, --set-secrets, --allow-unauthenticated or service-account changes.
gcloud run deploy needproof-decision-api --source backend --project needproof-ai --region asia-south1
if errorlevel 1 goto failed

echo === Check deployed health and actual 13A route ===
python scripts\needproof_13a_guard.py smoke
if errorlevel 1 goto failed

echo.
echo SUCCESS: Chunk 13A route is live on the dedicated Cloud Run API.
echo Verify live Firebase app's VITE_CLOUD_DECISION_API_URL matches this service.
echo Commit/push source files and scripts after confirming real discovery works.
exit /b 0

:failed
echo.
echo STOP: Deployment or verification failed. Do not redeploy Firebase Hosting blindly.
echo Review the error above. Existing source files have not been overwritten by this script.
exit /b 1
