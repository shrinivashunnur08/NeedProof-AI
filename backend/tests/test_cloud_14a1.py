"""14A.1 test contracts: evidence semantics, authenticated routes, and EVSI guardrails."""
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.evidence_planner_14a1 import EvidencePlanInput14A1, evaluate_evidence_plan
from app.cloud_decision_api import app, require_firebase_client


def case(offer_price=70000, stock=2, include_report=True, status="UNKNOWN"):
    candidate = {"place_id": "place_001", "name": "Example Store"}
    if include_report:
        candidate["evidence"] = {
            "product_query": "65W PD charger", "status": "REPORTED_UNVERIFIED",
            "submission": {"product_name": "65W PD charger", "stock_quantity": stock,
                "price_minor": offer_price, "currency": "INR", "delivery_available": True,
                "submitted_at": datetime.now(timezone.utc).isoformat()},
            "assessment": {"status": "REPORTED_UNVERIFIED", "freshness": "RECENT_REPORT", "eligible_for_commitment": False},
        }
    return {"snapshot": {"customer": {"product_query":"65W PD charger", "budget_minor":100000,
        "required_quantity":1, "delivery_required":False}, "merchants":[candidate]},
        "proposals":[{"place_id":"place_001", "assumed_prior_feasible":"0.65",
            "assumed_response_probability":"0.8", "verification_cost_minor":500,
            "verification_delay_minutes":2, "compatibility_status":status,
            "indicative_price_minor":73000}], "assumption_acknowledged": True}


def evaluate(payload):
    return evaluate_evidence_plan(EvidencePlanInput14A1.model_validate(payload))


def test_ranked_assumptions_do_not_verify_merchant():
    result = evaluate(case())
    assert result["recommended_action_id"] == "VERIFY_place_001"
    assert result["purchase_allowed"] is False
    assert result["current_verification_baseline"] is None
    assert result["snapshot_replanning"]["purchase_allowed"] is False
    assert result["evidence_traces"][0]["price_provenance"] == "MERCHANT_REPORTED_UNVERIFIED"
    assert result["calibration_status"].startswith("UNCALIBRATED")


def test_stock_out_blocks_action_and_does_not_promote_estimate():
    result = evaluate(case(stock=0))
    assert result["recommended_action_id"] is None
    assert result["actions"][0]["skip_reason"] == "REPORTED_STOCK_INSUFFICIENT"


def test_document_mismatch_blocks():
    result = evaluate(case(status="REPORTED_SPEC_MISMATCH"))
    assert result["actions"][0]["skip_reason"] == "REPORTED_SPEC_MISMATCH"


def test_missing_report_allows_labeled_estimate():
    result = evaluate(case(include_report=False))
    assert result["recommended_action_id"] == "VERIFY_place_001"
    assert result["evidence_traces"][0]["price_provenance"] == "CLIENT_ESTIMATE_UNVERIFIED"


def test_missing_price_fails_closed():
    payload = case(include_report=False)
    payload["proposals"][0].pop("indicative_price_minor")
    result = evaluate(payload)
    assert result["actions"][0]["skip_reason"] == "PRICE_INFORMATION_MISSING"


def test_budget_bound_and_deadline_restrictions():
    high = case(offer_price=200000)
    assert evaluate(high)["actions"][0]["skip_reason"] == "OUTSIDE_BUDGET"
    too_late = case()
    too_late["deadline_minutes"] = 1
    assert evaluate(too_late)["actions"][0]["skip_reason"] == "DEADLINE_INFEASIBLE"


def test_bayesian_signal_changes_assumed_posterior_not_verification():
    payload = case()
    payload["proposals"][0]["signals"] = [{"evidence_kind":"MERCHANT_REPORTED_UNVERIFIED",
        "observed_positive":True, "assumed_sensitivity":"0.9", "assumed_specificity":"0.8", "source_reference":"report_1"}]
    result = evaluate(payload)
    posterior = result["evidence_traces"][0]["assumed_posterior"]
    assert posterior > 0.65
    assert result["purchase_allowed"] is False
    assert result["current_verification_baseline"] is None


def test_impossible_evidence_rejected():
    payload = case()
    payload["proposals"][0]["signals"] = [{"evidence_kind":"OPERATOR_ASSUMPTION",
        "observed_positive":True, "assumed_sensitivity":"0", "assumed_specificity":"1", "source_reference":"test_imp"}]
    with pytest.raises(ValueError, match="Impossible likelihood"):
        evaluate(payload)


def test_reject_duplicate_unknown_places_and_missing_budget():
    payload = case()
    payload["proposals"].append(dict(payload["proposals"][0]))
    with pytest.raises(ValidationError): EvidencePlanInput14A1.model_validate(payload)
    payload = case(); payload["proposals"][0]["place_id"] = "unknown_001"
    with pytest.raises(ValidationError): EvidencePlanInput14A1.model_validate(payload)
    payload = case(); payload["snapshot"]["customer"]["budget_minor"] = None
    with pytest.raises(ValidationError): EvidencePlanInput14A1.model_validate(payload)


def test_no_unacknowledged_hypotheses():
    payload = case(); payload["assumption_acknowledged"] = False
    with pytest.raises(ValidationError): EvidencePlanInput14A1.model_validate(payload)


def test_api_requires_identity_and_gate(monkeypatch):
    monkeypatch.setenv("EVIDENCE_PLANNER_14A1_ENABLED", "true")
    client = TestClient(app)
    result = client.post("/api/v1/decision/evidence-plan", json=case())
    assert result.status_code == 401
    app.dependency_overrides[require_firebase_client] = lambda: "test_customer"
    try:
        result = client.post("/api/v1/decision/evidence-plan", json=case())
        assert result.status_code == 200
        assert result.json()["purchase_allowed"] is False
        monkeypatch.setenv("EVIDENCE_PLANNER_14A1_ENABLED", "false")
        assert client.post("/api/v1/decision/evidence-plan", json=case()).status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_route_does_not_unmount_existing_routes():
    try:
        from fastapi.routing import iter_route_contexts
    except ImportError:  # compatible with pre-0.137 FastAPI in snapshot rehearsal
        def iter_route_contexts(items):
            return items
    paths = {(r.path,m) for r in iter_route_contexts(app.routes) for m in getattr(r, "methods", set())}
    for path in ["/api/v1/decision/replan", "/api/v1/decision/verification-plan",
                 "/api/v1/products/research", "/api/v1/discovery/stores", "/api/v1/decision/evidence-plan"]:
        assert (path, "POST") in paths


def test_multiple_candidates_rank_best_expected_net_value():
    payload = case(include_report=False)
    payload["snapshot"]["merchants"].append({"place_id": "place_002", "name": "Second example"})
    payload["proposals"].append({
        "place_id": "place_002", "indicative_price_minor": 65000,
        "assumed_prior_feasible": "0.95", "assumed_response_probability": "0.95",
        "verification_cost_minor": 100, "verification_delay_minutes": 1,
    })
    result = evaluate(payload)
    assert result["recommended_action_id"] == "VERIFY_place_002"
    assert result["current_verification_baseline"] is None


def test_no_expected_response_cannot_win():
    payload = case()
    payload["proposals"][0]["assumed_response_probability"] = "0"
    result = evaluate(payload)
    assert result["recommended_action_id"] is None
    assert result["actions"][0]["skip_reason"] == "NO_EXPECTED_RESPONSE"
