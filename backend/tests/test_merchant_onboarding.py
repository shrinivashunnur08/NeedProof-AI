
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.merchant_onboarding import local_only
from app.api.assurance import require_assurance_operator
from app.db.models import Base
from app.db.session import get_db
from app.main import app


def test_merchant_registration_login_and_claim():
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
        bind=engine, expire_on_commit=False
    )

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[local_only] = lambda: None
    app.dependency_overrides[
        require_assurance_operator
    ] = lambda: None

    try:
        with TestClient(app) as client:
            credentials = {
                "email": "Demo@Example.com",
                "password": "TestPassphrase!12345",
                "display_name": "Demo Merchant",
            }

            registration = client.post(
                "/api/onboarding/register",
                json=credentials,
            )

            assert registration.status_code == 201
            assert "password_hash" not in registration.text

            duplicate = client.post(
                "/api/onboarding/register",
                json=credentials,
            )
            assert duplicate.status_code == 409

            incorrect = client.post(
                "/api/onboarding/login",
                json={
                    "email": "demo@example.com",
                    "password": "incorrect-password",
                },
            )
            assert incorrect.status_code == 401

            login = client.post(
                "/api/onboarding/login",
                json={
                    "email": "demo@example.com",
                    "password": credentials["password"],
                },
            )

            assert login.status_code == 200

            token = login.json()["access_token"]
            auth = {"Authorization": f"Bearer {token}"}

            assert client.get(
                "/api/onboarding/me",
                headers=auth,
            ).status_code == 200

            assert client.get(
                "/api/onboarding/me",
            ).status_code == 401

            claim = client.post(
                "/api/onboarding/claims",
                headers=auth,
                json={"place_id": "TEST_STORE_A"},
            )

            assert claim.status_code == 201
            assert claim.json()["status"] == "PENDING_REVIEW"

            claim_id = claim.json()["id"]

            assert client.post(
                "/api/onboarding/claims",
                headers=auth,
                json={"place_id": "TEST_STORE_A"},
            ).status_code == 409

            queue = client.get(
                "/api/onboarding/operator/claims"
            )
            assert queue.status_code == 200
            assert len(queue.json()) == 1

            decision = client.post(
                f"/api/onboarding/operator/claims/{claim_id}/decision",
                json={
                    "decision": "APPROVE",
                    "reviewer_note": (
                        "Synthetic operator review, not "
                        "independent business verification."
                    ),
                },
            )

            assert decision.status_code == 200
            assert (
                decision.json()["status"]
                == "OPERATOR_APPROVED_CLAIM"
            )
            assert (
                decision.json()[
                    "business_ownership_independently_verified"
                ] is False
            )

            assert client.post(
                f"/api/onboarding/operator/claims/{claim_id}/decision",
                json={
                    "decision": "REJECT",
                    "reviewer_note": (
                        "Second decision should be rejected."
                    ),
                },
            ).status_code == 409

            assert client.post(
                "/api/onboarding/logout",
                headers=auth,
            ).status_code == 200

            assert client.get(
                "/api/onboarding/me",
                headers=auth,
            ).status_code == 401

    finally:
        app.dependency_overrides.clear()
        engine.dispose()
