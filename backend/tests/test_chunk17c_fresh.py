"""Chunk 17C: real Python recomputation, no network, no paid models."""
import json

import pytest
from pydantic import ValidationError

from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c


def data(**changes):
    return {
        "product_query": "65W USB-C PD charger",
        "budget_inr": 1000, "reported_price_inr": 720,
        "location_note": "Thane",
        "simulated_report": "reported_offer",
        "simulation_acknowledged": True, **changes,
    }


def run(**changes):
    return evaluate_fresh_journey_17c(FreshJourney17C.model_validate(data(**changes)))


@pytest.mark.parametrize("kind,state", [
    ("reported_offer", "PROVISIONAL_VERIFICATION_NEEDED"),
    ("stockout", "MORE_EVIDENCE_NEEDED"),
    ("no_merchants", "DISCOVERY_NEEDED"),
])
def test_new_python_flow_each_input(kind,state):
    result=run(simulated_report=kind)
    assert result["mode"]=="FRESH_STRUCTURED_WHAT_IF_17C"
    assert result["workflow"]["workflow_state"]==state
    assert len(result["workflow"]["workflow_trace"])==5
    assert result["workflow"]["workflow_trace"][0]["status"]=="EVALUATED"
    assert result["workflow"]["workflow_trace"][1]["status"]=="NOT_PROVIDED"
    assert result["workflow"]["workflow_trace"][2]["status"]=="NOT_PROVIDED"
    assert result["workflow"]["workflow_trace"][3]["status"]=="NOT_PROVIDED"
    assert result["workflow"]["workflow_trace"][4]["state"]=="NO_PURCHASE_AUTHORIZATION"
    for key in ("purchase_allowed","gemini_called","merchant_contacted","database_written","stock_independently_verified","location_used_for_discovery"):
        assert result[key] is False,key
    assert result["workflow"]["purchase_allowed"] is False


def test_user_product_drives_new_snapshot():
    a=run(product_query="USB C charger")
    b=run(product_query="Electric kettle")
    assert a["input_product_query"] != b["input_product_query"]
    assert a["workflow"]["snapshot_sha256"] != b["workflow"]["snapshot_sha256"]


def test_budget_changes_candidate():
    cheap=run(budget_inr=1000)
    costly=run(budget_inr=300)
    assert cheap["workflow"]["merchant_replanning"]["selected"] is not None
    assert costly["workflow"]["merchant_replanning"]["selected"] is None
    assert costly["workflow"]["workflow_state"]=="MORE_EVIDENCE_NEEDED"


def test_stockout_is_illustrative_change_only():
    a=run()
    b=run(simulated_report="stockout")
    assert a["workflow"]["merchant_replanning"]["selected"] is not None
    assert b["workflow"]["merchant_replanning"]["selected"] is None
    assert b["workflow"]["change_detection"]["changed"] is True
    assert "historical merchant" in " ".join(b["limitations"]).lower()


def test_location_annotation_does_not_claim_store_search():
    a=run(location_note="Thane")
    b=run(location_note="Dombivli")
    assert a["workflow"]["workflow_state"] == b["workflow"]["workflow_state"]
    assert a["location_note_unverified"] != b["location_note_unverified"]
    assert b["location_used_for_discovery"] is False


@pytest.mark.parametrize("changes",[
    {"simulation_acknowledged": False},
    {"simulated_report": "actual_stock"},
    {"budget_inr": "1000"},
    {"budget_inr": -50},
    {"reported_price_inr": 0},
    {"product_query": "x"},
    {"product_query": "   "},
    {"product_query": "X"*161},
    {"location_note": "X"*81},
    {"merchant_id": "real-store-id"},
])
def test_invalid_data_fail_closed(changes):
    with pytest.raises(ValidationError): FreshJourney17C.model_validate(data(**changes))


def test_no_real_world_claims():
    output=json.dumps(run()).lower()
    assert "fictional" in output
    assert '"gemini_called": true' not in output
    assert '"purchase_allowed": true' not in output
    assert "fixture_17c_a" in output
