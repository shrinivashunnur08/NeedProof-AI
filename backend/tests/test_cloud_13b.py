"""Regression, privacy and isolation tests for the gated 13B API."""

import pytest
from fastapi.testclient import TestClient
from fastapi.routing import iter_route_contexts
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.cloud_decision_api import app
from app.db.models import utc_now
from app.db.session import get_db
from app.merchant_evidence_13b import (
    EvidenceInquiry13B, EvidenceRevision13B, MerchantGrant13B,
    feature_gate, require_customer, require_merchant,
)


@pytest.fixture()
def api(monkeypatch):
    monkeypatch.setenv("MERCHANT_EVIDENCE_ENABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    from app.config import get_settings
    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    for table in [EvidenceInquiry13B.__table__, MerchantGrant13B.__table__, EvidenceRevision13B.__table__]:
        table.create(bind=engine)
    user = {"uid": "customer-alpha"}

    def db_override():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_customer] = lambda: user["uid"]
    app.dependency_overrides[require_merchant] = lambda: user["uid"]
    with TestClient(app) as client:
        yield client, user, engine
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def test_route_contract_and_legacy_routes_remain():
    routes = {
    (r.path, method)
    for r in iter_route_contexts(app.routes)
    for method in getattr(r, "methods", set())
}
    for method, path in [
        ("POST", "/api/v1/discovery/stores"),
        ("POST", "/api/v1/decision/replan"),
        ("POST", "/api/v1/decision/verification-plan"),
        ("POST", "/api/v1/evidence/inquiries"),
        ("GET", "/api/v1/evidence/inquiries/{inquiry_id}"),
        ("GET", "/api/v1/evidence/merchant/inquiries"),
        ("POST", "/api/v1/evidence/merchant/inquiries/{inquiry_id}/reports"),
    ]:
        assert (path, method) in routes


def test_feature_flag_fails_closed(monkeypatch):
    monkeypatch.delenv("MERCHANT_EVIDENCE_ENABLED", raising=False)
    r = TestClient(app).post("/api/v1/evidence/inquiries", json={"place_id": "place-123", "product_query": "charger"})
    assert r.status_code == 503


def test_customer_ownership_and_unverified_history(api):
    client, user, engine = api
    payload = {"place_id": "places-abc", "product_query": "charger 65w", "budget_minor": 100_000}
    created = client.post("/api/v1/evidence/inquiries", json=payload)
    assert created.status_code == 201, created.text
    doc = created.json()
    inquiry_id = doc["inquiry_id"]
    assert doc["merchant_contacted"] is False
    assert doc["current_report"] is None
    assert doc["replanning"]["purchase_allowed"] is False
    assert client.post("/api/v1/evidence/inquiries", json=payload).status_code == 200  # duplicate guard
    user["uid"] = "customer-beta"
    assert client.get(f"/api/v1/evidence/inquiries/{inquiry_id}").status_code == 404
    user["uid"] = "unapproved-merchant"
    r = client.post(f"/api/v1/evidence/merchant/inquiries/{inquiry_id}/reports", json={"authorized_to_report": True, "stock_quantity": 3, "price_minor": 80000})
    assert r.status_code == 404
    with Session(engine) as db:
        db.add(MerchantGrant13B(merchant_uid="approved-merchant", place_id="places-abc", approval_status="OPERATOR_APPROVED_CLAIM", approved_at=utc_now()))
        db.commit()
    user["uid"] = "approved-merchant"
    inbox = client.get("/api/v1/evidence/merchant/inquiries")
    assert inbox.status_code == 200
    assert len(inbox.json()["inquiries"]) == 1
    for stock, expected in [(3, "PROVISIONAL"), (0, "EXCLUDED")]:
        updated = client.post(f"/api/v1/evidence/merchant/inquiries/{inquiry_id}/reports", json={"authorized_to_report": True, "stock_quantity": stock, "price_minor": 80000, "specification_notes": "model mentioned", "delivery_available": True})
        assert updated.status_code == 201, updated.text
        doc = updated.json()
        assert doc["replanning"]["candidates"][0]["status"] == expected
        assert doc["replanning"]["purchase_allowed"] is False
        assert doc["current_report"]["source"] == "MERCHANT_REPORTED_UNVERIFIED"
    user["uid"] = "customer-alpha"
    fetched = client.get(f"/api/v1/evidence/inquiries/{inquiry_id}")
    assert fetched.status_code == 200
    assert [r["stock_quantity"] for r in fetched.json()["history"]] == [0, 3]
    assert "requester_uid" not in fetched.text
    assert "merchant_uid" not in fetched.text


def test_merchant_cannot_see_other_place_inquiries(api):
    client, user, engine = api
    inquiry = client.post("/api/v1/evidence/inquiries", json={"place_id": "places-XYZ", "product_query": "usb adapter"}).json()
    with Session(engine) as db:
        db.add(MerchantGrant13B(merchant_uid="merchant-beta", place_id="another-place", approval_status="OPERATOR_APPROVED_CLAIM", approved_at=utc_now()))
        db.commit()
    user["uid"] = "merchant-beta"
    assert client.get("/api/v1/evidence/merchant/inquiries").json()["inquiries"] == []
    assert client.post(f"/api/v1/evidence/merchant/inquiries/{inquiry['inquiry_id']}/reports", json={"stock_quantity": 0, "authorized_to_report": True}).status_code == 404


def test_cloud_run_refuses_ephemeral_database(monkeypatch):
    monkeypatch.setenv("MERCHANT_EVIDENCE_ENABLED", "true")
    monkeypatch.setenv("K_SERVICE", "needproof-decision-api")
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.merchant_evidence_13b import feature_gate
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exception:
        feature_gate()
    assert exception.value.status_code == 503
    get_settings.cache_clear()
