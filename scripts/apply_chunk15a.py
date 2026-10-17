"""NeedProof Chunk 15A: source-hash-guarded offline security + code-splitting patch.

Only modifies backend/app/cloud_decision_api.py and frontend/src/FreeShowcase.tsx.
No Google APIs, network calls, deployments, Firebase config or billing mutations.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACK = ROOT / 'backend/app/cloud_decision_api.py'
FRONT = ROOT / 'frontend/src/FreeShowcase.tsx'
ADD = (
    ROOT / 'backend/app/api_guard_15a.py',
    ROOT / 'backend/tests/test_cloud_15a.py',
)
EXPECTED = {
    'backend/app/cloud_decision_api.py': 'ac6065231d54723efec46089850b5db45e1a3ad2c3035282ac0f45e6117313a3',
    'frontend/src/FreeShowcase.tsx': '2b5ca9296aec108ac46921d47f2b06f097628e1da64913401014adef56bab203',
}
COMPONENTS = [
    'MerchantEvidenceDesk','GroundedProductLab','ProductResearch13C2',
    'EvidencePlanner14A1','BasketOptimizer14A2','DecisionOrchestrator14A3',
    'RetailForecast14B1','RetailInsights14B2','InventoryReview14B3',
    'BusinessCommandCenter14B4',
]
B_IMPORT = 'from app.bi_command_center_14b4 import BIInput14B4, evaluate_bi_command_center_14b4'
B_ANCHOR = '    return await call_next(request)\n\n\n@lru_cache(maxsize=1)'
B_FLAG = 'app.add_middleware(BoundedAPIGuard15A)'
F_ANCHOR = '          {productGrounding13c1Enabled && ('
F_LAST = '          <MerchantEvidenceDesk />'
F_FLAG = 'Loading optional intelligence tools...'


def die(message):
    raise SystemExit('STOP: '+message+'\nNo source or production cloud resource was changed by this operation.')


def norm(path):
    return path.read_text(encoding='utf-8-sig').replace('\r\n','\n')


def exactly(text, token):
    if text.count(token) != 1:
        die('Missing or repeated integration anchor: '+token[:90])


def main():
    ap=argparse.ArgumentParser(description='NeedProof 15A offline guarded installer')
    modes=ap.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check',action='store_true')
    modes.add_argument('--apply',action='store_true')
    options=ap.parse_args()
    missing=[p for p in (BACK,FRONT,*ADD) if not p.is_file()]
    if missing:
        die('Extract ZIP into project root. Missing: '+', '.join(str(p.relative_to(ROOT)) for p in missing))
    back, front = norm(BACK), norm(FRONT)
    flags=(B_FLAG in back, 'from app.api_guard_15a import BoundedAPIGuard15A' in back,
           F_FLAG in front, 'const BusinessCommandCenter14B4 = lazy(' in front,
           '<Suspense fallback=' in front)
    if all(flags):
        for comp in COMPONENTS:
            exactly(front, f'const {comp} = lazy(')
        exactly(back,B_FLAG)
        exactly(front, F_FLAG)
        print('PASS: 15A already integrated; security guard and lazy components are in place.')
        return
    if any(flags):
        die('Partial 15A patch detected; manual review required. Will not overwrite.')
    for path,src in ((BACK,back),(FRONT,front)):
        rel=path.relative_to(ROOT).as_posix()
        if sha256(src.encode('utf-8')).hexdigest()!=EXPECTED[rel]:
            die('SHA256 mismatch from pushed ed71ed1 baseline: '+rel)
    exactly(back,B_IMPORT)
    exactly(back,B_ANCHOR)
    exactly(front,'  useState,\n  type ReactNode,')
    exactly(front,'type ExtractedIntent = {')
    exactly(front,F_ANCHOR)
    exactly(front,F_LAST)
    for comp in COMPONENTS:
        exactly(front, f'import {comp} from "./components/{comp}";')
    new_back=back.replace(B_IMPORT, B_IMPORT+'\nfrom app.api_guard_15a import BoundedAPIGuard15A',1)
    new_back=new_back.replace(B_ANCHOR,'''    return await call_next(request)


# Outermost application middleware: covers requests with missing Content-Length.
app.add_middleware(BoundedAPIGuard15A)


@lru_cache(maxsize=1)''',1)
    new_front=front.replace('  useState,\n  type ReactNode,','  useState,\n  lazy,\n  Suspense,\n  type ReactNode,',1)
    for comp in COMPONENTS:
        new_front=new_front.replace(f'import {comp} from "./components/{comp}";','',1)
    lazy_defs='\n'.join(f'const {comp} = lazy(() => import("./components/{comp}"));' for comp in COMPONENTS)+'\n\n'
    new_front=new_front.replace('type ExtractedIntent = {',lazy_defs+'type ExtractedIntent = {',1)
    new_front=new_front.replace(F_ANCHOR,'''          <Suspense fallback={<p role="status" className="text-sm text-slate-400">Loading optional intelligence tools...</p>}>
'''+F_ANCHOR,1)
    new_front=new_front.replace(F_LAST,F_LAST+'\n          </Suspense>',1)
    if new_back.count(B_FLAG)!=1 or new_front.count(F_FLAG)!=1 or new_front.count('<Suspense fallback=')!=1:
        die('Proposed 15A patch failed internal sanity checks')
    print('PASS: 15A source SHA256 and anchors match committed ed71ed1 source.')
    print('Would modify only backend/app/cloud_decision_api.py and frontend/src/FreeShowcase.tsx.')
    if options.check:
        print('DRY RUN: no source files, cloud APIs, flags or billing settings changed.')
        return
    backup=ROOT/'backup_15a'
    if backup.exists():
        die('Backup folder already exists. Preserve it; do not overwrite.')
    old={BACK:BACK.read_bytes(), FRONT:FRONT.read_bytes()}
    backup.mkdir()
    for path, raw in old.items():
        (backup/(path.name+'.before_15a')).write_bytes(raw)
    try:
        for path, new_text in ((BACK,new_back),(FRONT,new_front)):
            temp=path.with_name(path.name+'.15a.tmp')
            temp.write_text(new_text,encoding='utf-8',newline='\n')
            os.replace(temp,path)
    except Exception as exc:
        for path,raw in old.items():
            path.write_bytes(raw)
        die('Patch failed and original source restored: '+type(exc).__name__)
    print('SUCCESS: Chunk 15A source hardening integrated LOCALLY. No feature flags changed.')
    print('Backups: '+str(backup))
    print(r'NEXT: scripts\verify_chunk15a.cmd')

if __name__=='__main__':
    main()
