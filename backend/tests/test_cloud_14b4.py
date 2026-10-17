"""Chunk 14B.4: bounded aggregate BI synthesis and auth/flag contracts."""
from copy import deepcopy
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.bi_command_center_14b4 import BIInput14B4, evaluate_bi_command_center_14b4
from app.cloud_decision_api import app, require_firebase_client


def sample():
    return {
        "as_of": date.today().isoformat(), "synthetic_demo": True,
        "forecast": {"sku_code": "DEMO-SKU", "projected_sales_units": 53.4,
                     "horizon_days": 7, "backtest_wape_pct": 17.5, "reported_stockout_days": 0},
        "inventory": {"sku_code": "DEMO-SKU", "reported_on_hand_units": 25,
                      "balance_mismatches": 1, "cross_day_gaps": 0,
                      "unusual_sales_days": 2, "modeled_lead_time_shortfall_units": 14.6},
        "cohorts": {"anonymous_profile_count": 48, "aggregate_cohort_count": 2,
                    "minimum_cohort_size": 9, "association_rule_count": 3},
        "verification": {"candidates_considered": 4, "unresolved_evidence_items": 2,
                         "provisional_candidates": 3},
    }


def run(data=None):
    return evaluate_bi_command_center_14b4(BIInput14B4.model_validate(data or sample()))


def test_mode_privacy_safety_and_provenance():
    v = run()
    assert v["mode"] == "AGGREGATE_BI_COMMAND_CENTER_14B4"
    assert v["data_origin"] == "CLIENT_LABELED_SYNTHETIC_DEMO"
    for field in ("source_records_persisted", "independently_verified", "cloud_model_used",
                  "bigquery_used", "purchase_allowed", "fraud_determined", "individual_customer_data_returned"):
        assert v[field] is False
    assert len(v["limitations"]) >= 5


def test_data_not_returned_and_determinism():
    source=sample(); original=deepcopy(source)
    v=run(source)
    assert v==run(source) and source==original
    assert "forecast" not in v and "inventory" not in v and "cohorts" not in v and "verification" not in v
    assert all("source_module" in m and "data_origin" in m for m in v["metrics"])


def test_default_unverified_origin():
    data=sample(); data["synthetic_demo"]=False
    assert run(data)["data_origin"]=="USER_SUPPLIED_UNVERIFIED_AGGREGATE"


def test_coverage_all_and_summary():
    v=run()
    assert v["coverage"]["available_modules"]==4
    assert v["coverage"]["missing_modules"]==[]
    assert "4/4" in v["executive_summary"]


def test_partial_data_coverage():
    data=sample(); data["cohorts"]=None; data["verification"]=None
    v=run(data)
    assert v["coverage"]["available_modules"]==2
    assert set(v["coverage"]["missing_modules"])=={"cohorts", "verification"}
    assert "missing_modules" in {x["key"] for x in v["review_queue"]}


def test_single_module_is_accepted():
    data=sample(); data["inventory"]=data["cohorts"]=data["verification"]=None
    assert run(data)["coverage"]["available_modules"]==1


def test_empty_bundle_rejected():
    data=sample()
    for key in ("forecast","inventory","cohorts","verification"):data[key]=None
    with pytest.raises(ValidationError):BIInput14B4.model_validate(data)


def test_reconciliation_shortfall_and_verification_action_priority():
    v=run()
    keys={x["key"]:x for x in v["review_queue"]}
    assert keys["stock_reconciliation"]["priority"]==1
    assert keys["lead_time_gap"]["priority"]==1
    assert keys["verification_backlog"]["priority"]==1
    assert all(x["requires_human_verification"] for x in v["review_queue"])
    assert v["review_queue"]==sorted(v["review_queue"], key=lambda x:(x["priority"],x["key"]))


def test_no_claims_when_no_findings():
    data=sample()
    data["inventory"].update(balance_mismatches=0,cross_day_gaps=0,unusual_sales_days=0,modeled_lead_time_shortfall_units=0)
    data["verification"].update(unresolved_evidence_items=0,provisional_candidates=0)
    assert not {"stock_reconciliation","lead_time_gap","verification_backlog"}&{x["key"] for x in run(data)["review_queue"]}


def test_wape_is_warning_not_a_calibrated_score():
    data=sample();data["forecast"]["backtest_wape_pct"]=40
    assert "forecast_accuracy" in {x["key"] for x in run(data)["review_queue"]}
    assert "calibrated" in " ".join(run(data)["limitations"])


def test_missing_wape_is_allowed_and_not_invented():
    data=sample();data["forecast"]["backtest_wape_pct"]=None
    v=run(data)
    assert not any(m["key"]=="forecast_wape" for m in v["metrics"])


def test_old_snapshot_warns():
    data=sample(); data["as_of"]=(date.today()-timedelta(days=20)).isoformat()
    assert "stale_snapshot" in {x["key"] for x in run(data)["review_queue"]}


def test_future_date_rejected():
    data=sample();data["as_of"]=(date.today()+timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError):BIInput14B4.model_validate(data)


def test_product_mismatch_rejected():
    data=sample();data["inventory"]["sku_code"]="DIFFERENT"
    with pytest.raises(ValidationError):BIInput14B4.model_validate(data)


def test_identifying_input_fields_rejected():
    data=sample();data["customer_email"]="person@example.com"
    with pytest.raises(ValidationError):BIInput14B4.model_validate(data)
    data=sample();data["cohorts"]["customer_id"]="ABC"
    with pytest.raises(ValidationError):BIInput14B4.model_validate(data)
    data=sample();data["forecast"]["sku_code"]="person@example.com"
    with pytest.raises(ValidationError):BIInput14B4.model_validate(data)


def test_invalid_float_and_negative_values_rejected():
    for value in (float("nan"),float("inf"),-1,10_000_001):
        data=sample();data["forecast"]["projected_sales_units"]=value
        with pytest.raises(ValidationError):BIInput14B4.model_validate(data)


def test_cohort_min_size_and_relationship_validated():
    data=sample(); data["cohorts"].update(anonymous_profile_count=24,aggregate_cohort_count=4,minimum_cohort_size=7)
    with pytest.raises(ValidationError):BIInput14B4.model_validate(data)
    data=sample();data["cohorts"]["minimum_cohort_size"]=3
    with pytest.raises(ValidationError):BIInput14B4.model_validate(data)


def test_provisional_count_cannot_exceed_candidates():
    data=sample();data["verification"]["provisional_candidates"]=9
    with pytest.raises(ValidationError):BIInput14B4.model_validate(data)


def test_authentication_and_default_feature_off(monkeypatch):
    monkeypatch.delenv("BI_COMMAND_CENTER_14B4_ENABLED",raising=False)
    client=TestClient(app)
    assert client.post("/api/v1/analytics/command-center",json=sample()).status_code==401
    app.dependency_overrides[require_firebase_client]=lambda:"test-user"
    try:
        assert client.post("/api/v1/analytics/command-center",json=sample()).status_code==503
    finally: app.dependency_overrides.clear()


def test_auth_success_no_cache_and_bad_input(monkeypatch):
    monkeypatch.setenv("BI_COMMAND_CENTER_14B4_ENABLED","true")
    app.dependency_overrides[require_firebase_client]=lambda:"test-user"
    try:
        c=TestClient(app)
        response=c.post("/api/v1/analytics/command-center",json=sample())
        assert response.status_code==200,response.text
        assert response.headers["cache-control"]=="no-store"
        assert response.json()["mode"]=="AGGREGATE_BI_COMMAND_CENTER_14B4"
        payload=sample();payload["inventory"]["sku_code"]="BAD@CODE"
        assert c.post("/api/v1/analytics/command-center",json=payload).status_code==422
    finally: app.dependency_overrides.clear()
