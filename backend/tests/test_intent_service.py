
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.services.intent_service import (
    IntentService,
    IntentConfigurationError,
)
from app.schemas.intent import ExtractedIntent


def test_missing_project_is_rejected():
    settings = Settings(
        _env_file=None,
        google_cloud_project="",
        ai_mode="LIVE_VERTEX",
    )

    service = IntentService(settings)

    with pytest.raises(IntentConfigurationError):
        service.extract("Need a USB-C laptop charger today")


def test_structured_gemini_result_is_validated(monkeypatch):
    intent = ExtractedIntent(
        language="English",
        product_category="Electronics",
        requested_product="Laptop charger",
        budget_amount=1000,
        budget_currency="INR",
        delivery_deadline_text="today",
        required_specifications=["65W", "USB-C PD"],
        preferred_specifications=[],
        missing_information=["Laptop model"],
        clarification_questions=["What is the laptop model?"],
        compatibility_needs_verification=True,
    )

    class FakeResponse:
        parsed = intent
        text = None
        usage_metadata = SimpleNamespace(
            prompt_token_count=40,
            candidates_token_count=20,
        )

    class FakeModels:
        def generate_content(self, **kwargs):
            assert kwargs["model"] == "test-gemini"
            return FakeResponse()

    class FakeGenAIClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

        def close(self):
            pass

    monkeypatch.setattr(
        "app.services.intent_service.genai.Client",
        FakeGenAIClient,
    )

    settings = Settings(
        _env_file=None,
        google_cloud_project="test-project",
        gemini_model="test-gemini",
        ai_mode="LIVE_VERTEX",
    )

    result = IntentService(settings).extract(
        "Need 65W charger under ₹1000 today"
    )

    assert result.source == "vertex_ai"
    assert result.intent.budget_amount == 1000
    assert result.intent.required_specifications == [
        "65W",
        "USB-C PD",
    ]
    assert result.usage is not None
    assert result.usage.input_tokens == 40
