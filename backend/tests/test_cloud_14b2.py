"""Guardrails, deterministic descriptive methods, and Firebase-gated 14B.2 route."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.retail_segments_14b2 import CommerceInsightsInput14B2, evaluate_commerce_insights_14b2
from app.cloud_decision_api import app, require_firebase_client


def example():
    profiles=[]
    for group in range(3):
        for j in range(10):
            profiles.append({
                "recency_days": (3, 35, 150)[group] + j%3,
                "orders_90d": (24, 8, 1)[group] + j%2,
                "spend_minor_90d": (120000, 32000, 1800)[group] + j*100,
            })
    baskets=[]
    for a,b in (("USB-C","CASE"),("CHARGER","CABLE"),("SCREEN","MOUSE")):
        baskets += [[a,b] for _ in range(10)]
    return {"profiles":profiles,"baskets":baskets,"minimum_pair_orders":3,"synthetic_demo":True}


def evaluate(value=None):
    return evaluate_commerce_insights_14b2(CommerceInsightsInput14B2.model_validate(value or example()))


def test_group_count_and_privacy():
    value=evaluate()
    groups=value["segmentation"]
    assert groups["selected_k"] == 3
    assert sum(x["count"] for x in groups["segments"]) == 30
    assert all(x["count"]>=5 for x in groups["segments"])
    assert groups["individual_assignments_disclosed"] is False
    assert "profiles" not in value and "baskets" not in value
    assert "customer_id" not in str(value)


def test_rules_are_order_level_and_have_sensible_metrics():
    value=evaluate()
    rules=value["basket_analysis"]["rules"]
    assert rules and any(r["antecedent_sku"]=="CASE" and r["consequent_sku"]=="USB-C" for r in rules)
    assert all(r["cooccurring_orders"]==10 and r["lift"]==3 for r in rules)
    assert all(r["confidence_wilson95_lower_pct"] < r["confidence_pct"] for r in rules)
    assert all(r["association_only"] for r in rules)


def test_permutation_stability_of_profile_partition_and_baskets():
    payload=example()
    first=evaluate(payload)
    payload["profiles"]=list(reversed(payload["profiles"]))
    payload["baskets"]=list(reversed(payload["baskets"]))
    assert first==evaluate(payload)


def test_identical_profiles_suppress_fake_segments():
    payload=example()
    payload["profiles"]=[{"recency_days":7,"orders_90d":3,"spend_minor_90d":5000} for _ in range(30)]
    r=evaluate(payload)["segmentation"]
    assert r["selected_k"]==1 and r["exploratory_silhouette"] is None


def test_no_associations_for_independent_mixture():
    payload=example()
    payload["baskets"]=[]
    for a in ("A","B","C","D"):
        for b in ("X","Y","Z"):
            payload["baskets"] += [[a,b]]*3
    assert evaluate(payload)["basket_analysis"]["rules"]==[]


def test_pair_threshold_and_rule_cap():
    payload=example(); payload["minimum_pair_orders"]=11
    assert evaluate(payload)["basket_analysis"]["rules"]==[]
    payload["minimum_pair_orders"]=3
    assert len(evaluate(payload)["basket_analysis"]["rules"])<=12


def test_deterministic_no_io_no_purchase():
    data=example(); saved=deepcopy(data)
    first=evaluate(data)
    assert evaluate(data)==first and data==saved
    assert first["source_records_persisted"] is False
    assert first["direct_identifiers_accepted"] is False
    assert first["cloud_model_used"] is False
    assert first["purchase_allowed"] is False
    assert first["personalized_targeting_allowed"] is False
    assert first["independently_verified"] is False
    assert first["data_origin"]=="CLIENT_LABELED_SYNTHETIC_DEMO"


def test_user_data_provenance():
    d=example();d["synthetic_demo"]=False
    assert evaluate(d)["data_origin"]=="USER_SUPPLIED_UNVERIFIED_AGGREGATES"


def test_reject_profile_under_and_over_bound():
    for count in (23,121):
        d=example(); d["profiles"]=(d["profiles"]*5)[:count]
        with pytest.raises(ValidationError): CommerceInsightsInput14B2.model_validate(d)


def test_reject_basket_under_and_over_bound():
    for count in (23,201):
        d=example(); d["baskets"]=(d["baskets"]*7)[:count]
        with pytest.raises(ValidationError): CommerceInsightsInput14B2.model_validate(d)


def test_reject_malformed_baskets_and_product_codes():
    d=example(); d["baskets"][0]=["A","A"]
    with pytest.raises(ValidationError,match="Duplicate"): CommerceInsightsInput14B2.model_validate(d)
    d=example(); d["baskets"][0]=["A"]
    with pytest.raises(ValidationError,match="2–8"): CommerceInsightsInput14B2.model_validate(d)
    d=example(); d["baskets"][0]=["email@example.com","SKU"]
    with pytest.raises(ValidationError,match="Product"): CommerceInsightsInput14B2.model_validate(d)
    d=example();d["baskets"][0] = ["S"+str(i) for i in range(9)]
    with pytest.raises(ValidationError): CommerceInsightsInput14B2.model_validate(d)


def test_reject_too_many_skus():
    d=example(); d["baskets"]=[["COMMON",f"S{i}"] for i in range(35)]
    with pytest.raises(ValidationError,match="30"): CommerceInsightsInput14B2.model_validate(d)


def test_reject_additional_fields_and_invalid_numbers():
    d=example();d["customer_email"]="secret@example.com"
    with pytest.raises(ValidationError): CommerceInsightsInput14B2.model_validate(d)
    d=example();d["profiles"][0]["email"]="secret@example.com"
    with pytest.raises(ValidationError): CommerceInsightsInput14B2.model_validate(d)
    d=example();d["profiles"][0]["spend_minor_90d"]=-1
    with pytest.raises(ValidationError): CommerceInsightsInput14B2.model_validate(d)
    d=example();d["profiles"][0]["orders_90d"]=1.3
    with pytest.raises(ValidationError): CommerceInsightsInput14B2.model_validate(d)


def test_reject_too_few_or_many_pair_orders():
    d=example();d["minimum_pair_orders"]=2
    with pytest.raises(ValidationError): CommerceInsightsInput14B2.model_validate(d)
    d=example();d["minimum_pair_orders"]=21
    with pytest.raises(ValidationError): CommerceInsightsInput14B2.model_validate(d)


def test_unauthenticated_and_flag_off(monkeypatch):
    monkeypatch.delenv("RETAIL_INSIGHTS_14B2_ENABLED", raising=False)
    c=TestClient(app)
    assert c.post("/api/v1/analytics/cohort-basket-insights",json=example()).status_code==401
    app.dependency_overrides[require_firebase_client] = lambda: "test-user"
    try:
        assert c.post("/api/v1/analytics/cohort-basket-insights",json=example()).status_code==503
    finally:
        app.dependency_overrides.clear()


def test_authenticated_route_no_store_and_validation(monkeypatch):
    monkeypatch.setenv("RETAIL_INSIGHTS_14B2_ENABLED","true")
    app.dependency_overrides[require_firebase_client] = lambda: "test-user"
    try:
        c=TestClient(app)
        response=c.post("/api/v1/analytics/cohort-basket-insights",json=example())
        assert response.status_code==200, response.text
        assert response.headers["cache-control"]=="no-store"
        assert response.json()["mode"]=="DESCRIPTIVE_COHORT_BASKET_INSIGHTS_14B2"
        bad=example();bad["baskets"] = bad["baskets"][:2]
        assert c.post("/api/v1/analytics/cohort-basket-insights",json=bad).status_code==422
    finally:
        app.dependency_overrides.clear()


def test_existing_routes_remain_exposed():
    try:
        from fastapi.routing import iter_route_contexts
    except ImportError:
        routes = app.routes
    else:
        routes = iter_route_contexts(app.routes)
    names={getattr(r,"path",None) for r in routes}
    assert {"/api/v1/analytics/cohort-basket-insights","/api/v1/analytics/sales-forecast",
            "/api/v1/decision/orchestrate","/api/v1/commerce/basket-plan"} <= names
