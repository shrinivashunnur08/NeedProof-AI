@echo off
setlocal
cd /d "%~dp0.."
echo === NeedProof 13B.2 Firestore LOCAL verification ===
python scripts\apply_chunk13b2_firestore.py --check
if errorlevel 1 goto :fail
pushd backend
set MERCHANT_EVIDENCE_STORAGE=firestore
python -c "from app.cloud_decision_api import app; import fastapi.routing as rt; contexts=getattr(rt,'iter_route_contexts',lambda routes: routes); p={r.path for r in contexts(app.routes) if hasattr(r,'path')}; required={'/api/v1/discovery/stores','/api/v1/decision/replan','/api/v1/decision/verification-plan','/api/v1/evidence/inquiries','/api/v1/evidence/inquiries/{inquiry_id}','/api/v1/evidence/merchant/inquiries','/api/v1/evidence/merchant/inquiries/{inquiry_id}/reports'}; missing=required-p; assert not missing, missing; print('PASS: Firestore adapter and legacy Cloud Run routes registered')"
if errorlevel 1 (popd & goto :fail)
set MERCHANT_EVIDENCE_STORAGE=
python -m pytest -q tests\test_cloud_13b.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13a_routes.py tests\test_public_places.py
if errorlevel 1 (popd & goto :fail)
popd
pushd frontend
call npm run build
if errorlevel 1 (popd & goto :fail)
popd
echo PASS: 13B.2 Firestore local validation. No cloud deployment performed.
exit /b 0
:fail
echo STOP: Release not validated. Do not deploy.
exit /b 1
