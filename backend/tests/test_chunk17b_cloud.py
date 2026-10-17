"""Local TestClient tests. Firebase verification SDK stubbed; no real model calls."""
import os
import sys
import types
from fastapi.testclient import TestClient
import pytest

os.environ.setdefault('FIREBASE_PROJECT_ID','test-only-project')
os.environ.setdefault('FIREBASE_WEB_APP_ID','1:000:web:test-only')

from app import cloud_decision_api as cloud
from app.main import app as legacy_app
from app.schemas.intent import ExtractedIntent,IntentAnalysisResponse
from app.services.intent_service import IntentOutputError

PATH='/api/v1/ai/intent/extract'
BODY={'text':'Need 65W USB-C charger under ₹1000 in Thane today'}
HEADER={'Authorization':'Bearer TEST_ID_ONLY','X-Firebase-AppCheck':'TEST_APP_ONLY'}


@pytest.fixture
def trusted_stub(monkeypatch):
    calls=[]
    sdk=types.ModuleType('firebase_admin')
    sdk.auth=types.SimpleNamespace(verify_id_token=lambda token,app=None:
                                   (calls.append('id') or {'uid':'offline-user'}))
    sdk.app_check=types.SimpleNamespace(verify_token=lambda token,app=None:
                                       (calls.append('appcheck') or {'app_id':'test-app'}))
    monkeypatch.setitem(sys.modules,'firebase_admin',sdk)
    monkeypatch.setattr(cloud,'_firebase_app',lambda:'fake-app')
    monkeypatch.setattr(cloud,'FIREBASE_WEB_APP_ID','test-app')
    return calls


@pytest.fixture
def fake_service(monkeypatch):
    calls=[]
    class Service:
        def extract(self,text):
            calls.append(text)
            return IntentAnalysisResponse(source='vertex_ai',model='offline-sdk-stub',
                status='extracted_unverified',processing_ms=1,
                intent=ExtractedIntent(language='English',
                    requested_product='USB-C charger',budget_amount=1000,
                    budget_currency='INR',compatibility_needs_verification=True))
    cloud.app.dependency_overrides[cloud.get_intent_service_17b]=lambda:Service()
    yield calls
    cloud.app.dependency_overrides.pop(cloud.get_intent_service_17b,None)


def test_unauthenticated_request_is_rejected_before_model(monkeypatch,fake_service):
    monkeypatch.setenv('NEEDPROOF_INTENT_17B_ENABLED','true')
    result=TestClient(cloud.app).post(PATH,json=BODY)
    assert result.status_code==401
    assert fake_service==[]


def test_auth_but_disabled_route_is_503(monkeypatch,trusted_stub,fake_service):
    monkeypatch.delenv('NEEDPROOF_INTENT_17B_ENABLED',raising=False)
    result=TestClient(cloud.app).post(PATH,json=BODY,headers=HEADER)
    assert result.status_code==503
    assert fake_service==[]
    assert trusted_stub==['id','appcheck']


def test_valid_stubbed_tokens_and_flag_enable_offline_route(monkeypatch,trusted_stub,fake_service):
    monkeypatch.setenv('NEEDPROOF_INTENT_17B_ENABLED','true')
    result=TestClient(cloud.app).post(PATH,json=BODY,headers=HEADER)
    assert result.status_code==200,result.text
    assert result.json()['status']=='extracted_unverified'
    assert result.headers['cache-control']=='no-store'
    assert fake_service==[BODY['text']]
    assert trusted_stub==['id','appcheck']


def test_wrong_appcheck_does_not_reach_model(monkeypatch,trusted_stub,fake_service):
    monkeypatch.setenv('NEEDPROOF_INTENT_17B_ENABLED','true')
    monkeypatch.setattr(cloud,'FIREBASE_WEB_APP_ID','wrong-app')
    result=TestClient(cloud.app).post(PATH,json=BODY,headers=HEADER)
    assert result.status_code==401
    assert fake_service==[]


def test_invalid_body_rejected(monkeypatch,trusted_stub,fake_service):
    monkeypatch.setenv('NEEDPROOF_INTENT_17B_ENABLED','true')
    result=TestClient(cloud.app).post(PATH,json={'text':'x'},headers=HEADER)
    assert result.status_code==422
    assert fake_service==[]


def test_output_failure_stays_502(monkeypatch,trusted_stub):
    monkeypatch.setenv('NEEDPROOF_INTENT_17B_ENABLED','true')
    class Fail:
        def extract(self,text):raise IntentOutputError('Unsafe model JSON')
    cloud.app.dependency_overrides[cloud.get_intent_service_17b]=lambda:Fail()
    try:
        result=TestClient(cloud.app).post(PATH,json=BODY,headers=HEADER)
        assert result.status_code==502
    finally:
        cloud.app.dependency_overrides.pop(cloud.get_intent_service_17b,None)


def test_legacy_main_app_denies_public_paid_route_in_production(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT','production')
    result=TestClient(legacy_app).post('/api/intent/extract',json=BODY)
    assert result.status_code==403
