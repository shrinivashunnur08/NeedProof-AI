
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.merchant_onboarding import local_only
from app.db.models import (
    Base,
    SimulationOrder,
    utc_now,
)
from app.db.session import get_db
from app.main import app


BASE_URL = "/api/transactions/simulation"

NORMAL = {
    "budget_inr": 1800,
    "deadline_minutes": 60,
    "max_merchants": 2,
    "ttl_seconds": 120,
}


@pytest.fixture
def sandbox():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[local_only] = lambda: None

    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def reserve(client, key="test-reservation-key-0001", **changes):
    return client.post(
        f"{BASE_URL}/reserve",
        headers={"Idempotency-Key": key},
        json={**NORMAL, **changes},
    )


def available(client, sku):
    response = client.get(f"{BASE_URL}/inventory")
    assert response.status_code == 200

    for item in response.json()["items"]:
        if item["sku"] == sku:
            return item["available_quantity"]

    raise AssertionError(f"Missing inventory SKU {sku}")


def test_reservation_deducts_synthetic_inventory(sandbox):
    client, _ = sandbox

    before = available(client, "CHG-A")
    result = reserve(client)

    assert result.status_code == 201, result.text

    order = result.json()

    assert order["status"] == "RESERVED"
    assert order["plan"]["totals"]["total_minor"] == 156000
    assert order["payment_executed"] is False
    assert order["real_merchant_inventory_reserved"] is False

    assert available(client, "CHG-A") == before - 1
    assert len(order["events"]) == 1


def test_idempotency_prevents_double_reservation(sandbox):
    client, _ = sandbox

    first = reserve(client, "same-idempotency-key-001")
    stock_after_first = available(client, "CHG-A")

    second = reserve(client, "same-idempotency-key-001")

    assert first.status_code == 201
    assert second.status_code == 201

    assert (
        first.json()["order_id"]
        == second.json()["order_id"]
    )

    assert available(client, "CHG-A") == stock_after_first
    assert len(second.json()["events"]) == 1

    changed = reserve(
        client,
        "same-idempotency-key-001",
        budget_inr=2000,
    )

    assert changed.status_code == 409


def test_commit_cannot_execute_twice(sandbox):
    client, _ = sandbox

    order_id = reserve(client).json()["order_id"]

    first = client.post(
        f"{BASE_URL}/orders/{order_id}/commit"
    )
    second = client.post(
        f"{BASE_URL}/orders/{order_id}/commit"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "COMMITTED_SIMULATED"

    # One reservation event, one commit event.
    assert len(second.json()["events"]) == 2

    cannot_cancel = client.post(
        f"{BASE_URL}/orders/{order_id}/cancel"
    )

    assert cannot_cancel.status_code == 409


def test_cancel_returns_inventory(sandbox):
    client, _ = sandbox

    before = available(client, "CBL-B")
    order_id = reserve(client).json()["order_id"]

    assert available(client, "CBL-B") == before - 1

    cancelled = client.post(
        f"{BASE_URL}/orders/{order_id}/cancel"
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    assert available(client, "CBL-B") == before

    repeated = client.post(
        f"{BASE_URL}/orders/{order_id}/cancel"
    )

    assert repeated.status_code == 200
    assert len(repeated.json()["events"]) == 2

    cannot_commit = client.post(
        f"{BASE_URL}/orders/{order_id}/commit"
    )

    assert cannot_commit.status_code == 409


def test_expiration_restores_inventory(sandbox):
    client, factory = sandbox

    before = available(client, "MOU-B")
    order_id = reserve(client).json()["order_id"]

    with factory() as db:
        order = db.get(SimulationOrder, order_id)
        order.expires_at = utc_now() - timedelta(
            seconds=1
        )
        db.commit()

    # Reading the order triggers lazy expiration.
    expired = client.get(
        f"{BASE_URL}/orders/{order_id}"
    )

    assert expired.status_code == 200
    assert expired.json()["status"] == "EXPIRED"

    assert available(client, "MOU-B") == before

    commit = client.post(
        f"{BASE_URL}/orders/{order_id}/commit"
    )

    assert commit.status_code == 409


def test_insufficient_stock_does_not_go_negative(sandbox):
    client, _ = sandbox

    # Every reservation uses the same 3 default SKUs.
    # Each begins with 5 synthetic available units.
    for index in range(5):
        result = reserve(
            client,
            key=f"stock-contention-test-{index:04d}",
        )
        assert result.status_code == 201, result.text

    assert available(client, "CHG-A") == 0

    sixth = reserve(
        client,
        key="stock-contention-test-0006",
    )

    assert sixth.status_code == 409
    assert available(client, "CHG-A") == 0


def test_infeasible_basket_creates_no_reservation(sandbox):
    client, _ = sandbox

    before = available(client, "CHG-A")

    result = reserve(
        client,
        budget_inr=1559,
    )

    assert result.status_code == 422
    assert available(client, "CHG-A") == before


def test_missing_idempotency_key_is_rejected(sandbox):
    client, _ = sandbox

    result = client.post(
        f"{BASE_URL}/reserve",
        json=NORMAL,
    )

    assert result.status_code == 422
