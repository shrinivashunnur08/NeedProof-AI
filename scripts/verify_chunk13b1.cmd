@echo off
setlocal
cd /d "%~dp0.."
echo === NeedProof Chunk 13B.1 ===
echo Checking source integration...
python -c "from pathlib import Path; a=Path('backend/app/cloud_decision_api.py').read_text(encoding='utf-8'); assert 'app.include_router(evidence_13b_router)' in a; print('PASS: API router registered')"
if errorlevel 1 goto :fail
pushd backend
python -m pytest -q tests\test_cloud_13b.py tests\test_cloud_13a_routes.py tests\test_public_places.py
if errorlevel 1 (popd & goto :fail)
popd
pushd frontend
call npm run build
if errorlevel 1 (popd & goto :fail)
popd
echo PASS: Chunk 13B.1 backend route tests and frontend build.
echo The feature remains OFF in production until Cloud SQL and operator-reviewed merchant access are ready.
exit /b 0
:fail
echo STOP: Do not deploy while a validation fails.
exit /b 1
