"""NeedProof Chunk 14B.4 — guarded local source-only installer.

Never executes cloud commands, changes deployments or enables feature flags.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BACK=ROOT/'backend/app/cloud_decision_api.py'
FRONT=ROOT/'frontend/src/FreeShowcase.tsx'
ADD=[
 'backend/app/bi_command_center_14b4.py',
 'backend/tests/test_cloud_14b4.py',
 'frontend/src/components/BusinessCommandCenter14B4.tsx',
 'frontend/src/lib/biCommandCenter14b4.ts',
]
EXPECTED={
 'backend/app/cloud_decision_api.py':'0bf11fa66cdf55c2bc4f4b72ea9b7b9f2c018de072c6ba22989865a54586b90f',
 'frontend/src/FreeShowcase.tsx':'e5a1a7d10db0c599b9fd1bc042edb712cd9a2b0bd73e73890bdb787560d857d4',
}
BACK_IMPORT='from app.inventory_intelligence_14b3 import InventoryInput14B3, evaluate_inventory_14b3'
BACK_ROUTE='@app.post("/api/v1/analytics/inventory-review")'
NEW_BACK_IMPORT='from app.bi_command_center_14b4 import BIInput14B4, evaluate_bi_command_center_14b4'
NEW_ROUTE='@app.post("/api/v1/analytics/command-center")'
FRONT_IMPORT='import InventoryReview14B3 from "./components/InventoryReview14B3";'
NEW_FRONT_IMPORT='import BusinessCommandCenter14B4 from "./components/BusinessCommandCenter14B4";'
NEW_FRONT_FLAG='import { biCommandCenter14b4Enabled } from "./lib/biCommandCenter14b4";'
FRONT_ANCHOR='          <MerchantEvidenceDesk />'
NEW_FRONT_TAG='<BusinessCommandCenter14B4'


def die(msg):
    raise SystemExit('STOP: '+msg+'\nNo production cloud resource was accessed or modified.')


def norm(p):
    return p.read_text(encoding='utf-8-sig').replace('\r\n','\n')


def main():
    parser=argparse.ArgumentParser(description='Offline-only NeedProof 14B.4 integration')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true')
    mode.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    missing=[p for p in (BACK,FRONT,*(ROOT/name for name in ADD)) if not p.exists()]
    if missing:die('Extract ZIP into repository root. Missing '+', '.join(str(p.relative_to(ROOT)) for p in missing))
    back,front=norm(BACK),norm(FRONT)
    marks=[NEW_BACK_IMPORT in back,NEW_ROUTE in back,NEW_FRONT_IMPORT in front,NEW_FRONT_FLAG in front,NEW_FRONT_TAG in front]
    if all(marks):
        if back.count(NEW_ROUTE)!=1 or front.count(NEW_FRONT_TAG)!=1:
            die('Duplicate 14B.4 wiring detected; inspect manually')
        print('PASS: Chunk 14B.4 already integrated. Both feature flags default OFF.')
        return
    if any(marks):die('Partial 14B.4 patch found; will not overwrite or force merge')
    for path,data in ((BACK,back),(FRONT,front)):
        name=path.relative_to(ROOT).as_posix()
        if sha256(data.encode('utf-8')).hexdigest()!=EXPECTED[name]:
            die('Source SHA256 mismatch relative to 58d5e84: '+name)
    for contents,anchor in ((back,BACK_IMPORT),(back,BACK_ROUTE),(front,FRONT_IMPORT),(front,FRONT_ANCHOR)):
        if contents.count(anchor)!=1:die('Missing or duplicate source integration anchor: '+anchor)
    route='''@app.post("/api/v1/analytics/command-center")
def bi_command_center_14b4(payload: BIInput14B4, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("BI_COMMAND_CENTER_14B4_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="BI command center is disabled")
    return evaluate_bi_command_center_14b4(payload)


'''
    next_back=back.replace(BACK_IMPORT,BACK_IMPORT+'\n'+NEW_BACK_IMPORT,1).replace(BACK_ROUTE,route+BACK_ROUTE,1)
    next_front=front.replace(FRONT_IMPORT,FRONT_IMPORT+'\n'+NEW_FRONT_IMPORT+'\n'+NEW_FRONT_FLAG,1)
    next_front=next_front.replace(FRONT_ANCHOR,'''          {biCommandCenter14b4Enabled && (
            <BusinessCommandCenter14B4 onEvent={recordEvent} />
          )}

          <MerchantEvidenceDesk />''',1)
    if next_back.count(NEW_ROUTE)!=1 or next_front.count(NEW_FRONT_TAG)!=1:
        die('Proposed 14B.4 integration failed sanity check')
    print('PASS: 14B.4 source SHA256 and integration anchors match committed 58d5e84 baseline.')
    print('Would modify only backend/app/cloud_decision_api.py and frontend/src/FreeShowcase.tsx.')
    if args.check:
        print('DRY RUN: no source files, deployment flags, cloud APIs or billing settings changed.')
        return
    backup=ROOT/'backup_14b4'
    if backup.exists():die('Backup directory already exists; preserve it instead of overwriting')
    original={BACK:BACK.read_bytes(),FRONT:FRONT.read_bytes()}
    backup.mkdir()
    for p,content in original.items(): (backup/(p.name+'.before_14b4')).write_bytes(content)
    try:
        for p,value in ((BACK,next_back),(FRONT,next_front)):
            temp=p.with_name(p.name+'.14b4.tmp')
            temp.write_text(value,encoding='utf-8',newline='\n')
            os.replace(temp,p)
    except Exception as ex:
        for p,content in original.items():p.write_bytes(content)
        die('Atomic patch failed; restored originals: '+type(ex).__name__)
    print('SUCCESS: Chunk 14B.4 installed LOCALLY. API and React feature flags default OFF.')
    print('Backups: '+str(backup))
    print(r'NEXT: scripts\verify_chunk14b4.cmd')

if __name__=='__main__':main()
