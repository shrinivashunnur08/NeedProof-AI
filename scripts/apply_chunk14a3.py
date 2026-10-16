"""Guarded 14A.3 source patch for audited 2f7d898 checkout; no network."""
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACK = ROOT / "backend/app/cloud_decision_api.py"
FRONT = ROOT / "frontend/src/FreeShowcase.tsx"
ADDITIONS = [
    "backend/app/decision_orchestrator_14a3.py",
    "backend/tests/test_cloud_14a3.py",
    "frontend/src/components/DecisionOrchestrator14A3.tsx",
    "frontend/src/lib/decisionOrchestrator14a3.ts",
]
BASE_HASH = {
    "backend/app/cloud_decision_api.py": "020aa8db6dcd30d0e2ba9760444a30fe8fe6438cf9deb035d83b77aeefc121ed",
    "frontend/src/FreeShowcase.tsx": "06aca904174826a166264d5b33337ec922562e1031cb461ebbfd14c8df8b3207",
}
BACK_ANCHOR = "from app.basket_optimizer_14a2 import BasketPlan14A2, evaluate_basket_14a2"
BACK_ROUTE = '@app.post("/api/v1/commerce/basket-plan")'
FRONT_ANCHOR = 'import BasketOptimizer14A2 from "./components/BasketOptimizer14A2";'
FRONT_JSX = "          <MerchantEvidenceDesk />"
NEW_IMPORT = 'from app.decision_orchestrator_14a3 import OrchestrationInput14A3, orchestrate_decision_14a3'
NEW_ROUTE = '@app.post("/api/v1/decision/orchestrate")'
NEW_FRONT = 'import DecisionOrchestrator14A3 from "./components/DecisionOrchestrator14A3";'
NEW_FLAG = 'import { decisionOrchestrator14a3Enabled } from "./lib/decisionOrchestrator14a3";'
NEW_TAG = "<DecisionOrchestrator14A3"


def abort(reason: str) -> None:
    raise SystemExit("STOP: " + reason + "\nNo cloud services or configuration were changed.")


def normalized(path: Path) -> str:
    return path.read_text("utf-8-sig").replace("\r\n", "\n")


def run() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    missing = [p for p in (BACK, FRONT, *(ROOT / x for x in ADDITIONS)) if not p.is_file()]
    if missing:
        abort("Missing required files; extract ZIP into repository root: " + ", ".join(str(p.relative_to(ROOT)) for p in missing))
    back, front = normalized(BACK), normalized(FRONT)
    anchors = [NEW_IMPORT in back, NEW_ROUTE in back, NEW_FRONT in front, NEW_FLAG in front, NEW_TAG in front]
    if all(anchors):
        print("PASS: Chunk 14A.3 is already integrated. No feature flags changed.")
        return
    if any(anchors):
        abort("Partial 14A.3 patch detected. Restore original source or inspect manually; no overwrite.")
    for path, contents in ((BACK, back), (FRONT, front)):
        key = path.relative_to(ROOT).as_posix()
        if sha256(contents.encode("utf-8")).hexdigest() != BASE_HASH[key]:
            abort("Source drift from audited commit 2f7d898: " + key)
    for body, anchor in ((back, BACK_ANCHOR), (back, BACK_ROUTE),
                         (front, FRONT_ANCHOR), (front, FRONT_JSX)):
        if body.count(anchor) != 1:
            abort("Missing or duplicate integration anchor: " + anchor)
    route = '''@app.post("/api/v1/decision/orchestrate")
def evidence_orchestration_14a3(payload: OrchestrationInput14A3, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("DECISION_ORCHESTRATOR_14A3_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Evidence orchestration is disabled")
    try:
        return orchestrate_decision_14a3(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


'''
    back = back.replace(BACK_ANCHOR, BACK_ANCHOR + "\n" + NEW_IMPORT, 1)
    back = back.replace(BACK_ROUTE, route + BACK_ROUTE, 1)
    front = front.replace(FRONT_ANCHOR, FRONT_ANCHOR + "\n" + NEW_FRONT + "\n" + NEW_FLAG, 1)
    jsx = '''          {decisionOrchestrator14a3Enabled && (
            <DecisionOrchestrator14A3
              requestedProduct={isCurrent && intent ? intent.requested_product : null}
              extractedBudget={isCurrent && intent ? intent.budget_amount : null}
              onEvent={recordEvent}
            />
          )}

          <MerchantEvidenceDesk />'''
    front = front.replace(FRONT_JSX, jsx, 1)
    if back.count(NEW_ROUTE) != 1 or front.count(NEW_TAG) != 1:
        abort("Rendered patch integrity check failed")
    print("PASS: Chunk 14A.3 source anchors and SHA256 match committed 2f7d898.")
    print("Would modify only backend/app/cloud_decision_api.py and frontend/src/FreeShowcase.tsx.")
    if args.check:
        print("DRY RUN: source, production configuration and cloud resources untouched.")
        return
    backup = ROOT / "backup_14a3"
    if backup.exists():
        abort("Existing backup_14a3 prevents safe reapplication")
    sources = {BACK: BACK.read_bytes(), FRONT: FRONT.read_bytes()}
    backup.mkdir()
    for path, raw in sources.items():
        (backup / (path.name + ".before_14a3")).write_bytes(raw)
    try:
        for path, contents in ((BACK, back), (FRONT, front)):
            temp = path.with_name(path.name + ".14a3.tmp")
            temp.write_text(contents, encoding="utf-8", newline="\n")
            os.replace(temp, path)
    except Exception as exc:
        for path, raw in sources.items():
            path.write_bytes(raw)
        abort("Source write failed and original files were restored (" + type(exc).__name__ + ")")
    print("SUCCESS: Chunk 14A.3 integrated locally, new backend/frontend flags OFF.")
    print("Backup folder: " + str(backup))
    print(r"NEXT: scripts\verify_chunk14a3.cmd")


if __name__ == "__main__":
    run()
