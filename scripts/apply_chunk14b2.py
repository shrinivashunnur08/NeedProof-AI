"""Source-hash guarded 14B.2 local patch; no cloud calls or flag mutations."""
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BACK=ROOT/'backend/app/cloud_decision_api.py'
FRONT=ROOT/'frontend/src/FreeShowcase.tsx'
ADDITIONS=[
    'backend/app/retail_segments_14b2.py', 'backend/tests/test_cloud_14b2.py',
    'frontend/src/components/RetailInsights14B2.tsx','frontend/src/lib/retailInsights14b2.ts',
]
BASE_HASH={
    'backend/app/cloud_decision_api.py':'966f33c4caf464db4237f262d671529ad8a6276d4dbd631ee4d7e4f73d1be4fb',
    'frontend/src/FreeShowcase.tsx':'d92ecc09628644830b46d71ccbced2eaedf06c64fb381ea71e718eadb9eaa8f1',
}
BACK_ANCHOR='from app.retail_forecast_14b1 import ForecastInput14B1, evaluate_retail_forecast_14b1'
ROUTE_ANCHOR='@app.post("/api/v1/analytics/sales-forecast")'
FRONT_ANCHOR='import RetailForecast14B1 from "./components/RetailForecast14B1";'
FRONT_JSX='          <MerchantEvidenceDesk />'
NEW_BACK='from app.retail_segments_14b2 import CommerceInsightsInput14B2, evaluate_commerce_insights_14b2'
NEW_ROUTE='@app.post("/api/v1/analytics/cohort-basket-insights")'
NEW_FRONT='import RetailInsights14B2 from "./components/RetailInsights14B2";'
NEW_FRONT_FLAG='import { retailInsights14b2Enabled } from "./lib/retailInsights14b2";'
NEW_TAG='<RetailInsights14B2'


def stop(msg):
    raise SystemExit('STOP: '+msg+'\nNo cloud resource was changed by this script.')


def normalized(path):
    return path.read_text(encoding='utf-8-sig').replace('\r\n','\n')


def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args=parser.parse_args()
    missing=[p for p in (BACK,FRONT,*(ROOT/x for x in ADDITIONS)) if not p.is_file()]
    if missing:
        stop('Missing files. Extract archive directly into repo root: '+', '.join(str(p.relative_to(ROOT)) for p in missing))
    back,front=normalized(BACK),normalized(FRONT)
    markers=[NEW_BACK in back,NEW_ROUTE in back,NEW_FRONT in front,NEW_FRONT_FLAG in front,NEW_TAG in front]
    if all(markers):
        if back.count(NEW_ROUTE)!=1 or front.count(NEW_TAG)!=1:
            stop('Duplicate 14B.2 markers found; inspect manually')
        print('PASS: Chunk 14B.2 already integrated. Feature flags remain OFF by default.')
        return
    if any(markers): stop('Partial 14B.2 patch detected. Stop; do not force overwrite.')
    for path,contents in ((BACK,back),(FRONT,front)):
        key=path.relative_to(ROOT).as_posix()
        if sha256(contents.encode('utf-8')).hexdigest()!=BASE_HASH[key]:
            stop('Source does not match expected committed 4696bf1 baseline: '+key)
    for text,anchor in ((back,BACK_ANCHOR),(back,ROUTE_ANCHOR),(front,FRONT_ANCHOR),(front,FRONT_JSX)):
        if text.count(anchor)!=1: stop('Missing/duplicate integration anchor: '+anchor)

    route='''@app.post("/api/v1/analytics/cohort-basket-insights")
def cohort_and_basket_insights_14b2(payload: CommerceInsightsInput14B2, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("RETAIL_INSIGHTS_14B2_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Retail cohort/basket analysis is disabled")
    return evaluate_commerce_insights_14b2(payload)


'''
    patched_back=back.replace(BACK_ANCHOR,BACK_ANCHOR+'\n'+NEW_BACK,1).replace(ROUTE_ANCHOR,route+ROUTE_ANCHOR,1)
    patched_front=front.replace(FRONT_ANCHOR,FRONT_ANCHOR+'\n'+NEW_FRONT+'\n'+NEW_FRONT_FLAG,1)
    jsx='''          {retailInsights14b2Enabled && (
            <RetailInsights14B2 onEvent={recordEvent} />
          )}

          <MerchantEvidenceDesk />'''
    patched_front=patched_front.replace(FRONT_JSX,jsx,1)
    if patched_back.count(NEW_ROUTE)!=1 or patched_front.count(NEW_TAG)!=1:
        stop('Sanity check of proposed patch failed.')
    print('PASS: Chunk 14B.2 anchors and SHA256 match committed 4696bf1 source.')
    print('Would modify only backend/app/cloud_decision_api.py and frontend/src/FreeShowcase.tsx.')
    if args.check:
        print('DRY RUN: no files, cloud resources or deployment flags changed.')
        return
    backup=ROOT/'backup_14b2'
    if backup.exists(): stop('backup_14b2 exists; preserve it and stop rather than overwrite')
    originals={BACK:BACK.read_bytes(),FRONT:FRONT.read_bytes()}
    backup.mkdir()
    for path,raw in originals.items():
        (backup/(path.name+'.before_14b2')).write_bytes(raw)
    try:
        for path,contents in ((BACK,patched_back),(FRONT,patched_front)):
            temp=path.with_name(path.name+'.14b2.tmp')
            temp.write_text(contents,encoding='utf-8',newline='\n')
            os.replace(temp,path)
    except Exception as exc:
        for path,raw in originals.items(): path.write_bytes(raw)
        stop('Write failed, originals restored ('+type(exc).__name__+')')
    print('SUCCESS: Chunk 14B.2 installed locally; backend/frontend flags default OFF.')
    print('Backup folder: '+str(backup))
    print(r'NEXT: scripts\verify_chunk14b2.cmd')

if __name__=='__main__': main()
