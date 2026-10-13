
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
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


def setup_test_database():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_local_operator] = lambda: None

    return engine, factory


def create_request(client):
    response = client.post(
        "/api/verification/invitations",
        json={
            "place_id": "TEST_PLACE_ID",
            "product_query": "65W USB-C PD charger",
        },
    )

    assert response.status_code == 201
    return response.json()


def test_invitation_and_merchant_response():
    engine, factory = setup_test_database()

    try:
        with TestClient(app) as client:
            invitation = create_request(client)

            request_id = invitation["request_id"]
            token = invitation["invitation_token"]

            headers = {"X-Verification-Token": token}

            # Unauthorized reading must be rejected.
            response = client.get(
                f"/api/verification/requests/{request_id}"
            )
            assert response.status_code == 401

            # Correct invitation token can read request.
            response = client.get(
                f"/api/verification/requests/{request_id}",
                headers=headers,
            )
            assert response.status_code == 200
            assert response.json()["status"] == "AWAITING_RESPONSE"

            # Submit fictional test product information.
            payload = {
                "product_name": "Test 65W Charger",
                "stock_quantity": 3,
                "price_minor": 89900,
                "specification_notes": "USB-C PD 65W",
                "delivery_available": None,
                "authorized_to_respond": True,
            }

            response = client.post(
                f"/api/verification/requests/{request_id}/respond",
                headers=headers,
                json=payload,
            )

            assert response.status_code == 200
            assert response.json()["status"] == "REPORTED_UNVERIFIED"

            # Same invitation cannot be submitted twice.
            response = client.post(
                f"/api/verification/requests/{request_id}/respond",
                headers=headers,
                json=payload,
            )
            assert response.status_code == 409

            response = client.get(
                f"/api/verification/requests/{request_id}",
                headers=headers,
            )

            data = response.json()

            assert data["submission"]["stock_quantity"] == 3
            assert data["submission"]["price_minor"] == 89900
            assert (
                data["submission"]["merchant_identity_verified"]
                is False
            )

        with factory() as db:
            requests = db.scalars(
                select(VerificationRequest)
            ).all()
            submissions = db.scalars(
                select(MerchantEvidenceSubmission)
            ).all()

            assert len(requests) == 1
            assert len(submissions) == 1

            # Only the token hash is persisted.
            assert requests[0].invitation_hash != token
            assert len(requests[0].invitation_hash) == 64

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_invalid_token_and_missing_price():
    engine, _ = setup_test_database()

    try:
        with TestClient(app) as client:
            invitation = create_request(client)
            request_id = invitation["request_id"]
            token = invitation["invitation_token"]

            response = client.get(
                f"/api/verification/requests/{request_id}",
                headers={"X-Verification-Token": "incorrect-token"},
            )

            assert response.status_code == 403

            response = client.post(
                f"/api/verification/requests/{request_id}/respond",
                headers={"X-Verification-Token": token},
                json={
                    "product_name": "Test Charger",
                    "stock_quantity": 3,
                    "price_minor": None,
                    "authorized_to_respond": True,
                },
            )

            assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_expired_invitation():
    engine, factory = setup_test_database()

    try:
        with TestClient(app) as client:
            invitation = create_request(client)
            request_id = invitation["request_id"]
            token = invitation["invitation_token"]

            with factory() as db:
                record = db.get(
                    VerificationRequest,
                    request_id,
                )
                assert record is not None

                record.expires_at = utc_now() - timedelta(hours=1)
                db.commit()

            headers = {"X-Verification-Token": token}

            response = client.get(
                f"/api/verification/requests/{request_id}",
                headers=headers,
            )

            assert response.status_code == 200
            assert response.json()["status"] == "EXPIRED"

            response = client.post(
                f"/api/verification/requests/{request_id}/respond",
                headers=headers,
                json={
                    "product_name": "Test Charger",
                    "stock_quantity": 1,
                    "price_minor": 85000,
                    "authorized_to_respond": True,
                },
            )

            assert response.status_code == 410

    finally:
        app.dependency_overrides.clear()
        engine.dispose()
