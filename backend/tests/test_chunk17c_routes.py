"""Protected cloud and explicitly local-only dev route acceptance."""
from fastapi.testclient import TestClient

from app.cloud_decision_api import app as cloud, require_firebase_client
from app.main import app as local


def data(**changes):
    return {
        "product_query":"65W USB-C PD charger","budget_inr":1000,
        "reported_price_inr":720,"location_note":"Thane",
        "simulated_report":"reported_offer","simulation_acknowledged":True,**changes,
    }


def test_cloud_unauthenticated_and_disabled(monkeypatch):
    monkeypatch.delenv("FRESH_JOURNEY_17C_ENABLED", raising=False)
    c=TestClient(cloud)
    assert c.post("/api/v1/demo/fresh-journey",json=data()).status_code==401
    cloud.dependency_overrides[require_firebase_client] = lambda: "only-test-user"
    try:
        assert c.post("/api/v1/demo/fresh-journey",json=data()).status_code==503
    finally:
        cloud.dependency_overrides.clear()


def test_cloud_enabled_only_with_test_identity_override(monkeypatch):
    monkeypatch.setenv("FRESH_JOURNEY_17C_ENABLED","true")
    cloud.dependency_overrides[require_firebase_client] = lambda: "only-test-user"
    try:
        c=TestClient(cloud)
        r=c.post("/api/v1/demo/fresh-journey",json=data(simulated_report="stockout"))
        assert r.status_code==200,r.text
        assert r.headers["cache-control"]=="no-store"
        assert r.json()["workflow"]["workflow_state"]=="MORE_EVIDENCE_NEEDED"
        assert r.json()["purchase_allowed"] is False
    finally:
        cloud.dependency_overrides.clear()


def test_local_off_by_default(monkeypatch):
    monkeypatch.delenv("NEEDPROOF_17C_LOCAL_ENABLED",raising=False)
    c=TestClient(local,client=("127.0.0.1",12345))
    assert c.post("/api/v1/demo/fresh-journey",json=data()).status_code==403


def test_local_loopback_with_flag(monkeypatch):
    monkeypatch.setenv("NEEDPROOF_17C_LOCAL_ENABLED","true")
    monkeypatch.setenv("ENVIRONMENT","development")
    c=TestClient(local,client=("127.0.0.1",12345))
    r=c.post("/api/v1/demo/fresh-journey",json=data())
    assert r.status_code==200,r.text
    assert r.json()["workflow"]["workflow_state"]=="PROVISIONAL_VERIFICATION_NEEDED"
    assert r.headers["cache-control"]=="no-store"


def test_local_remote_client_denied(monkeypatch):
    monkeypatch.setenv("NEEDPROOF_17C_LOCAL_ENABLED","true")
    monkeypatch.setenv("ENVIRONMENT","development")
    c=TestClient(local,client=("198.51.100.10",12345))
    assert c.post("/api/v1/demo/fresh-journey",json=data()).status_code==403


def test_local_production_denied(monkeypatch):
    monkeypatch.setenv("NEEDPROOF_17C_LOCAL_ENABLED","true")
    monkeypatch.setenv("ENVIRONMENT","production")
    c=TestClient(local,client=("127.0.0.1",12345))
    assert c.post("/api/v1/demo/fresh-journey",json=data()).status_code==403


def test_unknown_schema_and_no_purchase(monkeypatch):
    monkeypatch.setenv("FRESH_JOURNEY_17C_ENABLED","true")
    cloud.dependency_overrides[require_firebase_client]=lambda:"only-test-user"
    try:
        c=TestClient(cloud)
        assert c.post("/api/v1/demo/fresh-journey",json=data(merchant_identity_verified=True)).status_code==422
    finally:cloud.dependency_overrides.clear()
