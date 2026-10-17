"""18A verification: dataset integrity, schema abuse and metamorphic safety."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_chunk18a_validation import DATASET, run_suite
from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c


def _baseline(**diff):
    data = dict(product_query='65W USB-C PD charger', location_note='Thane',
                budget_inr=1000, reported_price_inr=899,
                simulated_report='reported_offer', simulation_acknowledged=True)
    data.update(diff)
    return FreshJourney17C.model_validate(data)


def _run(**diff):
    return evaluate_fresh_journey_17c(_baseline(**diff))


def test_dataset_declares_fictional_provenance():
    data = json.loads(DATASET.read_text(encoding='utf8'))
    assert data['provenance'] == 'AUTHOR_CREATED_FICTIONAL_18A'
    assert len(data['cases']) >= 25
    assert len({c['id'] for c in data['cases']}) == len(data['cases'])


def test_case_suite_has_no_hidden_failed_rows():
    report = run_suite()
    assert report['total_cases'] >= 25
    assert report['failed'] == 0, [r for r in report['results'] if not r['pass']]
    assert report['real_participants'] == 0
    assert report['real_merchants'] == 0


def test_changed_report_replans_but_never_buys():
    a = _run(simulated_report='reported_offer')
    b = _run(simulated_report='stockout')
    assert a['workflow']['workflow_state'] == 'PROVISIONAL_VERIFICATION_NEEDED'
    assert b['workflow']['workflow_state'] == 'MORE_EVIDENCE_NEEDED'
    assert a['purchase_allowed'] is False and b['purchase_allowed'] is False
    assert a['workflow']['snapshot_sha256'] != b['workflow']['snapshot_sha256']


def test_budget_pressure_blocks_provisional_selection():
    affordable = _run(reported_price_inr=850, budget_inr=1000)
    unaffordable = _run(reported_price_inr=1150, budget_inr=1000)
    assert affordable['workflow']['merchant_replanning']['selected'] is not None
    assert unaffordable['workflow']['merchant_replanning']['selected'] is None
    assert unaffordable['purchase_allowed'] is False


def test_discovery_is_never_claimed_from_location_note():
    a = _run(location_note='Thane')
    b = _run(location_note='Pune')
    assert a['workflow']['workflow_state'] == b['workflow']['workflow_state']
    assert a['location_used_for_discovery'] is False
    assert b['location_used_for_discovery'] is False


def test_conflicting_documents_cannot_approve_purchase():
    r = _run(synthetic_documents='conflicting_fixtures')
    assert r['workflow']['workflow_state'] == 'RESEARCH_CONFLICT'
    assert r['purchase_allowed'] is False
    assert r['evidence_passport']['purchase_allowed'] is False
    assert r['verification_queue_17e']['purchase_allowed'] is False


@pytest.mark.parametrize('diff', [
    {'simulation_acknowledged': False},
    {'budget_inr': -1},
    {'budget_inr': True},
    {'reported_price_inr': -50},
    {'reported_price_inr': '899'},
    {'simulated_report': 'verified_merchant'},
    {'synthetic_documents': 'actual_seller_document'},
    {'fictional_merchant_update_17e': 'restock_after_stockout'},
    {'product_query': 'USB cable', 'synthetic_documents': 'conflicting_fixtures'},
    {'verified_by_merchant': True},
])
def test_dangerous_inputs_rejected_at_model_boundary(diff):
    with pytest.raises(ValidationError):
        _baseline(**diff)
