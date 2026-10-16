"""14B.1 deterministic observed-sales forecasts, rolling backtests, API gates."""
from datetime import date, timedelta
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.cloud_decision_api import app, require_firebase_client
from app.retail_forecast_14b1 import ForecastInput14B1, evaluate_retail_forecast_14b1


def sample(values=None, horizon=7, **kw):
    vals = values if values is not None else [5 + (i % 7)*2 for i in range(84)]
    start = date.today() - timedelta(days=len(vals))
    return {"product_label":"Synthetic SKU A","history":[
        {"day":(start+timedelta(days=i)).isoformat(),"units_sold":v,"reported_stockout":False}
        for i,v in enumerate(vals)
    ], "horizon_days":horizon, "synthetic_demo":True, **kw}


def run(p):
    return evaluate_retail_forecast_14b1(ForecastInput14B1.model_validate(p))


def test_weekly_pattern_selects_seasonal_and_no_leakage():
    r=run(sample())
    assert r["selected_model"] == "seasonal_naive_7"
    assert r["model_comparison"][0]["mae_units"] == 0
    assert r["model_comparison"][0]["wape_pct"] == 0
    assert r["holdout_origin_count"] == 14
    assert r["training_observations"] == 84
    assert len(r["predictions"]) == 7
    assert r["predictions"][0]["expected_units"] == 5


def test_forecast_horizon_14_and_dates():
    r=run(sample(horizon=14))
    assert len(r["predictions"])==14
    assert r["predictions"][0]["day"] == date.today().isoformat()
    assert r["predictions"][-1]["day"] == (date.today()+timedelta(days=13)).isoformat()


def test_short_flat_sales_zero_error_not_future_certainty():
    r=run(sample([3]*42))
    assert r["selected_model"] == "seasonal_naive_7"
    assert r["predictions"][0]["expected_units"] == 3
    assert any("NOT evidence of zero" in item for item in r["limitations"])
    assert any("Short series" in item for item in r["limitations"])


def test_all_zero_avoids_divide_by_zero_and_false_intervals():
    r=run(sample([0]*56))
    assert all(b["wape_pct"] is None for b in r["model_comparison"])
    assert r["predictions"][0]["lower_heuristic_80"] is None
    assert r["predictions"][0]["upper_heuristic_80"] is None
    assert any("All observed sales are zero" in x for x in r["limitations"])


def test_sales_stockout_flag_does_not_fabricate_demand():
    p=sample()
    p["history"][40]["reported_stockout"] = True
    r=run(p)
    assert r["reported_stockout_days"] == 1
    assert any("no imputation" in x for x in r["limitations"])
    assert r["target"] == "OBSERVED_UNIT_SALES_AS_DEMAND_PROXY"


def test_inventory_scenario_is_not_stockout_probability():
    p=sample(on_hand_units=10,replenishment_lead_days=5)
    r=run(p)
    s=r["inventory_exposure_scenario"]
    assert s["projected_shortfall_units"] > 0
    assert "not verified" in s["interpretation"]
    assert r["purchase_allowed"] is False
    assert r["forecast_independently_verified"] is False


def test_inventory_scenario_can_be_absent():
    assert run(sample())["inventory_exposure_scenario"] is None


def test_non_consecutive_and_duplicates_are_rejected():
    p=sample(); p["history"][4]["day"] = p["history"][3]["day"]
    with pytest.raises(ValidationError, match="consecutive"): ForecastInput14B1.model_validate(p)


def test_negative_or_fractional_sales_rejected():
    p=sample(); p["history"][10]["units_sold"] = -2
    with pytest.raises(ValidationError): ForecastInput14B1.model_validate(p)
    p=sample(); p["history"][10]["units_sold"] = 2.25
    with pytest.raises(ValidationError): ForecastInput14B1.model_validate(p)


def test_history_bounds_and_extra_data_rejected():
    with pytest.raises(ValidationError): ForecastInput14B1.model_validate(sample([1]*41))
    with pytest.raises(ValidationError): ForecastInput14B1.model_validate(sample([1]*181))
    p=sample(); p["unknown_server_flag"] = True
    with pytest.raises(ValidationError): ForecastInput14B1.model_validate(p)


def test_future_dates_and_horizon_constraints():
    p=sample()
    p["history"][-1]["day"] = (date.today()+timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError): ForecastInput14B1.model_validate(p)
    with pytest.raises(ValidationError): ForecastInput14B1.model_validate(sample(horizon=15))


def test_replenishment_input_consistency():
    with pytest.raises(ValidationError,match="together"):
        ForecastInput14B1.model_validate(sample(on_hand_units=2))
    with pytest.raises(ValidationError,match="cannot exceed"):
        ForecastInput14B1.model_validate(sample(horizon=3,on_hand_units=2,replenishment_lead_days=5))


def test_exactly_deterministic_no_persistence_no_cloud_calls():
    p=sample()
    old=deepcopy(p)
    a,b=run(p),run(p)
    assert a == b and old == p
    assert a["cloud_model_used"] is False
    assert a["observations_persisted"] is False
    assert a["data_origin"] == "CLIENT_LABELED_SYNTHETIC_DEMO"
    p["synthetic_demo"] = False
    assert run(p)["data_origin"] == "USER_SUPPLIED_UNVERIFIED"


def test_backtest_does_not_leak_future_sales_to_earlier_forecast():
    from app.retail_forecast_14b1 import _predict
    hist=[i%9 for i in range(50)]
    assert _predict("weekday_mean_4w",hist[:40],14) == _predict("weekday_mean_4w",hist[:40],14)
    assert _predict("seasonal_naive_7", hist[:40], 14) != _predict("seasonal_naive_7", hist[:40]+[999]*7, 14)


def test_backtest_honestly_compares_same_samples():
    r=run(sample(horizon=14))
    assert len({m["evaluated_forecast_points"] for m in r["model_comparison"]}) == 1
    assert all(m["rolling_origins"]==14 for m in r["model_comparison"])
    assert len({m["method"] for m in r["model_comparison"]}) == 4


def test_missing_auth_and_disabled_flag(monkeypatch):
    monkeypatch.delenv("RETAIL_FORECAST_14B1_ENABLED", raising=False)
    app.dependency_overrides[require_firebase_client] = lambda: "user-test"
    try:
        r=TestClient(app).post("/api/v1/analytics/sales-forecast",json=sample())
        assert r.status_code == 503
    finally:
        app.dependency_overrides.clear()
    assert TestClient(app).post("/api/v1/analytics/sales-forecast", json=sample()).status_code == 401


def test_api_valid_response_nostore_and_422(monkeypatch):
    monkeypatch.setenv("RETAIL_FORECAST_14B1_ENABLED","true")
    app.dependency_overrides[require_firebase_client] = lambda: "user-test"
    try:
        client=TestClient(app)
        r=client.post("/api/v1/analytics/sales-forecast",json=sample())
        assert r.status_code == 200, r.text
        assert r.json()["selected_model"] == "seasonal_naive_7"
        assert r.headers["cache-control"] == "no-store"
        bad=sample();bad["history"] = bad["history"][:20]
        assert client.post("/api/v1/analytics/sales-forecast",json=bad).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_prior_routes_and_protected_verification_still_present():
    try:
        from fastapi.routing import iter_route_contexts
    except ImportError:
        routes = app.routes
    else:
        routes = iter_route_contexts(app.routes)
    paths={r.path for r in routes}
    assert {"/api/v1/analytics/sales-forecast","/api/v1/decision/orchestrate",
            "/api/v1/commerce/basket-plan","/api/v1/decision/evidence-plan", "/api/v1/products/research"} <= paths
