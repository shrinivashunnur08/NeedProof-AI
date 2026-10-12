
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_request_preview():
    response = client.post(
        "/api/requests/preview",
        json={
            "text": "Need a 65W USB-C laptop charger under ₹1000"
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted_preview"


def test_short_request_is_rejected():
    response = client.post(
        "/api/requests/preview",
        json={"text": "Hi"},
    )

    assert response.status_code == 422
