"""17F synthetic benchmark: integrity, reproducibility, comparative honesty."""
from __future__ import annotations
import json
import socket
from pathlib import Path
import pytest
from app.benchmark_17f import load_cases, run_suite, run_one, simple_baseline, POLICIES, P, C, M, D
from app.fresh_journey_17c import FreshJourney17C

FIXTURE=Path(__file__).resolve().parents[1]/'fixtures'/'benchmark17f_cases.json'


def test_fixed_dataset_has_40_cases_eight_families():
    doc=load_cases(FIXTURE)
    assert len(doc['cases'])==40
    assert len({c['family'] for c in doc['cases']})==8
    assert all(c['fixture_origin']=='CURATED_FICTIONAL_SCENARIO' for c in doc['cases'])


def test_all_cases_valid_and_purchases_denied():
    doc=load_cases(FIXTURE)
    for c in doc['cases']:
        assert isinstance(FreshJourney17C.model_validate(c['input']),FreshJourney17C)
        assert c['expected']['purchase_allowed'] is False
        assert c['expected']['provisional_candidate_allowed']==(c['expected']['workflow_state']==P)


def test_suite_does_not_access_network(monkeypatch):
    def deny(*a,**k):raise AssertionError('Network access forbidden in benchmark')
    monkeypatch.setattr(socket.socket,'connect',deny)
    monkeypatch.setattr(socket.socket,'connect_ex',deny)
    monkeypatch.setattr(socket,'create_connection',deny)
    run_suite(load_cases(FIXTURE), repetitions=1)


def test_all_40_cases_execute_and_no_purchases():
    r=run_suite(load_cases(FIXTURE),repetitions=1)
    assert len(r['per_case'])==4
    assert all(m['case_count']==40 and m['unauthorized_purchase']==0 for m in r['policies'].values())
    assert r['policies']['NEEDPROOF_17E']['correct_state']==40
    assert r['policies']['NEEDPROOF_17E']['correct_first_check']==40
    assert r['policies']['NEEDPROOF_17E']['false_provisional_offer']==0


def test_strong_rules_baseline_is_not_hidden():
    r=run_suite(load_cases(FIXTURE), repetitions=1)
    # If a rules baseline ties, the report must preserve the tie.
    assert r['policies']['STRUCTURED_EVIDENCE_RULES']['correct_state']==40
    assert r['policies']['STRUCTURED_EVIDENCE_RULES']['correct_first_check']==40
    assert r['live_gemini_or_llm_baseline_executed'] is False
    assert r['ground_truth_independently_validated'] is False


def test_digest_is_reproducible_without_runtime_numbers():
    doc=load_cases(FIXTURE)
    a=run_suite(doc,repetitions=1)
    b=run_suite(doc,repetitions=2)
    assert a['dataset_sha256']==b['dataset_sha256']
    assert a['semantic_results_sha256']==b['semantic_results_sha256']


def test_stockout_and_conflict_are_distinct():
    cases=load_cases(FIXTURE)['cases']
    s=next(c for c in cases if c['family']=='stockout')
    c=next(c for c in cases if c['family']=='contradiction')
    assert run_one(s,'NEEDPROOF_17E')['workflow_state']==M
    assert run_one(c,'NEEDPROOF_17E')['workflow_state']==C
    assert run_one(c,'PRICE_ONLY')['false_provisional_offer'] is True
    assert run_one(s,'PRICE_ONLY')['false_provisional_offer'] is True


def test_no_merchants_never_create_offer():
    c=next(c for c in load_cases(FIXTURE)['cases'] if c['family']=='no_merchants')
    for p in POLICIES:
        o=run_one(c,p)
        assert o['workflow_state']==D
        assert o['provisional_candidate_selected'] is False


def test_mutated_labels_dont_silently_pass(tmp_path):
    d=load_cases(FIXTURE)
    d['cases'][0]['expected']['workflow_state']='FICTIONAL_AUTOBUY'
    file=tmp_path/'bad.json'; file.write_text(json.dumps(d),encoding='utf-8')
    with pytest.raises(ValueError):load_cases(file)


def test_duplicate_ids_rejected(tmp_path):
    d=load_cases(FIXTURE);d['cases'][1]['case_id']=d['cases'][0]['case_id']
    file=tmp_path/'bad.json';file.write_text(json.dumps(d),encoding='utf-8')
    with pytest.raises(ValueError):load_cases(file)


def test_no_exaggerated_impact_metrics_in_output():
    r=run_suite(load_cases(FIXTURE),repetitions=1)
    assert 'real_customer_time_saved' not in r
    assert 'business_savings_inr' not in r
    assert not r['ground_truth_independently_validated']
    assert any('NOT evidence' in str(s) for s in r['limitations'])


def test_invalid_repetition_count_rejected():
    d=load_cases(FIXTURE)
    for n in [0,21,-1]:
        with pytest.raises(ValueError):run_suite(d,repetitions=n)
