"""Run: cd backend && python -m pytest -q tests/test_cloud_decision_api.py"""
import os

# Cloud variables set before importing module; no live Firebase calls in tests.
os.environ.setdefault("FIREBASE_PROJECT_ID", "test-firebase-project")
os.environ.setdefault("FIREBASE_WEB_APP_ID", "1:000:web:test")
os.environ.setdefault("ALLOWED_ORIGINS", "https://needproof-ai-showcase.web.app")

from fastapi.testclient import TestClient
from app.cloud_decision_api import app, require_firebase_client

client = TestClient(app)


def snapshot(stock_a: int):
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()

    def merchant(name: str, stock: int, price_minor: int):
        return {
            "place_id": name,
            "name": name,
            "evidence": {
                "product_query": "65W USB-C PD laptop charger",
                "status": "REPORTED_UNVERIFIED",
                "submission": {
                    "product_name": "65W USB-C PD laptop charger",
                    "stock_quantity": stock,
                    "price_minor": price_minor,
                    "currency": "INR",
                    "delivery_available": True,
                    "submitted_at": timestamp,
                },
                "assessment": {
                    "status": "REPORTED_UNVERIFIED",
                    "freshness": "RECENT_REPORT",
                    "eligible_for_commitment": False,
                },
            },
        }

    return {
        "customer": {
            "product_query": "65W USB-C PD laptop charger",
            "budget_minor": 100000,
            "required_quantity": 1,
            "delivery_required": True,
        },
        "merchants": [
            merchant("TEST_STORE_A", stock_a, 89900),
            merchant("TEST_STORE_B", 5, 95000),
        ],
    }


def test_authentication_is_required():
    assert client.post("/api/v1/decision/replan", json=snapshot(3)).status_code == 401
    assert client.post("/api/v1/decision/verification-plan", json={}).status_code == 401
    assert client.get("/api/health").status_code == 404
    assert client.get("/health").status_code == 200


def test_correct_server_side_replanning():
    app.dependency_overrides[require_firebase_client] = lambda: "test-uid"
    try:
        initial = client.post("/api/v1/decision/replan", json=snapshot(3))
        assert initial.status_code == 200, initial.text
        data = initial.json()
        assert data["selected"]["place_id"] == "TEST_STORE_A"
        assert data["purchase_allowed"] is False
        updated = client.post("/api/v1/decision/replan", json=snapshot(0))
        assert updated.status_code == 200, updated.text
        data = updated.json()
        assert data["selected"]["place_id"] == "TEST_STORE_B"
        assert "REPORTED_STOCK_INSUFFICIENT" in data["candidates"][0]["reasons"]
        planning = client.post("/api/v1/decision/verification-plan", json={})
        assert planning.status_code == 200, planning.text
        assert "recommended_action_id" in planning.json()
    finally:
        app.dependency_overrides.clear()


def test_rejects_duplicate_merchants():
    app.dependency_overrides[require_firebase_client] = lambda: "test-uid"
    try:
        request = snapshot(3)
        request["merchants"].append(request["merchants"][0])
        assert client.post("/api/v1/decision/replan", json=request).status_code == 422
    finally:
        app.dependency_overrides.clear()
