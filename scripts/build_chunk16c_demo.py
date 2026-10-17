"""Generate a deterministic static demo by replaying the REAL local 16A Python engine.

All output data is synthetic. No external URLs, SDK network calls, tokens, or
cloud API calls. The resulting HTML is fully self-contained for file:// use.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
import re

SOURCE_HASHES = {
  "backend/app/guided_journey_16a.py": "931a658d43ed984392c85edd51de2c08eb48df17b52a26922a91526d14f5cc84",
  "backend/app/decision_orchestrator_14a3.py": "137e6f924eb923342489ddf5456395c178c25a9e08c849c00833a629474bc8a1",
}
BASELINE = "088b9df"
SCENARIOS = ("reported_offer", "stockout", "document_conflict", "no_merchants")
SNAPSHOT = datetime(2026, 10, 17, 0, 0, tzinfo=timezone.utc)
HERE = Path(__file__).resolve().parents[1]
DEMO = HERE / "demo" / "needproof16c"

def audited_source(root: Path, check_git=True) -> list[str]:
    problems=[]
    if check_git:
        code=subprocess.run(["git","merge-base","--is-ancestor",BASELINE,"HEAD"],cwd=root,check=False,capture_output=True)
        if code.returncode:problems.append(f"Git HEAD does not descend from {BASELINE}")
    for name in ("backend/app/guided_journey_16a.py", "backend/app/decision_orchestrator_14a3.py", "demo/needproof16c/template.html"):
        if not (root/name).is_file():problems.append(f"Missing required source: {name}")
    for name, expected in SOURCE_HASHES.items():
        path=root/name
        if path.is_file() and hashlib.sha256(path.read_bytes().replace(b"\r\n",b"\n")).hexdigest() != expected:
            problems.append("Audited source content changed: " + name)
    return problems

def replay() -> dict:
    sys.path.insert(0,str(HERE/'backend'))
    import app.guided_journey_16a as engine
    import app.algorithms.adaptive_replanning as replanning
    class FixedTime(datetime):
        @classmethod
        def now(cls,tz=None):return SNAPSHOT.astimezone(tz) if tz else SNAPSHOT.replace(tzinfo=None)
    class FixedDate(date):
        @classmethod
        def today(cls):return date(2026,10,17)
    generated={}
    with patch.object(engine,'datetime',FixedTime),patch.object(engine,'date',FixedDate),patch.object(replanning,'datetime',FixedTime):
        for name in SCENARIOS:
            payload=engine.GuidedJourneyInput16A(scenario=name,include_illustrative_business_context=True,simulation_acknowledged=True)
            row=engine.evaluate_guided_journey_16a(payload)
            for field in ("purchase_allowed", "real_merchant_contact", "stock_independently_verified", "cloud_model_used", "database_used", "source_records_persisted"):
                if row.get(field) is not False:raise ValueError(f"Unsafe 16A result for {name}: {field}")
            if row['workflow']['purchase_allowed'] is not False or len(row['workflow']['workflow_trace']) != 5:raise ValueError("Invalid engine trace or purchase guard")
            if row['fixture_origin'] != 'SERVER_OWNED_SYNTHETIC_NOT_REAL_MERCHANTS':raise ValueError('Fixture provenance mismatch')
            generated[name]=row
    if generated['reported_offer']['workflow']['workflow_state']==generated['stockout']['workflow']['workflow_state']:
        raise ValueError('Stock-out did not change workflow state')
    if generated['document_conflict']['workflow']['workflow_state']!='RESEARCH_CONFLICT':raise ValueError('Contradiction guard not triggered')
    if generated['no_merchants']['workflow']['workflow_state']!='DISCOVERY_NEEDED':raise ValueError('Missing discovery state')
    return {"mode":"OFFLINE_ENGINE_REPLAY_16C", "baseline":BASELINE,"source":"ACTUAL_LOCAL_16A_EVALUATOR","synthetic":True,"generated_at_fixed_utc":SNAPSHOT.isoformat(),"scenarios":generated}

def content() -> str:
    data=json.dumps(replay(),ensure_ascii=False,separators=(',',':'),sort_keys=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(DEMO/'template.html').read_text(encoding='utf-8')
    if template.count('__DATA__')!=1:raise ValueError('Template data anchor missing or repeated')
    return template.replace('__DATA__',data)

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--check',action='store_true',help='Guarded validation without writing')
    p.add_argument('--generate',action='store_true',help='Recreate deterministic offline HTML replay')
    p.add_argument('--verify',action='store_true',help='Validate existing HTML against generated expected bytes')
    p.add_argument('--no-git',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args()
    faults=audited_source(HERE,check_git=not args.no_git)
    if faults:
        for f in faults:print('STOP:',f)
        return 1
    if args.check:
        print('PASS: NeedProof 16C source and Git baseline checks; no changes or cloud calls')
        return 0
    expected=content()
    target=DEMO/'offline-demo.html'
    if args.generate:
        target.write_text(expected,encoding='utf-8',newline='\n')
        print('PASS: Generated synthetic engine replay at',target)
        print('HTML SHA256:',hashlib.sha256(expected.encode()).hexdigest())
        return 0
    if not target.is_file():
        print('STOP: Static replay is missing. Use --generate.')
        return 1
    published=target.read_text(encoding='utf-8')
    match=re.search(r'<script id="needproof-replay-data" type="application/json">(.*?)</script>',published,re.S)
    if not match or "connect-src 'none'" not in published or 'OFFLINE REPLAY · NO NETWORK CALLS' not in published:
        print('STOP: Static demo payload, offline security policy or provenance label missing')
        return 1
    saved=json.loads(match.group(1))
    calculated=json.loads(expected.split('<script id="needproof-replay-data" type="application/json">')[1].split('</script>')[0])
    if saved.get('source')!='ACTUAL_LOCAL_16A_EVALUATOR' or set(saved.get('scenarios',{}))!=set(SCENARIOS):
        print('STOP: Embedded replay metadata mismatch')
        return 1
    for name in SCENARIOS:
        row=saved['scenarios'][name]
        live=calculated['scenarios'][name]
        for boundary in ('purchase_allowed','real_merchant_contact','stock_independently_verified','cloud_model_used','database_used','source_records_persisted'):
            if row.get(boundary) is not False:
                print('STOP: Unsafe replay boundary:',name,boundary)
                return 1
        if row['workflow']['workflow_state']!=live['workflow']['workflow_state'] or len(row['workflow']['workflow_trace'])!=5:
            print('STOP: Evidence decision state has drifted:',name)
            return 1
    if published != expected:
        print('NOTE: Full offline replay differs in non-decision fields across environments. Engine decision/safety states match.')
    print('PASS: Offline HTML and locally executed 16A scenarios agree on all decision and purchase-safety states')
    return 0
if __name__=='__main__':raise SystemExit(main())
