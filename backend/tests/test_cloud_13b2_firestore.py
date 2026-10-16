"""Fail-closed Firestore evidence adapter checks; no Google credentials required."""
from datetime import datetime, timezone
from types import SimpleNamespace
from fastapi import HTTPException
import pytest
from app.evidence_firestore_13b2 import PROJECT, _hash, _serialize, feature_gate, _decision


def test_storage_disabled_by_default(monkeypatch):
    monkeypatch.delenv('MERCHANT_EVIDENCE_ENABLED', raising=False)
    with pytest.raises(HTTPException) as exc:
        feature_gate()
    assert exc.value.status_code == 503


def test_storage_requires_matching_project(monkeypatch):
    monkeypatch.setenv('MERCHANT_EVIDENCE_ENABLED', 'true')
    monkeypatch.setenv('MERCHANT_EVIDENCE_STORAGE', 'firestore')
    monkeypatch.setenv('MERCHANT_EVIDENCE_FIRESTORE_PROJECT', PROJECT)
    monkeypatch.setenv('FIREBASE_PROJECT_ID', 'wrong-project')
    with pytest.raises(HTTPException) as exc:
        feature_gate()
    assert exc.value.status_code == 503
    monkeypatch.setenv('FIREBASE_PROJECT_ID', PROJECT)
    feature_gate()


def test_revision_provenance_and_identity_not_exposed():
    data = {"merchant_uid": "some-secret-user", "stock_quantity": 0, "price_minor": 95000,
            "specification_notes": "Unverified assertion", "delivery_available": False,
            "recorded_at": datetime.now(timezone.utc)}
    public = _serialize('rev-xyz', data)
    assert public['source'] == 'MERCHANT_REPORTED_UNVERIFIED'
    assert public['merchant_identity_independently_verified'] is False
    assert 'merchant_uid' not in public


def test_stable_nonreversible_ids():
    assert _hash('uid', 'place') == _hash('uid', 'place')
    assert _hash('uid', 'place') != _hash('other', 'place')
    assert 'uid' not in _hash('uid', 'place')


def test_always_no_purchase_authorization():
    from app.merchant_evidence_13b import _decision
    inquiry = SimpleNamespace(place_id='places-123', product_query='65w usb charger', budget_minor=100000)
    replan = _decision(inquiry, None)
    assert replan['purchase_allowed'] is False
