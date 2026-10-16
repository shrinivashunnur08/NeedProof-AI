@echo off
setlocal
cd /d "%~dp0.."
echo === NeedProof 13B.3 LOCAL verification (no cloud changes) ===
python scripts\apply_chunk13b3.py --check || goto fail
pushd backend
python -m pytest -q tests\test_cloud_13b3.py tests\test_cloud_13b2_firestore.py tests\test_cloud_13b.py tests\test_public_places.py || (popd & goto fail)
popd
pushd frontend
call npm run build || (popd & goto fail)
popd
git diff --check || goto fail
echo PASS: Chunk 13B.3 backend tests and frontend build. No cloud deployment.
exit /b 0
:fail
echo STOP: Chunk 13B.3 validation failed. Do not deploy.
exit /b 1
