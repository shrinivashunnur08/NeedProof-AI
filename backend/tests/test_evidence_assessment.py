
import hashlib
from datetime import timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Base,
    VerificationRequest,
    utc_now,
)
from app.db.session import get_db
from app.main import app
from app.services.evidence_assessment import assess_evidence


def sample_request():
    return SimpleNamespace(
        id=1,
        expires_at=utc_now() + timedelta(hours=24),
    )


def sample_submission(
    *,
    stock=3,
    price=89900,
    minutes_old=5,
    specs="USB-C PD, 65W",
    delivery=True,
):
    return SimpleNamespace(
        stock_quantity=stock,
        price_minor=price,
        submitted_at=utc_now() - timedelta(minutes=minutes_old),
        specification_notes=specs,
        delivery_available=delivery,
    )


def test_complete_report_still_unverified():
    result = assess_evidence(
        sample_request(),
        sample_submission(),
    )

    assert result["status"] == "REPORTED_UNVERIFIED"
    assert result["reported_fields"] == 4
    assert result["freshness"] == "RECENTLY_REPORTED"
    assert result["eligible_for_commitment"] is False
    assert result["merchant_identity_verified"] is False

    assert (
        result["recommended_next_action"]["code"]
        == "VERIFY_MERCHANT_IDENTITY"
    )


def test_stale_report_requires_refresh():
    result = assess_evidence(
        sample_request(),
        sample_submission(minutes_old=240),
    )

    assert result["freshness"] == "STALE_REPORT"

    assert (
        result["recommended_next_action"]["code"]
        == "REFRESH_MERCHANT_EVIDENCE"
    )


def test_reported_zero_stock():
    result = assess_evidence(
        sample_request(),
        sample_submission(stock=0, price=None),
    )

    assert (
        result["recommended_next_action"]["code"]
        == "FIND_ALTERNATIVE_OFFER"
    )

    assert result["eligible_for_commitment"] is False


def test_missing_delivery_is_detected():
    result = assess_evidence(
        sample_request(),
        sample_submission(delivery=None),
    )

    assert result["reported_fields"] == 3

    assert (
        result["recommended_next_action"]["code"]
        == "CONFIRM_DELIVERY"
    )


def test_no_submission():
    result = assess_evidence(
        sample_request(),
        None,
    )

    assert result["reported_fields"] == 0
    assert result["status"] == "AWAITING_RESPONSE"


def test_assessment_requires_valid_token():
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

    token = "private-test-token"

    with factory() as db:
        record = VerificationRequest(
            place_id="TEST_PLACE_001",
            product_query="65W USB-C PD charger",
            invitation_hash=hashlib.sha256(
                token.encode("utf-8")
            ).hexdigest(),
            status="AWAITING_RESPONSE",
            expires_at=utc_now() + timedelta(hours=24),
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        request_id = record.id

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            url = (
                f"/api/verification/requests/"
                f"{request_id}/assessment"
            )

            no_token = client.get(url)
            assert no_token.status_code == 401

            invalid = client.get(
                url,
                headers={
                    "X-Verification-Token": "wrong-token"
                },
            )
            assert invalid.status_code == 403

            valid = client.get(
                url,
                headers={
                    "X-Verification-Token": token
                },
            )

            assert valid.status_code == 200

            data = valid.json()

            assert data["mode"] == "EVIDENCE_READINESS"
            assert data["reported_fields"] == 0
            assert data["eligible_for_commitment"] is False

            assert (
                valid.headers["cache-control"]
                == "no-store"
            )

    finally:
        app.dependency_overrides.clear()
        engine.dispose()
