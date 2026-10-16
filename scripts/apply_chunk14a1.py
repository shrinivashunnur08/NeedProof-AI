"""NeedProof 14A.1 guarded, local-only installer for commit 358714b.
No cloud API calls; production and frontend feature flags are OFF by default.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
BACK = ROOT / "backend/app/cloud_decision_api.py"
FRONT = ROOT / "frontend/src/FreeShowcase.tsx"
REQUIRED = [
    ROOT / "backend/app/evidence_planner_14a1.py",
    ROOT / "backend/tests/test_cloud_14a1.py",
    ROOT / "frontend/src/lib/evidencePlanner14a1.ts",
    ROOT / "frontend/src/components/EvidencePlanner14A1.tsx",
]
EXPECTED_HASHES = {
    "backend/app/cloud_decision_api.py": "36bc5ed4221f3b0466573b6b9fcb949fca3b87998650c222d12aa58e2fcdc033",
    "frontend/src/FreeShowcase.tsx": "1412b72d46e61e08c005720d89402a2c2a7c7e68254478435e6a7c15caf838cc",
}
BACK_IMPORT_ANCHOR = "from app.product_retrieval_13c2 import RetrievalInput, retrieve_and_review"
BACK_IMPORT = "from app.evidence_planner_14a1 import EvidencePlanInput14A1, evaluate_evidence_plan"
BACK_ROUTE_ANCHOR = '@app.post("/api/v1/products/research")'
BACK_ROUTE = '@app.post("/api/v1/decision/evidence-plan")'
FRONT_IMPORT_ANCHOR = 'import ProductResearch13C2 from "./components/ProductResearch13C2";'
FRONT_IMPORT = 'import EvidencePlanner14A1 from "./components/EvidencePlanner14A1";'
FRONT_FLAG = 'import { evidencePlanner14a1Enabled } from "./lib/evidencePlanner14a1";'
FRONT_JSX_ANCHOR = "          <MerchantEvidenceDesk />"
FRONT_TAG = "<EvidencePlanner14A1"


def die(message: str) -> None:
    sys.exit("STOP: " + message + "\nNo live cloud services were modified.")


def normalized(path: Path) -> str:
    return path.read_text("utf-8-sig").replace("\r\n", "\n")


def main() -> None:
    p = argparse.ArgumentParser()
    operation = p.add_mutually_exclusive_group(required=True)
    operation.add_argument("--check", action="store_true")
    operation.add_argument("--apply", action="store_true")
    args = p.parse_args()
    missing = [str(p.relative_to(ROOT)) for p in (BACK, FRONT, *REQUIRED) if not p.is_file()]
    if missing:
        die("Missing files (extract ZIP into project root): " + ", ".join(missing))
    backend, frontend = normalized(BACK), normalized(FRONT)
    indicators = (
        BACK_IMPORT in backend,
        BACK_ROUTE in backend,
        FRONT_IMPORT in frontend,
        FRONT_FLAG in frontend,
        FRONT_TAG in frontend,
    )
    if all(indicators):
        print("PASS: Chunk 14A.1 already integrated; feature flags remain OFF by default.")
        return
    if any(indicators):
        die("Partial or divergent 14A.1 installation; inspect your source first")
    for path, content in ((BACK, backend), (FRONT, frontend)):
        key = str(path.relative_to(ROOT)).replace("\\", "/")
        actual = sha256(content.encode()).hexdigest()
        if actual != EXPECTED_HASHES[key]:
            die(f"Source differs from audited commit 358714b: {key}. Do not overwrite local changes.")
    for body, marker in (
        (backend, BACK_IMPORT_ANCHOR), (backend, BACK_ROUTE_ANCHOR),
        (frontend, FRONT_IMPORT_ANCHOR), (frontend, FRONT_JSX_ANCHOR),
    ):
        if body.count(marker) != 1:
            die("Expected source anchor missing/duplicated: " + marker)
    backend = backend.replace(BACK_IMPORT_ANCHOR, BACK_IMPORT_ANCHOR + "\n" + BACK_IMPORT, 1)
    route = '''@app.post("/api/v1/decision/evidence-plan")
def hypothetical_evidence_plan(payload: EvidencePlanInput14A1, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("EVIDENCE_PLANNER_14A1_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Evidence verification planning is not enabled")
    try:
        return evaluate_evidence_plan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


'''
    backend = backend.replace(BACK_ROUTE_ANCHOR, route + BACK_ROUTE_ANCHOR, 1)
    frontend = frontend.replace(FRONT_IMPORT_ANCHOR,
        FRONT_IMPORT_ANCHOR + "\n" + FRONT_IMPORT + "\n" + FRONT_FLAG, 1)
    jsx = '''          {evidencePlanner14a1Enabled && (
            <EvidencePlanner14A1
              requestedProduct={isCurrent && intent ? intent.requested_product : null}
              extractedBudget={isCurrent && intent ? intent.budget_amount : null}
              onEvent={recordEvent}
            />
          )}

          <MerchantEvidenceDesk />'''
    frontend = frontend.replace(FRONT_JSX_ANCHOR, jsx, 1)
    if backend.count(BACK_ROUTE) != 1 or frontend.count(FRONT_TAG) != 1:
        die("Post-patch integrity check failed")
    print("PASS: 14A.1 patch matches audited 358714b source and API/React anchors.")
    print("Would change only backend/app/cloud_decision_api.py and frontend/src/FreeShowcase.tsx.")
    if args.check:
        print("DRY RUN: no code changes, network calls, costs, or feature-flag changes.")
        return
    backup = ROOT / "backup_14a1"
    if backup.exists():
        die(f"Backup already exists: {backup}; no overwrite permitted")
    backup.mkdir()
    originals = {BACK: BACK.read_bytes(), FRONT: FRONT.read_bytes()}
    try:
        for path, raw in originals.items():
            (backup / (path.name + ".before_14a1")).write_bytes(raw)
        for path, content in ((BACK, backend), (FRONT, frontend)):
            temp = path.with_name(path.name + ".14a1.tmp")
            temp.write_text(content, encoding="utf-8", newline="\n")
            os.replace(temp, path)
    except Exception as exc:
        for path, raw in originals.items():
            path.write_bytes(raw)
        die(f"Patch failed; originals restored ({type(exc).__name__})")
    print("SUCCESS: 14A.1 integrated locally. Backend and frontend flags remain OFF by default.")
    print("Backups:", backup)
    print(r"Next: scripts\verify_chunk14a1.cmd")


if __name__ == "__main__":
    main()
