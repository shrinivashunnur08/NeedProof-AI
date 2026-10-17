"""NeedProof 14B.3: SHA-guarded local-only installer; no cloud operations."""
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BACK=ROOT/'backend/app/cloud_decision_api.py'
FRONT=ROOT/'frontend/src/FreeShowcase.tsx'
ADDITIONS=[
    'backend/app/inventory_intelligence_14b3.py',
    'backend/tests/test_cloud_14b3.py',
    'frontend/src/components/InventoryReview14B3.tsx',
    'frontend/src/lib/inventoryReview14b3.ts',
]
BASE_HASH={
    'backend/app/cloud_decision_api.py':'a401c6571a1f2d241d0dd0f41700a0cd4145519db23fa9b58d2472431154fc74',
    'frontend/src/FreeShowcase.tsx':'0f5a15c7917fbd4497d50a805a2b77840981a9aa849735aef83940d31ac40566',
}
BACK_ANCHOR='from app.retail_segments_14b2 import CommerceInsightsInput14B2, evaluate_commerce_insights_14b2'
ROUTE_ANCHOR='@app.post("/api/v1/analytics/cohort-basket-insights")'
FRONT_ANCHOR='import RetailInsights14B2 from "./components/RetailInsights14B2";'
FRONT_JSX='          <MerchantEvidenceDesk />'
NEW_BACK='from app.inventory_intelligence_14b3 import InventoryInput14B3, evaluate_inventory_14b3'
NEW_ROUTE='@app.post("/api/v1/analytics/inventory-review")'
NEW_FRONT='import InventoryReview14B3 from "./components/InventoryReview14B3";'
NEW_FLAG='import { inventoryReview14b3Enabled } from "./lib/inventoryReview14b3";'
NEW_TAG='<InventoryReview14B3'


def abort(message):
    raise SystemExit('STOP: '+message+'\nNo production resources were accessed or modified.')


def norm(path):
    return path.read_text(encoding='utf-8-sig').replace('\r\n','\n')


def main():
    parser=argparse.ArgumentParser(description='Local-only NeedProof 14B.3 integration')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true')
    mode.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    missing=[p for p in (BACK,FRONT,*(ROOT/path for path in ADDITIONS)) if not p.is_file()]
    if missing:
        abort('Missing files. Extract ZIP into repository root: '+', '.join(str(p.relative_to(ROOT)) for p in missing))
    back,front=norm(BACK),norm(FRONT)
    marks=[NEW_BACK in back,NEW_ROUTE in back,NEW_FRONT in front,NEW_FLAG in front,NEW_TAG in front]
    if all(marks):
        if back.count(NEW_ROUTE)!=1 or front.count(NEW_TAG)!=1:
            abort('Duplicate 14B.3 markers; inspect files manually')
        print('PASS: Chunk 14B.3 already integrated. Live deployment flags remain OFF by default.')
        return
    if any(marks): abort('Partial 14B.3 patch found; do not overwrite or force merge')
    for path,contents in ((BACK,back),(FRONT,front)):
        key=path.relative_to(ROOT).as_posix()
        if sha256(contents.encode('utf-8')).hexdigest()!=BASE_HASH[key]:
            abort('Source drift detected relative to commit 1d69db1: '+key)
    for content,anchor in ((back,BACK_ANCHOR),(back,ROUTE_ANCHOR),(front,FRONT_ANCHOR),(front,FRONT_JSX)):
        if content.count(anchor)!=1: abort('Integration anchor missing or duplicate: '+anchor)
    route='''@app.post("/api/v1/analytics/inventory-review")
def inventory_review_14b3(payload: InventoryInput14B3, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("INVENTORY_INTELLIGENCE_14B3_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Inventory intelligence is disabled")
    return evaluate_inventory_14b3(payload)


'''
    patched_back=back.replace(BACK_ANCHOR,BACK_ANCHOR+'\n'+NEW_BACK,1).replace(ROUTE_ANCHOR,route+ROUTE_ANCHOR,1)
    patched_front=front.replace(FRONT_ANCHOR,FRONT_ANCHOR+'\n'+NEW_FRONT+'\n'+NEW_FLAG,1)
    patched_front=patched_front.replace(FRONT_JSX,'''          {inventoryReview14b3Enabled && (
            <InventoryReview14B3 onEvent={recordEvent} />
          )}

          <MerchantEvidenceDesk />''',1)
    if patched_back.count(NEW_ROUTE)!=1 or patched_front.count(NEW_TAG)!=1:
        abort('Proposed patch failed sanity checks')
    print('PASS: 14B.3 source anchors and SHA256 match committed 1d69db1 source.')
    print('Would modify only backend/app/cloud_decision_api.py and frontend/src/FreeShowcase.tsx.')
    if args.check:
        print('DRY RUN: no source files changed, no cloud calls or flag changes.')
        return
    backup=ROOT/'backup_14b3'
    if backup.exists(): abort('Backup folder already exists: preserve it rather than overwriting')
    original={BACK:BACK.read_bytes(),FRONT:FRONT.read_bytes()}
    backup.mkdir()
    for path,raw in original.items():
        (backup/(path.name+'.before_14b3')).write_bytes(raw)
    try:
        for path,contents in ((BACK,patched_back),(FRONT,patched_front)):
            temp=path.with_name(path.name+'.14b3.tmp')
            temp.write_text(contents,encoding='utf-8',newline='\n')
            os.replace(temp,path)
    except Exception as ex:
        for path,raw in original.items(): path.write_bytes(raw)
        abort('Write failed, originals restored: '+type(ex).__name__)
    print('SUCCESS: 14B.3 integrated locally. API and frontend flags remain OFF.')
    print('Backup folder: '+str(backup))
    print(r'NEXT: scripts\verify_chunk14b3.cmd')

if __name__=='__main__':main()
