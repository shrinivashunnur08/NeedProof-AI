
import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.verification import require_local_operator
from app.db.models import (
    Base,
    MerchantEvidenceSubmission,
    VerificationRequest,
    utc_now,
)
from app.db.session import get_db
from app.main import app


def setup_database():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_local_operator] = lambda: None

    return engine, factory


def add_report(
    factory,
    place_id,
    product_query,
    stock,
    price_minor,
    *,
    delivery=None,
):
    from datetime import timedelta

    token = "test-token-" + place_id + "-123456789012345"

    with factory() as db:
        record = VerificationRequest(
            place_id=place_id,
            product_query=product_query,
            invitation_hash=hashlib.sha256(
                token.encode()
            ).hexdigest(),
            status="REPORTED_UNVERIFIED",
            expires_at=utc_now() + timedelta(hours=24),
        )

        db.add(record)
        db.flush()

        db.add(
            MerchantEvidenceSubmission(
                request_id=record.id,
                product_name="Test USB-C Charger",
                stock_quantity=stock,
                price_minor=price_minor,
                currency="INR",
                specification_notes="Test USB-C PD 65W",
                delivery_available=delivery,
                evidence_status="MERCHANT_REPORTED_UNVERIFIED",
            )
        )

        request_id = record.id
        db.commit()

    return {
        "request_id": request_id,
        "invitation_token": token,
    }


def test_real_reported_advisory():
    engine, factory = setup_database()

    try:
        first = add_report(
            factory,
            "TEST_STORE_A",
            "65W USB-C PD charger",
            3,
            89900,
        )

        second = add_report(
            factory,
            "TEST_STORE_B",
            "65W USB-C PD charger",
            5,
            95000,
            delivery=True,
        )

        with TestClient(app) as client:
            response = client.post(
                "/api/optimization/reported-offers",
                json={
                    "budget_inr": 1000,
                    "quantity": 1,
                    "delivery_required": True,
                    "invitations": [first, second],
                },
            )

            assert response.status_code == 200

            data = response.json()

            assert data["mode"] == "REAL_REPORTED_ADVISORY"
            assert data["purchase_allowed"] is False
            assert data["total_including_fees_minor"] is None

            assert (
                data["selected"]["request_id"]
                == first["request_id"]
            )

            assert (
                data["selected"]["price_minor"]
                == 89900
            )

            assert len(data["alternatives"]) == 1

            # Tokens must never be returned.
            assert "invitation_token" not in response.text
            assert first["invitation_token"] not in response.text

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_invalid_invitation_token():
    engine, factory = setup_database()

    try:
        reference = add_report(
            factory, "TEST_C", "USB-C charger", 2, 85000
        )

        reference["invitation_token"] = (
            "incorrect-token-123456789012345"
        )

        with TestClient(app) as client:
            response = client.post(
                "/api/optimization/reported-offers",
                json={
                    "budget_inr": 1000,
                    "quantity": 1,
                    "invitations": [reference],
                },
            )

            assert response.status_code == 403

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_out_of_stock_report_is_excluded():
    engine, factory = setup_database()

    try:
        reference = add_report(
            factory, "TEST_D", "USB-C charger", 0, 70000
        )

        with TestClient(app) as client:
            response = client.post(
                "/api/optimization/reported-offers",
                json={
                    "budget_inr": 1000,
                    "quantity": 1,
                    "invitations": [reference],
                },
            )

            assert response.status_code == 200

            data = response.json()

            assert data["status"] == "NO_COMPARABLE_REPORTS"

            assert "REPORTED_STOCK_INSUFFICIENT" in (
                data["excluded"][0]["reasons"]
            )

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_mismatched_product_requests_are_excluded():
    engine, factory = setup_database()

    try:
        first = add_report(
            factory, "TEST_E", "USB-C charger", 2, 89900
        )

        second = add_report(
            factory, "TEST_F", "Wireless mouse", 2, 49900
        )

        with TestClient(app) as client:
            response = client.post(
                "/api/optimization/reported-offers",
                json={
                    "budget_inr": 1000,
                    "quantity": 1,
                    "invitations": [first, second],
                },
            )

            assert response.status_code == 200

            exclusions = response.json()["excluded"]

            assert "DIFFERENT_PRODUCT_REQUEST" in (
                exclusions[0]["reasons"]
            )

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_duplicate_request_ids_rejected():
    engine, factory = setup_database()

    try:
        reference = add_report(
            factory, "TEST_G", "USB-C charger", 2, 89900
        )

        with TestClient(app) as client:
            response = client.post(
                "/api/optimization/reported-offers",
                json={
                    "budget_inr": 1000,
                    "quantity": 1,
                    "invitations": [reference, reference],
                },
            )

            assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()
        engine.dispose()
