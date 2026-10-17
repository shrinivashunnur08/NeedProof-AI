"""14B.3: deterministic inventory evidence, anomaly and authentication contract tests."""
from copy import deepcopy
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.inventory_intelligence_14b3 import InventoryInput14B3, evaluate_inventory_14b3
from app.cloud_decision_api import app, require_firebase_client


def example():
    first = date.today() - timedelta(days=55)
    history=[]
    on_hand=500
    for i in range(56):
        received=20 if i%7==0 else 0
        sold=4+(i%7==1)*2
        # keep stock realistic; add an exceptional spike at day 40
        if i==40: sold=32
        close=on_hand+received-sold
        history.append({"day":(first+timedelta(days=i)).isoformat(),
                        "opening_units":on_hand,"received_units":received,
                        "sold_units":sold,"closing_units":close,"reported_stockout":False})
        on_hand=close
    return {"sku_code":"SKU-DEMO-1","lead_time_days":7,"history":history,"synthetic_demo":True}


def evaluate(data=None):
    return evaluate_inventory_14b3(InventoryInput14B3.model_validate(data or example()))


def test_stock_reconciliation_and_forecast_reuse():
    result=evaluate()
    assert result["mode"]=="REPORTED_STOCK_RECONCILIATION_14B3"
    assert result["inventory_review"]["totals"]["balance_mismatches"]==0
    assert result["inventory_review"]["totals"]["cross_day_gaps"]==0
    assert result["lead_time_scenario"]["forecast_sales_proxy_units"] >= 0
    assert result["forecast_model_reused_14b1"] in {"seasonal_naive_7","moving_average_7","weekday_mean_4w","damped_trend"}
    assert result["source_records_persisted"] is False and result["purchase_allowed"] is False
    assert result["inventory_independently_verified"] is False and result["fraud_determined"] is False


def test_determinism_no_mutation_no_exposure_of_raw_history():
    sample=example(); original=deepcopy(sample)
    result=evaluate(sample)
    assert result==evaluate(sample) and sample==original
    assert "history" not in result and "raw_transactions" not in result
    assert result["cloud_model_used"] is False


def test_provenance_of_user_input():
    sample=example(); sample["synthetic_demo"]=False
    assert evaluate(sample)["data_origin"]=="USER_SUPPLIED_UNVERIFIED"


def test_single_mismatch_flag_and_signed_difference():
    sample=example(); sample["history"][35]["closing_units"]+=7
    result=evaluate(sample)
    signals=result["inventory_review"]["signals"]
    assert result["inventory_review"]["totals"]["balance_mismatches"]==1
    assert any(x["signal"]=="BALANCE_DIFFERENCE" and x["difference_units"]==7 for x in signals)
    assert result["fraud_determined"] is False


def test_cross_day_gap_separate_from_mismatch():
    sample=example(); sample["history"][35]["opening_units"]+=8
    result=evaluate(sample)
    assert result["inventory_review"]["totals"]["cross_day_gaps"]==1
    assert result["inventory_review"]["totals"]["balance_mismatches"]==1


def test_past_only_spike_and_no_future_leakage():
    sample=example()
    result=evaluate(sample)
    assert result["inventory_review"]["totals"]["sales_spikes"]>=1
    first_spike=next(x for x in result["inventory_review"]["signals"] if x["signal"]=="UNUSUAL_SALES_SPIKE")
    assert first_spike["day"]==sample["history"][40]["day"]
    # Changing future records cannot change whether day 40 is identified.
    modified=deepcopy(sample)
    for row in modified["history"][41:]: row["sold_units"]=150
    updated=evaluate(modified)
    assert any(x["signal"]=="UNUSUAL_SALES_SPIKE" and x["day"]==first_spike["day"]
               for x in updated["inventory_review"]["signals"])


def test_no_false_spikes_for_constant_sales():
    sample=example()
    on_hand=500
    for row in sample["history"]:
        row.update(opening_units=on_hand,received_units=5,sold_units=5,closing_units=on_hand)
    result=evaluate(sample)
    assert result["inventory_review"]["totals"]["sales_spikes"]==0


def test_empty_clean_windows_suppresses_empirical_claim():
    sample=example()
    for row in sample["history"]: row["reported_stockout"]=True
    result=evaluate(sample)
    assert result["lead_time_scenario"]["status"]=="INSUFFICIENT_CLEAN_WINDOWS"
    assert result["lead_time_scenario"]["empirical_80p_units"] is None
    assert result["average_nonstockout_sales_units"] is None
    assert result["coverage_days_at_observed_sales_rate"] is None
    assert result["observed_stockout_days"]==56


def test_replenishment_scenario_without_purchase_authorization():
    sample=example()
    sample["history"][-1]["closing_units"]=0
    result=evaluate(sample)
    assert result["lead_time_scenario"]["status"]=="REPLENISHMENT_REVIEW"
    assert result["lead_time_scenario"]["gap_to_empirical_80p_units"]>0
    assert result["purchase_allowed"] is False


def test_limited_review_signals_not_hidden_total():
    sample=example()
    for row in sample["history"]: row["closing_units"]+=1
    result=evaluate(sample)["inventory_review"]
    assert result["total_review_signals"]>=50
    assert len(result["signals"])<=15 and result["signals_truncated"] is True


def test_reject_too_short_or_long_series():
    for n in (41,91):
        sample=example()
        if n==91:
            # Use chronological rows and a different start date.
            template=deepcopy(sample["history"][0])
            sample["history"]=[{**template,"day":(date.today()-timedelta(days=90-i)).isoformat()}
                               for i in range(91)]
        else: sample["history"]=sample["history"][:41]
        with pytest.raises(ValidationError): InventoryInput14B3.model_validate(sample)


def test_reject_duplicate_gap_reversed_and_future_dates():
    for new_day in ["2099-01-01",None]:
        sample=example()
        sample["history"][40]["day"]=sample["history"][39]["day"] if new_day is None else new_day
        with pytest.raises(ValidationError): InventoryInput14B3.model_validate(sample)
    sample=example(); sample["history"][40]["day"]=(date.today()-timedelta(days=3)).isoformat()
    with pytest.raises(ValidationError): InventoryInput14B3.model_validate(sample)


def test_reject_pii_extra_fields_and_bad_codes():
    sample=example(); sample["customer_email"]="person@example.com"
    with pytest.raises(ValidationError): InventoryInput14B3.model_validate(sample)
    sample=example();sample["history"][0]["customer_id"]="uid"
    with pytest.raises(ValidationError): InventoryInput14B3.model_validate(sample)
    sample=example();sample["sku_code"]="email@example.com"
    with pytest.raises(ValidationError): InventoryInput14B3.model_validate(sample)


def test_reject_negative_and_noninteger_quantities():
    for value in (-1,1.2,"12",1_000_001):
        sample=example();sample["history"][10]["sold_units"]=value
        with pytest.raises(ValidationError): InventoryInput14B3.model_validate(sample)


def test_lead_days_guardrails():
    for lead in (0,15):
        sample=example();sample["lead_time_days"]=lead
        with pytest.raises(ValidationError): InventoryInput14B3.model_validate(sample)


def test_auth_gate_and_default_off(monkeypatch):
    monkeypatch.delenv("INVENTORY_INTELLIGENCE_14B3_ENABLED",raising=False)
    client=TestClient(app)
    assert client.post("/api/v1/analytics/inventory-review",json=example()).status_code==401
    app.dependency_overrides[require_firebase_client]=lambda:"test-user"
    try:
        assert client.post("/api/v1/analytics/inventory-review",json=example()).status_code==503
    finally: app.dependency_overrides.clear()


def test_authenticated_route_success_invalid_payload(monkeypatch):
    monkeypatch.setenv("INVENTORY_INTELLIGENCE_14B3_ENABLED","true")
    app.dependency_overrides[require_firebase_client]=lambda:"test-user"
    try:
        c=TestClient(app)
        response=c.post("/api/v1/analytics/inventory-review",json=example())
        assert response.status_code==200, response.text
        assert response.headers["cache-control"]=="no-store"
        assert response.json()["mode"]=="REPORTED_STOCK_RECONCILIATION_14B3"
        sample=example();sample["history"]=sample["history"][:2]
        assert c.post("/api/v1/analytics/inventory-review",json=sample).status_code==422
    finally: app.dependency_overrides.clear()


def test_other_routes_still_registered():
    try:
        from fastapi.routing import iter_route_contexts
    except ImportError:
        routes=app.routes
    else:
        routes=iter_route_contexts(app.routes)
    paths={getattr(route,"path",None) for route in routes}
    assert {"/api/v1/analytics/inventory-review","/api/v1/analytics/cohort-basket-insights",
            "/api/v1/analytics/sales-forecast","/api/v1/decision/orchestrate"}<=paths
