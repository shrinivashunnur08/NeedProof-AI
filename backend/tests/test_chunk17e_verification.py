"""17E safety, deterministic prioritization, assumption-labelled EVSI, no real contact."""
import copy
import json

import pytest
from pydantic import ValidationError

from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c
from app.verification_queue_17e import build_verification_queue_17e


BASE = dict(product_query="65W USB-C PD charger", location_note="Thane", budget_inr=1000,
            reported_price_inr=720, simulated_report="reported_offer", simulation_acknowledged=True)


def run(**changes):
    return evaluate_fresh_journey_17c(FreshJourney17C.model_validate({**BASE, **changes}))


def test_offer_queue_prioritizes_spec_and_runs_existing_evsi():
    out = run()
    q = out["verification_queue_17e"]
    assert q["recommended_action_id"] == "CHECK_COMPATIBILITY"
    assert q["hypothetical_evsi"]["recommended_action_id"] == "VERIFY_fixture_17c_a"
    assert q["hypothetical_evsi"]["status"] == "EXECUTED_HYPOTHETICAL_UNCALIBRATED"
    assert q["hypothetical_evsi"]["assumptions_calibrated"] is False
    assert q["hypothetical_evsi"]["actions"][0]["net_evsi_inr"]
    assert out["workflow"]["workflow_trace"][2]["status"] == "NOT_PROVIDED"  # sidecar, not 14A3 stage


def test_conflict_blocks_evsi_and_forces_reconciliation_first():
    q = run(synthetic_documents="conflicting_fixtures")["verification_queue_17e"]
    assert q["recommended_action_id"] == "RECONCILE_CONFLICT"
    assert q["hypothetical_evsi"]["status"] == "BLOCKED_DOCUMENT_CONFLICT"
    assert q["hypothetical_evsi"]["recommended_action_id"] is None


@pytest.mark.parametrize("scenario,first", [
    ("stockout", "REFRESH_ALTERNATIVES"),
    ("no_merchants", "DISCOVER_MERCHANTS"),
    ("reported_offer", "CHECK_COMPATIBILITY"),
])
def test_decision_states_drive_first_proof(scenario, first):
    q = run(simulated_report=scenario)["verification_queue_17e"]
    assert q["recommended_action_id"] == first
    assert q["actions"][0]["action_id"] == first
    assert [a["rank"] for a in q["actions"]] == list(range(1, len(q["actions"])+1))
    assert all(a["status"] == "NOT_EXECUTED" for a in q["actions"])


def test_stockout_evsi_marks_reported_stock_insufficient():
    q = run(simulated_report="stockout")["verification_queue_17e"]
    assert q["hypothetical_evsi"]["recommended_action_id"] is None
    assert q["hypothetical_evsi"]["actions"][0]["skip_reason"] == "REPORTED_STOCK_INSUFFICIENT"


def test_without_merchants_no_model_evsi_ranking():
    q = run(simulated_report="no_merchants")["verification_queue_17e"]
    assert q["hypothetical_evsi"]["status"] == "NOT_APPLICABLE_NO_MERCHANT"
    assert q["hypothetical_evsi"]["actions"] == []


def test_stockout_transition_recomputes_13b_and_synchronizes_passport():
    out = run(fictional_merchant_update_17e="stockout_after_report")
    q = out["verification_queue_17e"]
    assert out["workflow"]["workflow_state"] == "MORE_EVIDENCE_NEEDED"
    assert out["workflow"]["change_detection"]["changed"] is True
    assert out["simulated_report"] == "stockout"
    assert out["evidence_passport"]["claims"][0]["display_value"].startswith("0 units")
    assert q["hypothetical_merchant_update"]["current_fictional_report"] == "stockout"
    assert q["hypothetical_merchant_update"]["authenticated_merchant"] is False
    assert q["hypothetical_merchant_update"]["persistent_history"] is False
    assert q["snapshot_sha256"] == out["workflow"]["snapshot_sha256"] == out["evidence_passport"]["snapshot_sha256"]


def test_restock_transition_recomputes_but_doesnt_verify_stock():
    out = run(simulated_report="stockout", fictional_merchant_update_17e="restock_after_stockout")
    assert out["workflow"]["workflow_state"] == "PROVISIONAL_VERIFICATION_NEEDED"
    assert out["workflow"]["change_detection"]["changed"] is True
    assert out["evidence_passport"]["claims"][0]["display_value"].startswith("1 unit")
    assert out["verification_queue_17e"]["stock_verified"] is False


@pytest.mark.parametrize("case", [
    {"simulated_report": "no_merchants", "fictional_merchant_update_17e": "stockout_after_report"},
    {"simulated_report": "reported_offer", "fictional_merchant_update_17e": "restock_after_stockout"},
    {"simulated_report": "stockout", "fictional_merchant_update_17e": "stockout_after_report"},
    {"fictional_merchant_update_17e": "real_confirmed_stock"},
    {"fictional_merchant_update_17e": 7},
    {"simulation_acknowledged": False},
    {"independently_verified": True},
])
def test_unauthorized_or_inconsistent_revision_rejected(case):
    with pytest.raises(ValidationError):
        FreshJourney17C.model_validate({**BASE, **case})


@pytest.mark.parametrize("opts", [
    {}, {"simulated_report": "stockout"}, {"simulated_report": "no_merchants"},
    {"synthetic_documents": "matching_fixture"}, {"synthetic_documents": "conflicting_fixtures"},
    {"fictional_merchant_update_17e": "stockout_after_report"},
    {"simulated_report": "stockout", "fictional_merchant_update_17e": "restock_after_stockout"},
    {"reported_price_inr": 2000},
])
def test_all_scenarios_fail_closed_and_no_business_results_fabricated(opts):
    result = run(**opts)
    q = result["verification_queue_17e"]
    assert result["purchase_allowed"] is False
    assert q["purchase_allowed"] is False
    assert q["merchant_verified"] is q["stock_verified"] is False
    assert q["external_requests_performed"] is q["database_written"] is False
    assert q["real_merchant_evidence_submitted"] is False
    assert q["business_kpis"]["actual_contact_count"] == 0
    assert q["business_kpis"]["real_customer_time_saved_measured"] is False
    assert q["business_kpis"]["real_conversion_improvement_measured"] is False
    assert all(a["requires_independent_evidence"] for a in q["actions"])
    assert q["snapshot_sha256"] == result["workflow"]["snapshot_sha256"]


def test_queue_rejects_tampered_passport_fingerprint():
    r = run()
    p = copy.deepcopy(r["evidence_passport"])
    p["snapshot_sha256"] = "f"*64
    with pytest.raises(RuntimeError, match="different evidence snapshots"):
        build_verification_queue_17e(snapshot={}, passport=p, workflow=r["workflow"])


def test_queue_doesnt_promote_verified_labels():
    r = run()
    p = copy.deepcopy(r["evidence_passport"])
    p["real_world_evidence_present"] = True
    with pytest.raises(RuntimeError, match="refuses verified"):
        build_verification_queue_17e(snapshot={}, passport=p, workflow=r["workflow"])


def test_json_roundtrip_has_no_secret_or_external_reference():
    result = run(synthetic_documents="conflicting_fixtures")
    dumped = json.dumps(result["verification_queue_17e"])
    assert "https://" not in dumped and "Bearer " not in dumped
    assert "FICTIONAL_SCENARIO_AND_UNCALIBRATED_ASSUMPTIONS" in dumped
