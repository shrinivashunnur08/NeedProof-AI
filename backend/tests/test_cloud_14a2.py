"""14A.2: fail-closed evidence, basket constraints, and route gating."""
import os

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.basket_optimizer_14a2 import BasketPlan14A2, evaluate_basket_14a2
from app.cloud_decision_api import app, require_firebase_client


def payload():
    return {
        "items": [
            {"item_id": "charger", "name": "USB-C charger", "quantity": 1},
            {"item_id": "cable", "name": "USB-C cable", "quantity": 2},
        ],
        "merchants": [
            {"merchant_id": "a", "name": "Example merchant A", "fulfillment_fee_minor": 5000},
            {"merchant_id": "b", "name": "Example merchant B", "fulfillment_fee_minor": 0},
        ],
        "offers": [
            dict(sku="a-chg", item_id="charger", merchant_id="a", product_name="charger",
                 unit_price_minor=30000, stock_on_hand=2, delivery_eta_minutes=10,
                 merchant_verified=True, stock_verified=True, compatibility_verified=True,
                 delivery_verified=True, evidence_source="SIMULATION_VERIFIED"),
            dict(sku="b-chg", item_id="charger", merchant_id="b", product_name="charger",
                 unit_price_minor=35000, stock_on_hand=2, delivery_eta_minutes=15,
                 merchant_verified=True, stock_verified=True, compatibility_verified=True,
                 delivery_verified=True, evidence_source="SIMULATION_VERIFIED"),
            dict(sku="a-cbl", item_id="cable", merchant_id="a", product_name="cable",
                 unit_price_minor=5000, stock_on_hand=2, delivery_eta_minutes=10,
                 merchant_verified=True, stock_verified=True, compatibility_verified=True,
                 delivery_verified=True, evidence_source="SIMULATION_VERIFIED"),
            dict(sku="b-cbl", item_id="cable", merchant_id="b", product_name="cable",
                 unit_price_minor=8000, stock_on_hand=2, delivery_eta_minutes=15,
                 merchant_verified=True, stock_verified=True, compatibility_verified=True,
                 delivery_verified=True, evidence_source="SIMULATION_VERIFIED"),
            dict(sku="cheap-unverified", item_id="charger", merchant_id="a", product_name="charger",
                 unit_price_minor=10000, stock_on_hand=100, delivery_eta_minutes=2,
                 merchant_verified=True, stock_verified=True, compatibility_verified=True,
                 delivery_verified=True, evidence_source="MERCHANT_REPORTED_UNVERIFIED",
                 evidence_reference="merchant-report-test-001"),
        ],
        "budget_minor": 75000, "deadline_minutes": 60, "max_merchants": 2,
        "hypothetical_scenario_acknowledged": True,
    }


def run(p):
    return evaluate_basket_14a2(BasketPlan14A2.model_validate(p))


def test_exact_total_fees_and_quantities():
    data = run(payload())
    assert data["scenario_status"] in ("OPTIMAL", "FEASIBLE")
    assert data["synthetic_optimum"]["totals"]["total_minor"] == 45000
    assert {x["sku"] for x in data["synthetic_optimum"]["selected_offers"]} == {"a-chg", "a-cbl"}
    assert data["purchase_allowed"] is False
    assert data["real_merchant_inventory_verified"] is False


def test_unverified_low_price_never_selected_even_with_all_flags_true():
    data = run(payload())
    assert "cheap-unverified" not in {x["sku"] for x in data["synthetic_optimum"]["selected_offers"]}
    assert data["verification_backlog"][0]["evidence_source"] == "MERCHANT_REPORTED_UNVERIFIED"
    assert "NOT_A_VERIFIED_SYNTHETIC_FIXTURE" in data["verification_backlog"][0]["required_checks"]


def test_deadline_and_budget_fail_closed():
    p = payload(); p["deadline_minutes"] = 9
    assert run(p)["scenario_status"] == "INFEASIBLE"
    p = payload(); p["budget_minor"] = 20000
    assert run(p)["scenario_status"] == "INFEASIBLE"


def test_merchant_limit_changes_combination():
    p = payload(); p["max_merchants"] = 1
    data = run(p)
    assert data["scenario_status"] in ("OPTIMAL", "FEASIBLE")
    assert len(data["synthetic_optimum"]["used_merchants"]) == 1


def test_reported_stockout_is_not_selectable():
    p = payload(); p["offers"][0]["stock_on_hand"] = 0
    data = run(p)
    assert "a-chg" not in {x["sku"] for x in data["synthetic_optimum"]["selected_offers"]}


def test_duplicate_or_broken_references_rejected():
    p = payload(); p["items"][1]["item_id"] = "charger"
    with pytest.raises(ValidationError): BasketPlan14A2.model_validate(p)
    p = payload(); p["offers"][0]["merchant_id"] = "nonexistent"
    with pytest.raises(ValidationError): BasketPlan14A2.model_validate(p)


def test_mandatory_synthetic_acknowledgement():
    p = payload(); p["hypothetical_scenario_acknowledged"] = False
    with pytest.raises(ValidationError): BasketPlan14A2.model_validate(p)


def test_all_unverified_offers_produce_no_purchase_plan():
    p = payload()
    for offer in p["offers"]:
        offer["evidence_source"] = "MERCHANT_REPORTED_UNVERIFIED"
    data = run(p)
    assert data["scenario_status"] == "INFEASIBLE"
    assert data["synthetic_optimum"]["selected_offers"] == []
    assert len(data["verification_backlog"]) == 5


def test_authenticated_route_and_disabled_flag(monkeypatch):
    monkeypatch.delenv("BASKET_OPTIMIZER_14A2_ENABLED", raising=False)
    app.dependency_overrides[require_firebase_client] = lambda: "test-user"
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/commerce/basket-plan", json=payload())
            assert response.status_code == 503
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            response = client.post("/api/v1/commerce/basket-plan", json=payload())
            assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_enabled_route_has_no_purchase_authorization(monkeypatch):
    monkeypatch.setenv("BASKET_OPTIMIZER_14A2_ENABLED", "true")
    app.dependency_overrides[require_firebase_client] = lambda: "test-user"
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/commerce/basket-plan", json=payload())
            assert response.status_code == 200, response.text
            assert response.json()["purchase_allowed"] is False
    finally:
        app.dependency_overrides.clear()
