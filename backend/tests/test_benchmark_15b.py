"""15B local synthetic benchmark contract. No network or API requests."""
import json
from hashlib import sha256
from pathlib import Path

import pytest
from benchmarks_15b.runner import (load_fixtures, fixture_bytes, run_all,
    retrieval_benchmark, evsi_benchmark, basket_benchmark, forecast_benchmark,
    bayesian_benchmark, write_reports)


def test_provenance_and_fixture_limits():
    x=load_fixtures()
    assert x['origin']=='HAND_AUTHORED_SYNTHETIC_ILLUSTRATIVE_NOT_EXTERNAL'
    assert len(x['retrieval'])==6 and len(x['evsi'])==4
    assert len(x['baskets'])==4 and len(x['forecasts'])==4
    assert x['synthetic_bayesian_trials']==120
    assert len(sha256(fixture_bytes()).hexdigest())==64


def test_retrieval_exact_citations_and_metrics():
    r=retrieval_benchmark(load_fixtures())
    assert r['citations_offsets_and_hashes_checked']>12
    assert r['candidate']['cases']==6
    assert 0<=r['candidate']['hit_at_1']<=1
    assert 0<=r['baseline']['mrr']<=1


def test_evsi_comparator_no_negative_model_gain():
    r=evsi_benchmark(load_fixtures())
    assert len(r['cases'])==4
    assert all(x['synthetic_assumed_gain_inr']>=0 for x in r['cases'])
    assert all(x['no_real_merchant_contact'] for x in r['cases'])


def test_basket_excludes_reported_stock_and_no_purchase():
    r=basket_benchmark(load_fixtures())
    assert all(x['unverified_trap_excluded'] for x in r['cases'])
    assert all(x['purchase_allowed'] is False for x in r['cases'])
    assert all(x['modeled_savings_minor'] is None or x['modeled_savings_minor']>=0 for x in r['cases'])


def test_forecast_strict_later_holdout():
    r=forecast_benchmark(load_fixtures())
    assert len(r['cases'])==4
    assert all(x['training_days']==84 and x['untouched_holdout_days']==14 for x in r['cases'])
    assert all(x['chosen_method'] in ('seasonal_naive_7','moving_average_7','weekday_mean_4w','damped_trend') for x in r['cases'])


def test_calibration_simulation_not_real_labels():
    r=bayesian_benchmark(load_fixtures())
    assert r['trials']==120
    assert 0<=r['posterior_brier']<=1
    assert 0<=r['posterior_ece_5_bins']<=1
    assert any('by construction' in limitation for limitation in r['limitations'])


def test_complete_benchmark_deterministic():
    assert run_all()==run_all()


def test_json_markdown_exports_reproducible(tmp_path):
    x=run_all()
    a,b=write_reports(tmp_path,x)
    assert json.loads(a.read_text(encoding='utf-8'))==x
    assert 'Not** independent retail-world proof' in b.read_text(encoding='utf-8')
    old=(a.read_bytes(),b.read_bytes())
    write_reports(tmp_path,x)
    assert old==(a.read_bytes(),b.read_bytes())


def test_fixture_has_no_personal_data_or_live_urls():
    raw=fixture_bytes().decode('utf-8')
    assert 'http://' not in raw and 'https://' not in raw
    assert 'access_token' not in raw and 'private_key' not in raw
    assert 'customer_email' not in raw and 'customer_id' not in raw


def test_benchmark_method_and_purchase_disclosure():
    x=run_all()
    assert x['method']=='OFFLINE_SYNTHETIC_FIXED_CASES_HOLDOUT_15B'
    assert all(not v['purchase_allowed'] for v in x['basket']['cases'])
    assert any('not' in note.lower() for note in x['global_limitations'])
