"""Guarded, local-only 16C.2 judge replay integration. No API or cloud changes."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'frontend/src/FreeShowcase.tsx'
REPLAY=ROOT/'frontend/src/generated/needproof16cReplay.json'
SOURCE_HTML=ROOT/'demo/needproof16c/offline-demo.html'
COMPONENT=ROOT/'frontend/src/components/JudgeReplay16C2.tsx'
BASELINE='88bdaac'
BASE_SHA='b5835247d9c344eac27da39602e9e521069bb95eb62d75f1c262da8467baeeda'
MARKER='const JudgeReplay16C2 = lazy(() => import("./components/JudgeReplay16C2"));'
ANCHORS=[
  ('const GuidedJourney16A = lazy(() => import("./components/GuidedJourney16A"));',
   'const GuidedJourney16A = lazy(() => import("./components/GuidedJourney16A"));\n'+MARKER),
  ('<nav aria-label="Showcase workspace" className="space-y-2">',
   '<nav aria-label="Showcase workspace" className="space-y-2">\n          <a href="#judge-replay-16c2" className="block rounded-lg border border-emerald-500/50 bg-emerald-900/20 px-3 py-3 text-xs font-bold text-emerald-200">Start guided demo</a>'),
  ('className="flex gap-2 lg:hidden"', 'className="flex gap-2 overflow-x-auto pb-2 lg:hidden"'),
  ('aria-label="Mobile showcase navigation"\n            className="flex gap-2 overflow-x-auto pb-2 lg:hidden"\n          >',
   'aria-label="Mobile showcase navigation"\n            className="flex gap-2 overflow-x-auto pb-2 lg:hidden"\n          >\n            <a href="#judge-replay-16c2" className="shrink-0 rounded-lg border border-emerald-600 bg-emerald-900/30 px-3 py-2 text-xs font-bold text-emerald-200">Guided demo</a>'),
  ('          <DecisionSpotlight\n',
   '          <Suspense fallback={<p role="status" className="rounded-lg p-4 text-sm text-slate-400">Loading the fictional guided demo...</p>}>\n            <JudgeReplay16C2 />\n          </Suspense>\n\n          <DecisionSpotlight\n'),
]
SAFETY_KEYS=('purchase_allowed','real_merchant_contact','stock_independently_verified','cloud_model_used','database_used','source_records_persisted')
SCENARIOS=('reported_offer','stockout','document_conflict','no_merchants')

def normalized(data:bytes)->bytes:
    return data.replace(b'\r\n',b'\n')

def sha(path:Path)->str:
    return hashlib.sha256(normalized(path.read_bytes())).hexdigest()

def data_from_html():
    if not SOURCE_HTML.is_file(): raise ValueError('Missing committed 16C.1 offline HTML replay')
    txt=SOURCE_HTML.read_text(encoding='utf-8')
    m=re.search(r'<script id="needproof-replay-data" type="application/json">(.*?)</script>',txt,re.S)
    if not m:raise ValueError('Missing replay data in HTML')
    return json.loads(m.group(1))

def validate_replay():
    if not COMPONENT.is_file() or not REPLAY.is_file(): raise ValueError('Missing React component or checked-in replay JSON: extract ZIP first')
    saved=json.loads(REPLAY.read_text(encoding='utf-8'))
    expected=data_from_html()
    if saved != expected: raise ValueError('React replay data does not match committed 16C.1 offline HTML')
    if saved.get('mode')!='OFFLINE_ENGINE_REPLAY_16C' or saved.get('source')!='ACTUAL_LOCAL_16A_EVALUATOR' or saved.get('synthetic') is not True:raise ValueError('Source provenance incorrect')
    if set(saved['scenarios'])!=set(SCENARIOS):raise ValueError('Missing replay scenarios')
    states={}
    for key in SCENARIOS:
        row=saved['scenarios'][key]
        if row.get('fixture_origin') != 'SERVER_OWNED_SYNTHETIC_NOT_REAL_MERCHANTS':raise ValueError('Not an engine fixture')
        if any(row.get(f) is not False for f in SAFETY_KEYS):raise ValueError('Purchase / live-call boundary failed: '+key)
        if row['workflow'].get('purchase_allowed') is not False or len(row['workflow'].get('workflow_trace',[]))!=5:raise ValueError('Unsafe orchestration trace')
        states[key]=row['workflow']['workflow_state']
    if states['reported_offer']==states['stockout'] or states['document_conflict']!='RESEARCH_CONFLICT' or states['no_merchants']!='DISCOVERY_NEEDED':raise ValueError('Scenario state integrity failed')
    ts=COMPONENT.read_text(encoding='utf-8')
    for forbidden in ('fetch(', 'XMLHttpRequest(', 'sendBeacon(', 'generateContent(', 'getFirestore(', 'https://'):
        if forbidden in ts:raise ValueError('Potential network call in offline React walkthrough: '+forbidden)
    for check in ('OFFLINE REPLAY', 'NO PURCHASE APPROVAL', 'verifiedFixture'):
        if check not in ts:raise ValueError('Missing safety or provenance UI: '+check)

def create_patch(s:str):
    for before,after in ANCHORS:
        if s.count(before)!=1:raise ValueError('Incompatible source anchor or changed source: '+repr(before[:70]))
        s=s.replace(before,after,1)
    return s

def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check',action='store_true')
    group.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if (ROOT/'.git').exists():
        p=subprocess.run(['git','merge-base','--is-ancestor',BASELINE,'HEAD'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if p.returncode:raise SystemExit('STOP: Git HEAD does not descend from 88bdaac')
    try:
        validate_replay()
        if not TARGET.is_file():raise ValueError('Missing existing React showcase')
        current=TARGET.read_text(encoding='utf-8')
        if MARKER in current:
            if current.count(MARKER)!=1 or current.count('<JudgeReplay16C2 />')!=1:raise ValueError('Partial/duplicated previous patch')
            print('PASS: 16C.2 already integrated and replay safety checks pass. No cloud changes.')
            return
        if sha(TARGET)!=BASE_SHA:raise ValueError('FreeShowcase.tsx differs from audited 88bdaac baseline; stop and request a compatible patch')
        patched=create_patch(current)
        if args.check:
            print('PASS: 16C.2 audited FreeShowcase anchors, SHA256 and 16C.1 engine replay match')
            print('Would modify: frontend/src/FreeShowcase.tsx only')
            print('DRY RUN: no source, flags, network, API, IAM, Firebase or billing changes')
            return
        backup=ROOT/'backup_16c2'
        backup.mkdir(exist_ok=True)
        shutil.copy2(TARGET, backup/'FreeShowcase.tsx')
        TARGET.write_text(patched,encoding='utf-8',newline='\n')
        print('SUCCESS: Local React judge replay integrated; API / cloud configuration unchanged.')
        print('Backup:',backup)
        print('NEXT: scripts\\verify_chunk16c2.cmd')
    except (ValueError,OSError) as exc:
        raise SystemExit('STOP: '+str(exc)) from exc

if __name__=='__main__': main()
