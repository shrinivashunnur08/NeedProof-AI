
from fastapi.testclient import TestClient

from app.algorithms.commerce_demo import demo_plan
from app.main import app


client = TestClient(app)


def test_default_optimal_basket():
    result = demo_plan()

    assert result["status"] == "OPTIMAL"
    assert result["mode"] == "SYNTHETIC_OPTIMIZATION"

    assert result["totals"]["total_minor"] == 156000
    assert result["totals"]["remaining_minor"] == 24000

    selected = {
        offer["sku"]
        for offer in result["selected_offers"]
    }

    assert selected == {
        "CHG-A",
        "CBL-B",
        "MOU-B",
    }


def test_fulfillment_fees_are_charged_once():
    result = demo_plan()

    assert (
        result["totals"]["subtotal_minor"]
        == 144000
    )

    assert (
        result["totals"]["fulfillment_fees_minor"]
        == 12000
    )

    assert len(result["used_merchants"]) == 2


def test_single_merchant_constraint():
    result = demo_plan(max_merchants=1)

    assert result["status"] == "OPTIMAL"

    assert (
        result["totals"]["total_minor"]
        == 159800
    )

    assert len(result["used_merchants"]) == 1

    assert (
        result["used_merchants"][0]["name"]
        == "Harbor Electronics"
    )


def test_insufficient_budget():
    result = demo_plan(budget_inr=1559)

    assert result["status"] == "INFEASIBLE"
    assert result["selected_offers"] == []
    assert result["totals"] is None


def test_urgent_deadline():
    result = demo_plan(deadline_minutes=10)

    assert result["status"] == "INFEASIBLE"
    assert result["totals"] is None


def test_unverified_offers_are_excluded():
    result = demo_plan()

    exclusions = {
        offer["sku"]: offer["reasons"]
        for offer in result["excluded_offers"]
    }

    assert "UNVERIFIED_EVIDENCE_SOURCE" in (
        exclusions["CHG-UNVERIFIED"]
    )

    assert "INSUFFICIENT_STOCK" in (
        exclusions["CBL-OUT-OF-STOCK"]
    )

    selected = {
        offer["sku"]
        for offer in result["selected_offers"]
    }

    assert "CHG-UNVERIFIED" not in selected
    assert "CBL-OUT-OF-STOCK" not in selected


def test_optimization_api():
    response = client.get(
        "/api/optimization/demo-plan"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "OPTIMAL"


def test_invalid_parameters():
    response = client.get(
        "/api/optimization/demo-plan",
        params={"max_merchants": 0},
    )

    assert response.status_code == 422
