"""16B: Real auth dependency code path with controlled SDK responses.

This is an OFFLINE identity-contract test. Firebase Admin SDK responses are mocked;
no Firebase Auth, App Check, Firestore, Cloud Run or merchant endpoints are used.
"""
from __future__ import annotations

import logging
import sys
import types
from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import cloud_decision_api as api

DEMO = {"scenario": "reported_offer", "simulation_acknowledged": True}


@dataclass
class StubVerify:
    user: dict | None = None
    app: dict | None = None
    auth_raises: bool = False
    app_raises: bool = False

    def install(self, monkeypatch):
        """Exercise the production verification *function* without SDK network I/O."""
        self.calls = []
        outer = self

        def verify_user(token, app=None):
            outer.calls.append(("auth", token, app))
            if outer.auth_raises:
                raise ValueError("invalid ID token")
            return outer.user or {"uid": "offline-user"}

        def verify_app(token, app=None):
            outer.calls.append(("appcheck", token, app))
            if outer.app_raises:
                raise ValueError("invalid App Check")
            return outer.app if outer.app is not None else {"app_id": "1:000:web:offline"}

        sdk = types.ModuleType("firebase_admin")
        sdk.auth = types.SimpleNamespace(verify_id_token=verify_user)
        sdk.app_check = types.SimpleNamespace(verify_token=verify_app)
        monkeypatch.setitem(sys.modules, "firebase_admin", sdk)
        monkeypatch.setattr(api, "_firebase_app", lambda: "offline-sdk-app")
        monkeypatch.setattr(api, "FIREBASE_WEB_APP_ID", "1:000:web:offline")
        return self


def guarded_call():
    return api.require_firebase_client("Bearer FAKE_ID_ONLY_FOR_TESTS", "FAKE_APP_CHECK_ONLY_FOR_TESTS")


def status_of(call):
    with pytest.raises(HTTPException) as exc:
        call()
    return exc.value.status_code


@pytest.mark.parametrize("auth,appcheck", [
    (None, None),
    ("Bearer token", None),
    (None, "appcheck-token"),
    ("token-without-bearer", "appcheck-token"),
    ("bearer token", "appcheck-token"),
])
def test_missing_or_malformed_header_fails_before_sdk(auth, appcheck):
    assert status_of(lambda: api.require_firebase_client(auth, appcheck)) == 401


def test_valid_auth_and_matching_appcheck_required(monkeypatch):
    fake = StubVerify().install(monkeypatch)
    assert guarded_call() == "offline-user"
    assert [call[0] for call in fake.calls] == ["auth", "appcheck"]
    assert all(call[2] == "offline-sdk-app" for call in fake.calls)


def test_wrong_app_id_fails_closed(monkeypatch):
    StubVerify(app={"app_id": "other-web-app"}).install(monkeypatch)
    assert status_of(guarded_call) == 401


@pytest.mark.parametrize("uid", [None, "", 3, [], {}])
def test_missing_or_invalid_firebase_uid_fails_closed(monkeypatch, uid):
    StubVerify(user={"uid": uid}).install(monkeypatch)
    assert status_of(guarded_call) == 401


@pytest.mark.parametrize("which", ["auth_raises", "app_raises"])
def test_rejected_sdk_token_fails_closed(monkeypatch, which):
    fake = StubVerify()
    setattr(fake, which, True)
    fake.install(monkeypatch)
    assert status_of(guarded_call) == 401


def test_no_tokens_written_to_security_log(monkeypatch, caplog):
    StubVerify(auth_raises=True).install(monkeypatch)
    with caplog.at_level(logging.WARNING):
        assert status_of(guarded_call) == 401
    assert "FAKE_ID_ONLY_FOR_TESTS" not in caplog.text
    assert "FAKE_APP_CHECK_ONLY_FOR_TESTS" not in caplog.text


def test_route_uses_real_auth_dependency_without_overrides(monkeypatch):
    assert not api.app.dependency_overrides, "Tests must not bypass the Firebase dependency"
    monkeypatch.setenv("GUIDED_JOURNEY_16A_ENABLED", "true")
    fake = StubVerify().install(monkeypatch)
    response = TestClient(api.app).post(
        "/api/v1/demo/guided-journey", json=DEMO,
        headers={"Authorization": "Bearer FAKE_ID_ONLY_FOR_TESTS",
                 "X-Firebase-AppCheck": "FAKE_APP_CHECK_ONLY_FOR_TESTS"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["purchase_allowed"] is False
    assert result["stock_independently_verified"] is False
    assert result["real_merchant_contact"] is False
    assert response.headers["cache-control"] == "no-store"
    assert len(fake.calls) == 2


def test_route_denies_wrong_app_check_without_override(monkeypatch):
    assert not api.app.dependency_overrides
    monkeypatch.setenv("GUIDED_JOURNEY_16A_ENABLED", "true")
    StubVerify(app={"app_id": "another-firebase-app"}).install(monkeypatch)
    response = TestClient(api.app).post(
        "/api/v1/demo/guided-journey", json=DEMO,
        headers={"Authorization": "Bearer fake", "X-Firebase-AppCheck": "fake"},
    )
    assert response.status_code == 401
    assert response.headers.get("cache-control") == "no-store"


def test_route_disabled_by_default_even_with_test_verified_identity(monkeypatch):
    assert not api.app.dependency_overrides
    monkeypatch.delenv("GUIDED_JOURNEY_16A_ENABLED", raising=False)
    StubVerify().install(monkeypatch)
    response = TestClient(api.app).post(
        "/api/v1/demo/guided-journey", json=DEMO,
        headers={"Authorization": "Bearer fake", "X-Firebase-AppCheck": "fake"},
    )
    assert response.status_code == 503


def test_cross_project_firestore_gate_fails_closed(monkeypatch):
    from app.evidence_firestore_13b2 import feature_gate, PROJECT
    monkeypatch.setenv("MERCHANT_EVIDENCE_ENABLED", "true")
    monkeypatch.setenv("MERCHANT_EVIDENCE_STORAGE", "firestore")
    monkeypatch.setenv("MERCHANT_EVIDENCE_FIRESTORE_PROJECT", PROJECT)
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "some-other-firebase-project")
    assert status_of(feature_gate) == 503


def test_merchant_feature_disabled_by_default(monkeypatch):
    from app.evidence_firestore_13b2 import feature_gate
    monkeypatch.delenv("MERCHANT_EVIDENCE_ENABLED", raising=False)
    assert status_of(feature_gate) == 503
