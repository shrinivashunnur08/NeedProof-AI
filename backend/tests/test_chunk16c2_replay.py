"""Offline 16C.2 replay source, purchase boundary, and UI wiring tests."""
from pathlib import Path
import importlib.util
import json
import re

ROOT=Path(__file__).resolve().parents[2]
COMPONENT=ROOT/'frontend/src/components/JudgeReplay16C2.tsx'
FREE=ROOT/'frontend/src/FreeShowcase.tsx'
JSON=ROOT/'frontend/src/generated/needproof16cReplay.json'
HTML=ROOT/'demo/needproof16c/offline-demo.html'
SCENARIOS=['reported_offer','stockout','document_conflict','no_merchants']

def data():return json.loads(JSON.read_text(encoding='utf-8'))

def test_matches_engine_derived_static_html():
    m=re.search(r'<script id="needproof-replay-data" type="application/json">(.*?)</script>',HTML.read_text(encoding='utf-8'),re.S)
    assert m and data()==json.loads(m.group(1))

def test_provenance_is_explicit():
    d=data();assert d['synthetic'] is True
    assert d['mode']=='OFFLINE_ENGINE_REPLAY_16C'
    assert d['source']=='ACTUAL_LOCAL_16A_EVALUATOR'

def test_scenarios_present():assert set(data()['scenarios'])==set(SCENARIOS)

def test_no_approval_or_live_side_effects():
    for row in data()['scenarios'].values():
        for field in ('purchase_allowed','real_merchant_contact','stock_independently_verified','cloud_model_used','database_used','source_records_persisted'):
            assert row[field] is False
        assert row['workflow']['purchase_allowed'] is False

def test_orchestrator_traces_are_complete():
    for row in data()['scenarios'].values():assert len(row['workflow']['workflow_trace'])==5

def test_evidence_changes_decision():
    d=data()['scenarios'];assert d['reported_offer']['workflow']['workflow_state'] != d['stockout']['workflow']['workflow_state']
    assert d['document_conflict']['workflow']['workflow_state']=='RESEARCH_CONFLICT'
    assert d['no_merchants']['workflow']['workflow_state']=='DISCOVERY_NEEDED'

def test_component_avoids_network():
    ts=COMPONENT.read_text(encoding='utf-8')
    for forbidden in ('fetch(', 'XMLHttpRequest(', 'sendBeacon(', 'generateContent(', 'getFirestore(', 'https://'):
        assert forbidden not in ts

def test_ui_has_replay_boundary():
    ts=COMPONENT.read_text(encoding='utf-8');assert 'OFFLINE REPLAY' in ts
    assert 'NO PURCHASE APPROVAL' in ts and 'verifiedFixture' in ts

def test_replay_integrated_in_showcase():
    ts=FREE.read_text(encoding='utf-8')
    assert ts.count('<JudgeReplay16C2 />')==1
    assert ts.count('const JudgeReplay16C2 = lazy(')==1
    assert 'href="#judge-replay-16c2"' in ts

def test_preflight_logic():
    f=ROOT/'scripts/apply_chunk16c2.py'
    spec=importlib.util.spec_from_file_location('preflight16c2',f)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.validate_replay()
