"""All tests use mocked Gemini: no network, cloud, credentials or live model."""
from types import SimpleNamespace
import json

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas.intent import ExtractedIntent
from app.services.intent_service import (
    IntentService, IntentModelError, IntentOutputError, IntentConfigurationError,
)

REQUEST = 'Need 65W USB-C PD charger under ₹1000 in Thane today'


def example(**overrides):
    source = dict(language='English', product_category='electronics',
                  requested_product='USB-C PD charger',budget_amount=1000,
                  budget_currency='INR', delivery_location='Thane',
                  delivery_deadline_text='today',
                  required_specifications=['65W','USB-C PD'], preferred_specifications=[],
                  missing_information=['Exact laptop model'],
                  clarification_questions=['What is your laptop model?'],
                  compatibility_needs_verification=True)
    source.update(overrides)
    return source


def run(monkeypatch, payload, query=REQUEST, error=None, as_text=False):
    calls=[]
    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            if error: raise RuntimeError('PRIVATE_REQUEST_TEXT_MUST_NOT_BE_LOGGED')
            return SimpleNamespace(parsed=None if as_text else payload,
                  text=json.dumps(payload,ensure_ascii=False) if as_text else None,
                  usage_metadata=SimpleNamespace(prompt_token_count=13,candidates_token_count=20))
    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs['vertexai'] is True
            self.models=FakeModels()
        def close(self): pass
    monkeypatch.setattr('app.services.intent_service.genai.Client',FakeClient)
    settings=Settings(_env_file=None,ai_mode='LIVE_VERTEX',
                      google_cloud_project='offline-project',gemini_model='mock-model')
    service=IntentService(settings)
    return service, calls


def test_new_intent_structured_and_unverified(monkeypatch):
    service,calls=run(monkeypatch,example())
    result=service.extract(REQUEST)
    assert result.intent.budget_amount==1000
    assert result.status=='extracted_unverified'
    assert result.intent.compatibility_needs_verification is True
    assert result.usage.input_tokens==13
    assert len(calls)==1 and calls[0]['config'].max_output_tokens==1200


def test_fallback_json_path(monkeypatch):
    service,_=run(monkeypatch,example(),as_text=True)
    assert service.extract(REQUEST).intent.delivery_location=='Thane'


@pytest.mark.parametrize('alter',[
    {'budget_amount': 9999},
    {'budget_currency':'USD'},
    {'delivery_location':'Mumbai'},
    {'required_specifications':['140W USB-C PD']},
])
def test_unsupported_claim_rejected(monkeypatch,alter):
    service,_=run(monkeypatch,example(**alter))
    with pytest.raises(IntentOutputError): service.extract(REQUEST)


def test_no_currency_inference_from_wattage(monkeypatch):
    request='Need a 65W USB-C charger near Thane'
    service,_=run(monkeypatch,example(budget_amount=None,budget_currency='INR'),query=request)
    with pytest.raises(IntentOutputError):service.extract(request)


def test_hindi_marathi_unicode_and_original_location(monkeypatch):
    query='मला ठाणे येथे 65W USB-C चार्जर 1000 रुपये मध्ये पाहिजे'
    intent=example(language='Marathi',delivery_location='ठाणे',
                  budget_currency='INR',budget_amount=1000)
    service,_=run(monkeypatch,intent,query=query)
    assert service.extract(query).intent.delivery_location=='ठाणे'


def test_non_existent_compatibility_proof_never_promoted(monkeypatch):
    service,_=run(monkeypatch,example(compatibility_needs_verification=False,
                                    missing_information=[],clarification_questions=[]))
    result=service.extract(REQUEST)
    assert result.intent.compatibility_needs_verification
    assert result.intent.clarification_questions


def test_model_failure_redacts_sensitive_exception(monkeypatch,caplog):
    service,_=run(monkeypatch,example(),error=True)
    with pytest.raises(IntentModelError): service.extract(REQUEST)
    assert 'PRIVATE_REQUEST_TEXT_MUST_NOT_BE_LOGGED' not in caplog.text


def test_empty_model_output_is_not_success(monkeypatch):
    service,_=run(monkeypatch,example())
    def fake(): return SimpleNamespace(parsed=None,text=None,usage_metadata=None)
    class FakeClient:
        models=SimpleNamespace(generate_content=lambda **kw: fake())
        def __init__(self,**kw):pass
        def close(self):pass
    monkeypatch.setattr('app.services.intent_service.genai.Client',FakeClient)
    with pytest.raises(IntentOutputError):service.extract(REQUEST)


def test_structured_validation_does_not_accept_empty_product():
    with pytest.raises(ValidationError):ExtractedIntent.model_validate(example(requested_product=''))


def test_wrong_mode_is_denied_without_model_call():
    service=IntentService(Settings(_env_file=None,google_cloud_project='mock',ai_mode='OFFLINE'))
    with pytest.raises(IntentConfigurationError): service.extract(REQUEST)
