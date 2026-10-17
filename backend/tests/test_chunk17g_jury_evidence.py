"""Offline proof-of-integrity tests for the 17G judge panel."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
PIN=ROOT/'frontend/src/generated/benchmark17fReview.json'
REPORT=ROOT/'qa_reports/17f/benchmark_results.json'
VERIFIER=ROOT/'scripts/verify_chunk17g_evidence.py'


def verifier():
    spec=importlib.util.spec_from_file_location('chunk17g_proof',VERIFIER)
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.verify_summary


def test_published_benchmark_explicitly_is_not_field_validation():
    data=json.loads(PIN.read_text(encoding='utf-8'))
    assert data['dataset_size']==40
    assert data['origin'].startswith('17F Python benchmark')
    assert all(data[k] is False for k in ('independent_ground_truth','live_gemini_tested','real_merchants_contacted','observed_real_customer_outcomes'))
    assert len(data['policies'])==4
    byid={p['id']:p for p in data['policies']}
    assert byid['NEEDPROOF_17E']['correct']==byid['STRUCTURED_EVIDENCE_RULES']['correct']==40
    assert byid['PRICE_ONLY']['unsafe_provisional']==15
    assert byid['STOCK_AND_BUDGET']['unsafe_provisional']==7


def test_jury_component_is_accessible_and_states_limitations():
    text=(ROOT/'frontend/src/components/JuryEvidence17G.tsx').read_text(encoding='utf-8')
    assert 'aria-expanded={open}' in text
    assert 'role="region"' in text
    assert 'builder-authored fictional' in text
    assert 'ties a strong structured-rules baseline' in text
    assert 'freshEnabled ?' in text


def test_existing_fresh_decision_and_replay_are_preserved():
    show=(ROOT/'frontend/src/FreeShowcase.tsx').read_text(encoding='utf-8')
    assert show.count('<JudgeReplay16C2 />')==1
    assert show.count('<FreshDecision17C />')==1
    assert show.count('<JuryEvidence17G freshEnabled=')==1


def test_verifier_matches_reports():
    if not REPORT.is_file():
        pytest.skip('Run scripts/run_chunk17f_benchmark.py first to generate report')
    assert verifier()(PIN,REPORT)


def test_verifier_rejects_tampered_score(tmp_path):
    if not REPORT.is_file():
        pytest.skip('Run scripts/run_chunk17f_benchmark.py first to generate report')
    pin=json.loads(PIN.read_text(encoding='utf-8'))
    pin['policies'][0]['correct']=12
    p=tmp_path/'tampered.json';p.write_text(json.dumps(pin),encoding='utf-8')
    with pytest.raises(ValueError,match='STALE JURY EVIDENCE'):
        verifier()(p,REPORT)


def test_verifier_rejects_fake_live_claim(tmp_path):
    if not REPORT.is_file():
        pytest.skip('Run scripts/run_chunk17f_benchmark.py first to generate report')
    pin=json.loads(PIN.read_text(encoding='utf-8'))
    pin['live_gemini_tested']=True
    p=tmp_path/'false_live.json';p.write_text(json.dumps(pin),encoding='utf-8')
    with pytest.raises(ValueError,match='Unsupported verification claim'):
        verifier()(p,REPORT)
