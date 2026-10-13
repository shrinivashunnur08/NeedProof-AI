
from fastapi.testclient import TestClient

from app.main import app
from app.api.intent import get_intent_service
from app.schemas.intent import (
    ExtractedIntent,
    IntentAnalysisResponse,
)
from app.services.intent_service import IntentModelError

client = TestClient(app)


class FakeIntentService:
    def extract(self, text: str):
        return IntentAnalysisResponse(
            source="vertex_ai",
            model="test-model",
            status="extracted_unverified",
            processing_ms=20,
            intent=ExtractedIntent(
                language="English",
                product_category="Electronics",
                requested_product="USB-C laptop charger",
                budget_amount=1000,
                budget_currency="INR",
                delivery_deadline_text="before 6 PM",
                delivery_location=None,
                required_specifications=[
                    "65W",
                    "USB-C PD",
                ],
                preferred_specifications=[],
                missing_information=[
                    "Laptop model not provided"
                ],
                clarification_questions=[
                    "What is your laptop model?"
                ],
                compatibility_needs_verification=True,
            ),
        )


def test_extract_intent_success():
    app.dependency_overrides[get_intent_service] = (
        lambda: FakeIntentService()
    )

    try:
        response = client.post(
            "/api/intent/extract",
            json={
                "text": (
                    "Need a 65W USB-C PD charger "
                    "under ₹1000 before 6 PM"
                )
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["source"] == "vertex_ai"
        assert data["intent"]["budget_amount"] == 1000
        assert data["intent"]["budget_currency"] == "INR"
        assert "65W" in data["intent"]["required_specifications"]
        assert data["intent"]["compatibility_needs_verification"]

    finally:
        app.dependency_overrides.clear()


def test_reject_empty_customer_request():
    response = client.post(
        "/api/intent/extract",
        json={"text": "   "},
    )

    assert response.status_code == 422


def test_reject_excessively_long_request():
    response = client.post(
        "/api/intent/extract",
        json={"text": "A" * 2500},
    )

    assert response.status_code == 422


def test_gemini_failure_is_not_disguised_as_success():
    class FailingService:
        def extract(self, text):
            raise IntentModelError("Gemini unavailable")

    app.dependency_overrides[get_intent_service] = (
        lambda: FailingService()
    )

    try:
        response = client.post(
            "/api/intent/extract",
            json={"text": "Need a laptop charger today"},
        )

        assert response.status_code == 502
        assert "Gemini unavailable" in response.json()["detail"]

    finally:
        app.dependency_overrides.clear()
