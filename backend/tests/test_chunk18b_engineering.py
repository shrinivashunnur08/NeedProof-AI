"""18B guardrail tests on the real local 17C decision engine and 17F policies."""
from __future__ import annotations
import json
import sys
from copy import deepcopy
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_chunk18b_analysis import DATASET, analyze, _assert_safe, _counterfactual
from run_chunk18b_cost_model import compute
from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c


@pytest.fixture(scope='module')
def report():
    return analyze(repetitions=1)


def test_18a_data_is_explicitly_fictional_and_complete():
    source = json.loads(DATASET.read_text(encoding='utf8'))
    assert source['provenance'] == 'AUTHOR_CREATED_FICTIONAL_18A'
    assert len(source['cases']) == 47


def test_study_counts_and_no_swallowed_exceptions(report):
    assert report['passed'], report['failures']
    assert len(report['schema_rejected_cases']) == 10
    assert len(report['case_comparisons']) == 37 * 4
    assert report['live_gemini_calls'] == 0
    assert report['cloud_calls'] == 0
    assert report['actual_participants'] == 0
    assert report['actual_merchants'] == 0


def test_baseline_parity_is_disclosed_not_suppressed(report):
    baseline = report['policies']['STRUCTURED_EVIDENCE_RULES']
    full = report['policies']['NEEDPROOF_17E']
    assert baseline['tested'] == full['tested'] == 37
    assert baseline['correct'] == full['correct'] == 37
    assert baseline['false_provisional'] == full['false_provisional'] == 0


def test_counterfactual_signal_omission_is_measured(report):
    rows = report['input_signal_counterfactuals']
    assert len(rows) == 5
    assert sum(r['experiment'] == 'WITHHOLD_CONFLICT_SIGNAL' for r in rows) == 3
    assert sum(r['experiment'] == 'WITHHOLD_REVISION_SIGNAL' for r in rows) == 2
    assert all(r['changed'] for r in rows)
    assert all(not r['unauthorized_purchase'] for r in rows)


def test_evidence_bindings_and_fail_closed_purchase():
    payload = FreshJourney17C.model_validate(dict(product_query='65W USB-C PD charger', budget_inr=1000,
                       reported_price_inr=899, location_note='Thane', simulated_report='reported_offer',
                       simulation_acknowledged=True, synthetic_documents='conflicting_fixtures'))
    original = evaluate_fresh_journey_17c(payload)
    assert all(_assert_safe(original).values())
    removed = _counterfactual(payload, 'WITHHOLD_CONFLICT_SIGNAL')
    assert removed['purchase_allowed'] is False
    assert original['workflow']['workflow_state'] == 'RESEARCH_CONFLICT'
    assert removed['workflow']['workflow_state'] != 'RESEARCH_CONFLICT'


def test_counterfactual_does_not_mutate_original():
    payload = FreshJourney17C.model_validate(dict(product_query='65W USB-C PD charger', budget_inr=1000,
                reported_price_inr=899, simulated_report='stockout', simulation_acknowledged=True,
                fictional_merchant_update_17e='restock_after_stockout'))
    before = deepcopy(payload.model_dump())
    alt = _counterfactual(payload, 'WITHHOLD_REVISION_SIGNAL')
    assert payload.model_dump() == before
    assert alt['purchase_allowed'] is False
    assert alt['workflow']['workflow_state'] == 'MORE_EVIDENCE_NEEDED'


def test_cost_is_calculation_not_actual_billing():
    assumptions = json.loads((ROOT / 'validation/18b/hypothetical_cost_inputs.json').read_text(encoding='utf8'))
    report = compute(assumptions)
    assert report['actual_billed_usd'] is None
    assert report['observed_roi'] is None
    assert report['example_total_usd'] == '3.70'


@pytest.mark.parametrize('change', [
    ('provenance', 'VERIFIED_LIVE_GCP'),
    ('journeys', -3),
    ('fraction_requiring_merchant_check', '2'),
    ('illustrative_usd_per_model_call', '-1'),
])
def test_cost_refuses_false_or_out_of_bounds_inputs(change):
    assumptions = json.loads((ROOT / 'validation/18b/hypothetical_cost_inputs.json').read_text(encoding='utf8'))
    key, value = change
    if key == 'provenance':
        assumptions[key] = value
    else:
        assumptions['assumptions'][key] = value
    with pytest.raises(ValueError):
        compute(assumptions)


def test_unknown_counterfactual_refused():
    payload = FreshJourney17C.model_validate(dict(product_query='65W USB-C PD charger', budget_inr=1000,
        reported_price_inr=899, simulated_report='reported_offer', simulation_acknowledged=True))
    with pytest.raises(ValueError):
        _counterfactual(payload, 'NO_PROTECTION')
