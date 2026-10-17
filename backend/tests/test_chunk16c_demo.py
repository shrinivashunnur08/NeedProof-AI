"""16C engine-replay test suite; does not contact network, cloud or read secrets."""
import importlib.util
import hashlib
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/build_chunk16c_demo.py'
spec=importlib.util.spec_from_file_location('chunk16c_build',SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

@pytest.fixture(scope='module')
def rows():return module.replay()

def test_four_expected_engine_scenarios(rows):
    assert set(rows['scenarios'])==set(module.SCENARIOS)
    assert rows['source']=='ACTUAL_LOCAL_16A_EVALUATOR'

@pytest.mark.parametrize('name',module.SCENARIOS)
def test_safety_boundary_for_every_scenario(rows,name):
    r=rows['scenarios'][name]
    assert r['purchase_allowed'] is False
    assert r['real_merchant_contact'] is False
    assert r['stock_independently_verified'] is False
    assert r['database_used'] is False
    assert r['cloud_model_used'] is False
    assert r['source_records_persisted'] is False
    assert r['workflow']['purchase_allowed'] is False
    assert len(r['workflow']['workflow_trace'])==5

def test_stockout_replans(rows):
    a=rows['scenarios']['reported_offer']['workflow']
    b=rows['scenarios']['stockout']['workflow']
    assert a['workflow_state'] != b['workflow_state']
    assert b['change_detection']['changed'] is True

def test_document_conflict_blocks(rows):
    assert rows['scenarios']['document_conflict']['workflow']['workflow_state']=='RESEARCH_CONFLICT'

def test_missing_merchants_requests_discovery(rows):
    assert rows['scenarios']['no_merchants']['workflow']['workflow_state']=='DISCOVERY_NEEDED'

def test_template_blocks_network_and_has_accessibility_controls():
    html=(ROOT/'demo/needproof16c/template.html').read_text(encoding='utf-8')
    assert "connect-src 'none'" in html
    assert 'role="group"' in html
    assert 'aria-live="polite"' in html
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "<script src=" not in html

def test_engine_replay_is_deterministic():
    assert module.content() == module.content()
    assert 'connect-src' in (ROOT/'demo/needproof16c/offline-demo.html').read_text(encoding='utf-8')
    import re
    body=(ROOT/'demo/needproof16c/offline-demo.html').read_text(encoding='utf-8')
    raw=re.search(r'<script id="needproof-replay-data" type="application/json">(.*?)</script>',body,re.S)
    assert raw is not None
    published=json.loads(raw.group(1))
    for case in module.SCENARIOS:
        assert published['scenarios'][case]['workflow']['workflow_state'] == module.replay()['scenarios'][case]['workflow']['workflow_state']
