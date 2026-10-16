"""Guarded local-only installer for NeedProof Chunk 13C.2.
Does not deploy, call Google Cloud, change IAM, or enable feature flags.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
BACK = ROOT / "backend/app/cloud_decision_api.py"
FRONT = ROOT / "frontend/src/FreeShowcase.tsx"
REQUIRED = [
    ROOT / "backend/app/product_retrieval_13c2.py",
    ROOT / "backend/tests/test_cloud_13c2.py",
    ROOT / "frontend/src/components/ProductResearch13C2.tsx",
    ROOT / "frontend/src/lib/productRetrieval13c2.ts",
]
BACK_IMPORT = "from app.product_retrieval_13c2 import RetrievalInput, retrieve_and_review"
FRONT_IMPORT = 'import ProductResearch13C2 from "./components/ProductResearch13C2";'
FRONT_FLAG = 'import { productRetrieval13c2Enabled } from "./lib/productRetrieval13c2";'
BACK_ROUTE = '@app.post("/api/v1/products/research")'
FRONT_TAG = "<ProductResearch13C2"


def die(s: str):
    sys.exit("STOP: " + s + "\nNo cloud resource was modified.")


def main():
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    flags = parser.parse_args()
    missing = [str(p.relative_to(ROOT)) for p in (BACK, FRONT, *REQUIRED) if not p.is_file()]
    if missing:
        die("Missing files: " + ", ".join(missing))
    backend = BACK.read_text(encoding="utf-8-sig")
    frontend = FRONT.read_text(encoding="utf-8-sig")
    indicators = [BACK_IMPORT in backend, BACK_ROUTE in backend, FRONT_IMPORT in frontend,
                  FRONT_FLAG in frontend, FRONT_TAG in frontend]
    if all(indicators):
        print("PASS: Chunk 13C.2 already integrated. All deployment flags remain OFF by default.")
        return
    if any(indicators):
        die("Partial Chunk 13C.2 integration detected; do not blindly rerun installer")
    anchors = [
        (backend, 'from app.product_grounding_13c1 import ReviewInput, review_product'),
        (backend, '@app.post("/api/v1/products/grounded-review")'),
        (frontend, 'import GroundedProductLab from "./components/GroundedProductLab";'),
        (frontend, "          <MerchantEvidenceDesk />"),
    ]
    for content, anchor in anchors:
        if content.count(anchor) != 1:
            die("Required 13C.1/13B anchor missing or duplicated: " + anchor)

    backend = backend.replace('from app.product_grounding_13c1 import ReviewInput, review_product',
        'from app.product_grounding_13c1 import ReviewInput, review_product\n' + BACK_IMPORT, 1)
    route = '''@app.post("/api/v1/products/research")
def product_evidence_research(payload: RetrievalInput, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("PRODUCT_RETRIEVAL_13C2_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Document research is not enabled")
    return retrieve_and_review(payload)


'''
    backend = backend.replace('@app.post("/api/v1/products/grounded-review")',
                              route + '@app.post("/api/v1/products/grounded-review")', 1)
    frontend = frontend.replace('import GroundedProductLab from "./components/GroundedProductLab";',
                                'import GroundedProductLab from "./components/GroundedProductLab";\n' + FRONT_IMPORT + '\n' + FRONT_FLAG, 1)
    jsx = '''          {productRetrieval13c2Enabled && (
            <ProductResearch13C2
              requestedProduct={isCurrent && intent ? intent.requested_product : null}
              onEvent={recordEvent}
            />
          )}

          <MerchantEvidenceDesk />'''
    frontend = frontend.replace('          <MerchantEvidenceDesk />', jsx, 1)
    if backend.count(BACK_ROUTE) != 1 or frontend.count(FRONT_TAG) != 1:
        die("Post-patch integrity check failed")
    print("PASS: 13B/13C.1 source anchors are compatible with 13C.2.")
    print("Would modify: backend/app/cloud_decision_api.py; frontend/src/FreeShowcase.tsx")
    if flags.check:
        print("DRY RUN: no files changed, no cloud calls, feature flags remain OFF")
        return
    backup = ROOT / "backup_13c2"
    if backup.exists():
        die("Backup already exists; will not overwrite: " + str(backup))
    backup.mkdir()
    originals = {BACK: BACK.read_bytes(), FRONT: FRONT.read_bytes()}
    for p in originals:
        shutil.copy2(p, backup / (p.name + '.before_13c2'))
    try:
        for p, content in ((BACK, backend), (FRONT, frontend)):
            temp = p.with_name(p.name + '.13c2.tmp')
            temp.write_text(content, encoding='utf-8', newline='\n')
            os.replace(temp, p)
    except Exception:
        for p, original in originals.items():
            p.write_bytes(original)
        die("Write failed; originals restored")
    print("SUCCESS: Chunk 13C.2 integrated locally. API, UI and optional Gemini flags remain OFF.")
    print("Backups:", backup)
    print(r"NEXT: scripts\verify_chunk13c2.cmd")


if __name__ == "__main__":
    main()
