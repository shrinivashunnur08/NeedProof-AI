"""Guarded, local-only installer for NeedProof 13C.1 (commit 0189889).

Run from any folder: python scripts/apply_chunk13c1.py --check / --apply
No cloud calls, IAM operations, package installs, feature enablement or paid services.
"""
from __future__ import annotations
import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACK = ROOT / "backend/app/cloud_decision_api.py"
FRONT = ROOT / "frontend/src/FreeShowcase.tsx"
EXPECTED = {
    BACK: "e3e80018f4af5493911f1df48ff9f87f262d90b44b3690c261aeeb76097d1961",
    FRONT: "ad38d4758932576c46f0e3037dbde6b73964bea30679dfa6fc80efde0084d96d",
}
REQUIRED = [
    ROOT / "backend/app/product_grounding_13c1.py",
    ROOT / "backend/tests/test_cloud_13c1.py",
    ROOT / "frontend/src/components/GroundedProductLab.tsx",
    ROOT / "frontend/src/lib/productGrounding13c1.ts",
]
BACK_IMPORT = "from app.product_grounding_13c1 import ReviewInput, review_product"
ROUTE_MARK = '@app.post("/api/v1/products/grounded-review")'
FRONT_IMPORT = 'import GroundedProductLab from "./components/GroundedProductLab";'
FLAG_IMPORT = 'import { productGrounding13c1Enabled } from "./lib/productGrounding13c1";'


def stop(msg):
    sys.exit("STOP: " + msg + "\nNo cloud resources were created.")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cli = argparse.ArgumentParser()
    action = cli.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--apply", action="store_true")
    args = cli.parse_args()

    missing = [str(f.relative_to(ROOT)) for f in [BACK, FRONT, *REQUIRED] if not f.is_file()]
    if missing:
        stop("Missing package files: " + ", ".join(missing))
    backend = BACK.read_text("utf-8-sig")
    frontend = FRONT.read_text("utf-8-sig")
    installed = ROUTE_MARK in backend and FRONT_IMPORT in frontend and '<GroundedProductLab' in frontend
    partial = any([ROUTE_MARK in backend, FRONT_IMPORT in frontend, '<GroundedProductLab' in frontend]) and not installed
    if partial:
        stop("Detected a partial 13C.1 installation; review files before retrying")
    if installed:
        print("PASS: Chunk 13C.1 already integrated. Production flag still defaults OFF.")
        return

    for path, expected in EXPECTED.items():
        if digest(path) != expected:
            stop("Source changed since snapshot 0189889: " + str(path.relative_to(ROOT)))

    anchors = [
        ('from app.public_places import DiscoveryInput, discover_stores', backend),
        ('@app.post("/api/v1/discovery/stores")', backend),
        ('import MerchantEvidenceDesk from "./components/MerchantEvidenceDesk";', frontend),
        ('          <MerchantEvidenceDesk />', frontend),
    ]
    for anchor, text in anchors:
        if text.count(anchor) != 1:
            stop("Missing or repeated integration anchor: " + anchor)

    backend = backend.replace('from app.public_places import DiscoveryInput, discover_stores',
                              'from app.public_places import DiscoveryInput, discover_stores\n' + BACK_IMPORT, 1)
    route = '''@app.post("/api/v1/products/grounded-review")
def product_grounding_review(payload: ReviewInput, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("PRODUCT_GROUNDING_13C1_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Product evidence review is not enabled")
    return review_product(payload)


'''
    backend = backend.replace('@app.post("/api/v1/discovery/stores")', route + '@app.post("/api/v1/discovery/stores")', 1)
    frontend = frontend.replace('import MerchantEvidenceDesk from "./components/MerchantEvidenceDesk";',
                                'import MerchantEvidenceDesk from "./components/MerchantEvidenceDesk";\n' + FRONT_IMPORT + '\n' + FLAG_IMPORT, 1)
    fragment = '''          {productGrounding13c1Enabled && (
            <GroundedProductLab
              requestedProduct={isCurrent && intent ? intent.requested_product : null}
              onEvent={recordEvent}
            />
          )}

          <MerchantEvidenceDesk />'''
    frontend = frontend.replace('          <MerchantEvidenceDesk />', fragment, 1)
    if backend.count(ROUTE_MARK) != 1 or frontend.count('<GroundedProductLab') != 1:
        stop("Post-patch integrity check failed")

    print("PASS: source checks and integration anchors match commit 0189889.")
    print("Would modify: backend/app/cloud_decision_api.py, frontend/src/FreeShowcase.tsx")
    if args.check:
        print("DRY RUN: no file changes, no cloud calls, all feature flags remain OFF.")
        return

    backup = ROOT / "backup_13c1"
    if backup.exists():
        stop("backup_13c1 already exists; installer will not overwrite backups")
    backup.mkdir()
    originals = {BACK: BACK.read_bytes(), FRONT: FRONT.read_bytes()}
    for path in (BACK, FRONT):
        shutil.copy2(path, backup / (path.name + ".before_13c1"))
    try:
        for path, content in ((BACK, backend), (FRONT, frontend)):
            temp = path.with_name(path.name + ".13c1.tmp")
            temp.write_text(content, encoding="utf-8")
            os.replace(temp, path)
    except Exception:
        for path, data in originals.items():
            path.write_bytes(data)
        stop("Installer write error; originals restored")
    print("SUCCESS: Chunk 13C.1 added locally; PRODUCT_GROUNDING_13C1_ENABLED and VITE_PRODUCT_GROUNDING_13C1_ENABLED default OFF.")
    print("Backups:", backup)
    print("NEXT: scripts\\verify_chunk13c1.cmd")


if __name__ == "__main__":
    main()
