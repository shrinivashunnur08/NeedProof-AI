"""Offline contract tests for Chunk 17A auditor; no app or cloud imports."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
AUDITOR = ROOT / 'scripts/audit_chunk17a.py'
spec = importlib.util.spec_from_file_location('needproof_chunk17a_auditor', AUDITOR)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    for name in module.REQUIRED_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('// checked in source fixture\n', encoding='utf-8')
    for _label, name, marker, _mode in module.SOURCE_LINKS:
        path = tmp_path / name
        path.write_text(path.read_text(encoding='utf-8') + '\n' + marker + '\n', encoding='utf-8')
    (tmp_path / 'backend/app/cloud_decision_api.py').write_text(
        '''@app.get("/health")\n@app.post("/api/v1/decision/replan")\n@app.post("/api/v1/discovery/stores")\n'''
        + (tmp_path / 'backend/app/cloud_decision_api.py').read_text(encoding='utf-8')
        + '''\nverify_id_token\napp_check.verify_token\nallow_origins=ALLOWED_ORIGINS\n''',
        encoding='utf-8',
    )
    (tmp_path / 'firestore.rules').write_text('allow read, write: if false\n', encoding='utf-8')
    (tmp_path / 'firebase.json').write_text(json.dumps({
        'hosting': {'public': 'frontend/dist', 'rewrites': [{'source': '**', 'destination': '/index.html'}]},
        'firestore': {'rules': 'firestore.rules'},
    }), encoding='utf-8')
    (tmp_path / '.firebaserc').write_text(json.dumps({'projects': {'default': 'needproof-ai-showcase'}}), encoding='utf-8')
    cases = {
        k: {'purchase_allowed': False, 'real_merchant_contact': False,
            'cloud_model_used': False,
            'workflow': {'workflow_state': v, 'purchase_allowed': False,
                         'workflow_trace': [{'stage': f'phase{i}'} for i in range(5)]}}
        for k, v in module.EXPECTED_STATES.items()
    }
    (tmp_path / 'frontend/src/generated/needproof16cReplay.json').write_text(
        json.dumps({'synthetic': True, 'scenarios': cases}), encoding='utf-8'
    )
    return tmp_path


def test_audit_can_pass_safe_fixture(sample_repo):
    d = module.audit(sample_repo)
    assert d['result'] == 'PASS_OFFLINE_SOURCE_GATE', d['errors']
    assert d['replay']['safety_pass']
    assert len(d['cloud_api_routes']) == 3


def test_no_real_stock_or_purchase_claim(sample_repo):
    d = module.audit(sample_repo)
    assert all(x['purchase_denied'] for x in d['replay']['cases'].values())
    assert all(x['no_real_merchant_contact'] for x in d['replay']['cases'].values())
    assert all(x['no_live_model_claim'] for x in d['replay']['cases'].values())


def test_tampered_replay_rejected(sample_repo):
    path = sample_repo / 'frontend/src/generated/needproof16cReplay.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['scenarios']['stockout']['purchase_allowed'] = True
    path.write_text(json.dumps(data), encoding='utf-8')
    d = module.audit(sample_repo)
    assert d['result'] == 'NEEDS_INSPECTION'
    assert not d['replay']['safety_pass']


def test_missing_app_check_wiring_rejected(sample_repo):
    path = sample_repo / 'backend/app/cloud_decision_api.py'
    path.write_text(path.read_text(encoding='utf-8').replace('app_check.verify_token', ''), encoding='utf-8')
    d = module.audit(sample_repo)
    assert d['result'] == 'NEEDS_INSPECTION'
    assert not d['security_source_checks']['app_check_verifier_source_present']


def test_no_broad_firestore_rules(sample_repo):
    path = sample_repo / 'firestore.rules'
    path.write_text('allow read, write: if true;', encoding='utf-8')
    assert module.audit(sample_repo)['result'] == 'NEEDS_INSPECTION'


def test_no_env_value_leak_even_when_present(sample_repo):
    secret = 'NEVER_PRINT_OR_COPY_THIS_SECRET_123456'
    path = sample_repo / 'frontend/.env.production.local'
    path.write_text(f'VITE_FAKE_PASSWORD={secret}\n', encoding='utf-8')
    d = module.audit(sample_repo)
    string = json.dumps(d) + module.report_md(d)
    assert secret not in string
    assert d['local_env_FILE_PRESENCE_ONLY']['frontend_env_production_local_present'] is True


def test_audit_is_explicitly_not_live_evidence(sample_repo):
    d = module.audit(sample_repo)
    assert d['audit_type'] == 'STATIC_SOURCE_ONLY_NO_NETWORK'
    assert 'Gemini' in ' '.join(d['NOT_VERIFIED'])
    assert 'Cloud Run' in ' '.join(d['NOT_VERIFIED'])


def test_report_contains_actionable_reconciliation(sample_repo):
    out = module.report_md(module.audit(sample_repo))
    assert '17B' in out and '17C' in out
    assert 'NOT a live' in out
    assert 'Firebase' in out


def test_script_and_trace_are_additive_only():
    script = AUDITOR.read_text(encoding='utf-8')
    trace = (ROOT / 'scripts/trace_chunk17a_backend.py').read_text(encoding='utf-8')
    assert 'frontend/.env.production.local' in script  # only existence check
    assert "(root / 'frontend/.env.production.local').exists()" in script
    assert 'socket.socket.connect = _deny_outbound' in trace
    assert 'LOCAL_TEST_IDENTITY_NOT_REAL_AUTH' in trace
