"""16A offline smoke test: a coherent fixture-only demo with real engine calls."""
from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.cloud_decision_api import app, require_firebase_client
from app.guided_journey_16a import GuidedJourneyInput16A, evaluate_guided_journey_16a


def payload(scenario="reported_offer", **extra):
    return {"scenario": scenario, "simulation_acknowledged": True, **extra}


def run(scenario="reported_offer", **extra):
    return evaluate_guided_journey_16a(GuidedJourneyInput16A.model_validate(payload(scenario, **extra)))


def test_reported_offer_is_provisional_and_not_checkout():
    v=run()
    assert v["mode"]=="GUIDED_EVIDENCE_JOURNEY_16A"
    assert v["workflow"]["workflow_state"]=="PROVISIONAL_VERIFICATION_NEEDED"
    assert v["workflow"]["merchant_replanning"]["selected"] is not None
    assert v["workflow"]["product_research"]["sources_verified"] is False
    assert len(v["workflow"]["workflow_trace"])==5
    assert v["workflow"]["hypothetical_verification_plan"]["recommended_action_id"] is not None


def test_stockout_replans_and_does_not_promote_other_missing_claim():
    v=run("stockout")
    assert v["workflow"]["workflow_state"]=="MORE_EVIDENCE_NEEDED"
    assert v["workflow"]["change_detection"]["changed"] is True
    assert {c["event"] for c in v["workflow"]["change_detection"]["changes"]}=={"CLIENT_EVIDENCE_CHANGED"}
    assert v["workflow"]["merchant_replanning"]["selected"] is None
    assert v["workflow"]["purchase_allowed"] is False


def test_contradiction_blocks_evsi_promotion():
    v=run("document_conflict")
    assert v["workflow"]["workflow_state"]=="RESEARCH_CONFLICT"
    assert v["workflow"]["recommended_next_action"]=="RECONCILE_CONFLICTING_DOCUMENT_EXCERPTS"
    assert len(v["workflow"]["product_research"]["passages"])>=1
    assert v["stock_independently_verified"] is False


def test_discovery_needed_without_merchants():
    v=run("no_merchants")
    assert v["workflow"]["workflow_state"]=="DISCOVERY_NEEDED"
    assert v["workflow"]["recommended_next_action"]=="DISCOVER_MERCHANTS"
    assert v["workflow"]["hypothetical_verification_plan"] is None


@pytest.mark.parametrize("scenario",["reported_offer","stockout","document_conflict","no_merchants"])
def test_universal_safety_invariants(scenario):
    v=run(scenario)
    for key in ("journey_is_historical_verified_record","real_merchant_contact","stock_independently_verified","purchase_allowed","cloud_model_used","database_used","source_records_persisted","business_context_is_derived_from_customer_journey"):
        assert v[key] is False, (scenario,key)
    assert v["fixture_origin"]=="SERVER_OWNED_SYNTHETIC_NOT_REAL_MERCHANTS"
    assert v["workflow"]["synthetic_basket_scenario"]["purchase_allowed"] is False
    assert v["workflow"]["gemini_used"] is False
    assert v["workflow"]["merchant_contact_performed"] is False
    assert all("source" in step for step in v["workflow"]["workflow_trace"])
    assert "fictional" in " ".join(v["limitations"]).lower()


def test_bi_aggregate_is_separate_not_authenticated_upstream():
    v=run()
    bi=v["separate_illustrative_business_context"]
    assert bi["mode"]=="AGGREGATE_BI_COMMAND_CENTER_14B4"
    assert bi["data_origin"]=="CLIENT_LABELED_SYNTHETIC_DEMO"
    assert bi["coverage"]["available_modules"]==4
    assert bi["purchase_allowed"] is False
    assert bi["source_records_persisted"] is False
    assert v["business_context_is_derived_from_customer_journey"] is False


def test_optional_bi_can_be_omitted():
    v=run(include_illustrative_business_context=False)
    assert v["separate_illustrative_business_context"] is None


def test_required_simulation_acknowledgement():
    for bad in (False, "true", None):
        with pytest.raises(ValidationError):
            GuidedJourneyInput16A.model_validate(payload(simulation_acknowledged=bad))
    with pytest.raises(ValidationError):
        GuidedJourneyInput16A.model_validate({"scenario":"reported_offer"})


def test_strict_input_rejects_extra_or_synthetic_impersonation():
    for example in (
        payload(merchant_id="real_merchant_id"),
        payload(user_email="user@example.org"),
        payload("not_supported"),
        payload(include_illustrative_business_context="yes"),
    ):
        with pytest.raises(ValidationError):GuidedJourneyInput16A.model_validate(example)


def test_response_excludes_sensitive_input_and_purchases():
    v=run()
    rendered=json.dumps(v).lower()
    assert "@example.org" not in rendered
    assert '"purchase_allowed": true' not in rendered
    assert "api_key" not in rendered
    assert "fixture_store_a" in rendered


def test_request_does_not_mutate_inputs():
    p=payload("stockout")
    original=deepcopy(p)
    GuidedJourneyInput16A.model_validate(p)
    assert p==original


def test_default_off_and_auth_requirements(monkeypatch):
    monkeypatch.delenv("GUIDED_JOURNEY_16A_ENABLED",raising=False)
    client=TestClient(app)
    assert client.post("/api/v1/demo/guided-journey",json=payload()).status_code==401
    app.dependency_overrides[require_firebase_client]=lambda:"synthetic-test-user"
    try:
        assert client.post("/api/v1/demo/guided-journey",json=payload()).status_code==503
    finally: app.dependency_overrides.clear()


def test_authorized_local_api_and_caching(monkeypatch):
    monkeypatch.setenv("GUIDED_JOURNEY_16A_ENABLED","true")
    app.dependency_overrides[require_firebase_client]=lambda:"synthetic-test-user"
    try:
        c=TestClient(app)
        for scenario in ("reported_offer","stockout","document_conflict","no_merchants"):
            r=c.post("/api/v1/demo/guided-journey",json=payload(scenario))
            assert r.status_code==200,(scenario,r.text)
            assert r.headers.get("cache-control")=="no-store"
            assert r.json()["purchase_allowed"] is False
        bad=c.post("/api/v1/demo/guided-journey",json=payload("unknown"))
        assert bad.status_code==422
    finally:app.dependency_overrides.clear()


def test_reject_large_request(monkeypatch):
    monkeypatch.setenv("GUIDED_JOURNEY_16A_ENABLED","true")
    r=TestClient(app).post("/api/v1/demo/guided-journey",data="x"*40000,headers={"content-type":"application/json"})
    assert r.status_code==413


def test_old_routes_preserved():
    try:from fastapi.routing import iter_route_contexts
    except ImportError: routes=app.routes
    else: routes=iter_route_contexts(app.routes)
    paths={r.path for r in routes}
    assert {"/api/v1/demo/guided-journey","/api/v1/decision/orchestrate","/api/v1/analytics/command-center","/api/v1/products/research","/health"}<=paths
