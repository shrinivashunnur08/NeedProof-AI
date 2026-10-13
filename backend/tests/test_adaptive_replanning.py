
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.algorithms.adaptive_replanning import (
    ReplanInput,
    evaluate_replan,
)
from app.api.merchant_onboarding import local_only
from app.main import app


NOW = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)


def merchant(
    place_id: str,
    price: int,
    stock: int,
    *,
    minutes_old: int = 5,
    assessment: bool = True,
    product: str = "65W USB-C PD laptop charger",
    delivery: bool | None = None,
):
    return {
        "place_id": place_id,
        "name": place_id,
        "evidence": {
            "product_query": product,
            "status": "REPORTED_UNVERIFIED",
            "submission": {
                "product_name": "Test 65W charger",
                "stock_quantity": stock,
                "price_minor": price * 100,
                "currency": "INR",
                "delivery_available": delivery,
                "submitted_at": (
                    NOW - timedelta(minutes=minutes_old)
                ).isoformat(),
            },
            "assessment": (
                {
                    "status": "REPORTED_UNVERIFIED",
                    "freshness": "RECENT_REPORT",
                    "eligible_for_commitment": False,
                }
                if assessment else None
            ),
        },
    }


def run(merchants, *, budget=1000, quantity=1,
        delivery_required=False):
    payload = ReplanInput.model_validate({
        "customer": {
            "product_query": "65W USB-C PD laptop charger",
            "budget_minor": budget * 100,
            "required_quantity": quantity,
            "delivery_required": delivery_required,
        },
        "merchants": merchants,
    })

    return evaluate_replan(payload, now=NOW)


def test_selects_lowest_preliminary_quote():
    result = run([
        merchant("TEST_A", 899, 3),
        merchant("TEST_B", 950, 5),
    ])

    assert result["selected"]["place_id"] == "TEST_A"
    assert result["decision_status"] == "PROVISIONAL_OFFER_FOUND"
    assert result["purchase_allowed"] is False


def test_stock_out_switches_to_next_store():
    result = run([
        merchant("TEST_A", 899, 0),
        merchant("TEST_B", 950, 5),
    ])

    assert result["selected"]["place_id"] == "TEST_B"

    first = result["candidates"][0]
    assert first["status"] == "EXCLUDED"
    assert "REPORTED_STOCK_INSUFFICIENT" in first["reasons"]


def test_budget_blocks_all_offers():
    result = run([
        merchant("TEST_A", 899, 3),
        merchant("TEST_B", 950, 5),
    ], budget=850)

    assert result["selected"] is None
    assert result["decision_status"] == "NO_PROVISIONAL_OFFER"
    assert all(
        "ITEM_SUBTOTAL_EXCEEDS_BUDGET" in item["reasons"]
        for item in result["candidates"]
    )


def test_stale_report_cannot_be_selected():
    result = run([
        merchant("TEST_A", 700, 3, minutes_old=180),
        merchant("TEST_B", 950, 5),
    ])

    assert result["selected"]["place_id"] == "TEST_B"
    assert "STALE_SUBMISSION" in result["candidates"][0]["reasons"]


def test_missing_assessment_needs_review():
    result = run([
        merchant("TEST_A", 899, 3, assessment=False),
    ])

    assert result["selected"] is None
    assert result["candidates"][0]["status"] == "NEEDS_REVIEW"


def test_quantity_affects_subtotal_and_stock():
    result = run([
        merchant("TEST_A", 400, 1),
        merchant("TEST_B", 450, 3),
    ], quantity=2)

    assert result["selected"]["place_id"] == "TEST_B"
    assert result["selected"]["reported_subtotal_minor"] == 90000


def test_delivery_reported_unavailable_is_excluded():
    result = run([
        merchant("TEST_A", 899, 3, delivery=False),
        merchant("TEST_B", 950, 5, delivery=True),
    ], delivery_required=True)

    assert result["selected"]["place_id"] == "TEST_B"
    assert "DELIVERY_REPORTED_UNAVAILABLE" in (
        result["candidates"][0]["reasons"]
    )


def test_different_product_is_not_compared():
    result = run([
        merchant("TEST_A", 400, 3, product="Wireless mouse"),
        merchant("TEST_B", 950, 5),
    ])

    assert result["selected"]["place_id"] == "TEST_B"
    assert "PRODUCT_REQUEST_MISMATCH" in (
        result["candidates"][0]["reasons"]
    )


def test_missing_response_never_becomes_offer():
    result = run([
        {"place_id": "TEST_A", "name": "Test A", "evidence": None}
    ])

    assert result["selected"] is None
    assert result["candidates"][0]["status"] == "AWAITING_EVIDENCE"


def test_endpoint_and_validation():
    app.dependency_overrides[local_only] = lambda: None

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/journey/replan",
                json={
                    "customer": {
                        "product_query": "65W USB-C PD laptop charger",
                        "budget_minor": 100000,
                        "required_quantity": 1,
                    },
                    "merchants": [],
                },
            )

            assert response.status_code == 200
            assert response.json()["selected"] is None

            invalid = client.post(
                "/api/journey/replan",
                json={
                    "customer": {
                        "product_query": "charger",
                        "required_quantity": 0,
                    },
                    "merchants": [],
                },
            )

            assert invalid.status_code == 422
    finally:
        app.dependency_overrides.pop(local_only, None)
