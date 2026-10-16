"""14A.2 deterministic guarded patch. No network calls or cloud changes."""
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
BACK = ROOT / 'backend/app/cloud_decision_api.py'
FRONT = ROOT / 'frontend/src/FreeShowcase.tsx'
FILES = [
    'backend/app/basket_optimizer_14a2.py',
    'backend/tests/test_cloud_14a2.py',
    'frontend/src/lib/basketOptimizer14a2.ts',
    'frontend/src/components/BasketOptimizer14A2.tsx',
]
HASHES = {
    'backend/app/cloud_decision_api.py': '7715f8c0a642e923c5360fd249bad4fad4962e6d901f1a72052a7caabbd7aab5',
    'frontend/src/FreeShowcase.tsx': '141f040be59c803ca05c301aaa4f3281b90d9d55f69f4d774387b3db22813503',
}
IMPORT_BACK = 'from app.basket_optimizer_14a2 import BasketPlan14A2, evaluate_basket_14a2'
ROUTE = '@app.post("/api/v1/commerce/basket-plan")'
IMPORT_FRONT = 'import BasketOptimizer14A2 from "./components/BasketOptimizer14A2";'
FLAG_FRONT = 'import { basketOptimizer14a2Enabled } from "./lib/basketOptimizer14a2";'
TAG = '<BasketOptimizer14A2'
ANCHOR_BACK = 'from app.evidence_planner_14a1 import EvidencePlanInput14A1, evaluate_evidence_plan'
ANCHOR_ROUTE = '@app.post("/api/v1/decision/evidence-plan")'
ANCHOR_FRONT = 'import EvidencePlanner14A1 from "./components/EvidencePlanner14A1";'
ANCHOR_JSX = '          <MerchantEvidenceDesk />'


def fail(reason):
    sys.exit('STOP: ' + reason + '\nNo live infrastructure, source files, or feature flags were changed by the failed check.')


def normalize(path):
    return path.read_text('utf-8-sig').replace('\r\n', '\n')


def main():
    parser = argparse.ArgumentParser()
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--check', action='store_true')
    operation.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    missing = [p for p in [BACK,FRONT,*[ROOT/s for s in FILES]] if not p.is_file()]
    if missing:
        fail('Missing package files (extract ZIP to project root): ' + ', '.join(str(p.relative_to(ROOT)) for p in missing))
    backend, frontend = normalize(BACK), normalize(FRONT)
    indicators = [IMPORT_BACK in backend, ROUTE in backend, IMPORT_FRONT in frontend,
                  FLAG_FRONT in frontend, TAG in frontend]
    if all(indicators):
        print('PASS: Chunk 14A.2 already integrated. Feature flags still default OFF.')
        return
    if any(indicators):
        fail('Partial 14A.2 installation detected; do not apply a second patch')
    for path, contents in [(BACK,backend),(FRONT,frontend)]:
        key = path.relative_to(ROOT).as_posix()
        if sha256(contents.encode('utf-8')).hexdigest() != HASHES[key]:
            fail('Source differs from audited commit 0c3028c: ' + key)
    for contents, anchor in [(backend,ANCHOR_BACK),(backend,ANCHOR_ROUTE),
                             (frontend,ANCHOR_FRONT),(frontend,ANCHOR_JSX)]:
        if contents.count(anchor) != 1:
            fail('Missing or duplicate anchor: ' + anchor)
    backend = backend.replace(ANCHOR_BACK, ANCHOR_BACK + '\n' + IMPORT_BACK, 1)
    route = '''@app.post("/api/v1/commerce/basket-plan")
def basket_scenario_plan(payload: BasketPlan14A2, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("BASKET_OPTIMIZER_14A2_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Basket scenario planner is disabled")
    return evaluate_basket_14a2(payload)


'''
    backend = backend.replace(ANCHOR_ROUTE,route+ANCHOR_ROUTE,1)
    frontend = frontend.replace(ANCHOR_FRONT,ANCHOR_FRONT + '\n' + IMPORT_FRONT + '\n' + FLAG_FRONT,1)
    jsx = '''          {basketOptimizer14a2Enabled && (
            <BasketOptimizer14A2 onEvent={recordEvent} />
          )}

          <MerchantEvidenceDesk />'''
    frontend = frontend.replace(ANCHOR_JSX,jsx,1)
    if backend.count(ROUTE) != 1 or frontend.count(TAG) != 1:
        fail('Patched content integrity check failed')
    print('PASS: 14A.2 checked against committed 0c3028c source and 14A.1 anchors.')
    print('Would modify only backend/app/cloud_decision_api.py and frontend/src/FreeShowcase.tsx.')
    if args.check:
        print('DRY RUN: no changes to source, Cloud Run, Firebase, Gemini, or IAM.')
        return
    backup=ROOT/'backup_14a2'
    if backup.exists():
        fail('Backup already exists: backup_14a2; refuse to overwrite')
    originals={BACK:BACK.read_bytes(),FRONT:FRONT.read_bytes()}
    backup.mkdir()
    for path, raw in originals.items():
        (backup/(path.name+'.before_14a2')).write_bytes(raw)
    try:
        for path, content in [(BACK,backend),(FRONT,frontend)]:
            tmp=path.with_name(path.name+'.14a2.tmp')
            tmp.write_text(content,encoding='utf-8',newline='\n')
            os.replace(tmp,path)
    except Exception as ex:
        for path, raw in originals.items():
            path.write_bytes(raw)
        fail('Installer failed and original sources were restored ('+type(ex).__name__+')')
    print('SUCCESS: Chunk 14A.2 integrated locally. Both deployment flags default OFF.')
    print('Backups:',backup)
    print(r'NEXT: scripts\verify_chunk14a2.cmd')

if __name__ == '__main__':
    main()
