
import hashlib
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.assurance import require_assurance_operator
from app.db.models import (
    Base,
    MerchantEvidenceSubmission,
    VerificationRequest,
    utc_now,
)
from app.db.session import get_db
from app.main import app


TEST_TOKEN = "fictional-assurance-test-token-123456"


def setup_case_database(with_submission=True):
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

    with factory() as db:
        request = VerificationRequest(
            place_id="TEST_ASSURANCE_STORE",
            product_query="65W USB-C PD charger",
            invitation_hash=hashlib.sha256(
                TEST_TOKEN.encode()
            ).hexdigest(),
            status="REPORTED_UNVERIFIED",
            expires_at=utc_now() + timedelta(hours=24),
        )

        db.add(request)
        db.flush()

        request_id = request.id

        if with_submission:
            db.add(
                MerchantEvidenceSubmission(
                    request_id=request_id,
                    product_name="Test 65W Charger",
                    stock_quantity=3,
                    price_minor=89900,
                    currency="INR",
                    specification_notes="USB-C PD 65W test",
                    delivery_available=None,
                    evidence_status="MERCHANT_REPORTED_UNVERIFIED",
                )
            )

        db.commit()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_assurance_operator] = (
        lambda: None
    )

    return engine, factory, request_id


def open_case(client, request_id):
    response = client.post(
        "/api/assurance/cases",
        json={
            "request_id": request_id,
            "invitation_token": TEST_TOKEN,
        },
    )

    assert response.status_code == 200, response.text
    return response.json()


def observe(
    client,
    case_id,
    check_type,
    source_type,
    finding,
):
    response = client.post(
        f"/api/assurance/cases/{case_id}/observations",
        json={
            "check_type": check_type,
            "source_type": source_type,
            "finding": finding,
            "reviewer_note": (
                "Synthetic unit-test observation only."
            ),
        },
    )

    return response


def test_initial_case_is_unverified():
    engine, _, request_id = setup_case_database()

    try:
        with TestClient(app) as client:
            result = open_case(client, request_id)

            assert result["mode"] == "OPERATOR_ASSURANCE_REVIEW"
            assert result["status"] == "REPORTED_UNVERIFIED"
            assert result["field_status"]["merchant_identity"] == "UNVERIFIED"
            assert result["field_status"]["stock"] == "REPORTED_UNVERIFIED"
            assert result["purchase_allowed"] is False

            # Reopening the same case is idempotent.
            again = open_case(client, request_id)
            assert again["case_id"] == result["case_id"]

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_operator_attestations_never_authorize_purchase():
    engine, _, request_id = setup_case_database()

    try:
        with TestClient(app) as client:
            case = open_case(client, request_id)
            case_id = case["case_id"]

            identity = observe(
                client,
                case_id,
                "IDENTITY",
                "DIRECTORY_CALLBACK",
                "CORROBORATES",
            )

            assert identity.status_code == 200
            assert (
                identity.json()["field_status"]["merchant_identity"]
                == "OPERATOR_ATTESTED"
            )

            stock = observe(
                client,
                case_id,
                "STOCK",
                "AUTHORIZED_POS_EXPORT",
                "CORROBORATES",
            )

            assert stock.status_code == 200
            assert (
                stock.json()["field_status"]["stock"]
                == "OPERATOR_CORROBORATED"
            )

            price = observe(
                client,
                case_id,
                "PRICE",
                "AUTHORIZED_POS_EXPORT",
                "CORROBORATES",
            )

            assert price.status_code == 200

            result = price.json()

            assert (
                result["field_status"]["price"]
                == "OPERATOR_CORROBORATED"
            )

            assert (
                result["field_status"]["compatibility"]
                == "NOT_VERIFIED"
            )

            assert result["purchase_allowed"] is False
            assert (
                result["independently_authenticated_merchant"]
                is False
            )

            assert len(result["observations"]) == 3

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_conflict_is_not_overwritten_by_support():
    engine, _, request_id = setup_case_database()

    try:
        with TestClient(app) as client:
            case_id = open_case(client, request_id)["case_id"]

            observe(
                client,
                case_id,
                "IDENTITY",
                "DIRECTORY_CALLBACK",
                "CORROBORATES",
            )

            observe(
                client,
                case_id,
                "STOCK",
                "AUTHORIZED_POS_EXPORT",
                "CORROBORATES",
            )

            contradiction = observe(
                client,
                case_id,
                "STOCK",
                "DIRECTORY_CALLBACK",
                "CONTRADICTS",
            )

            assert contradiction.status_code == 200

            result = contradiction.json()

            assert result["status"] == "CONFLICT_RECORDED"
            assert (
                result["field_status"]["stock"]
                == "CONFLICT_RECORDED"
            )

            assert (
                result["recommended_next_action"]["code"]
                == "RESOLVE_CONFLICT"
            )

            assert result["purchase_allowed"] is False

            # Adding more support must not hide the conflict.
            later = observe(
                client,
                case_id,
                "STOCK",
                "AUTHORIZED_POS_EXPORT",
                "CORROBORATES",
            )

            assert (
                later.json()["field_status"]["stock"]
                == "CONFLICT_RECORDED"
            )

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_invalid_invitation_and_source():
    engine, _, request_id = setup_case_database()

    try:
        with TestClient(app) as client:
            invalid = client.post(
                "/api/assurance/cases",
                json={
                    "request_id": request_id,
                    "invitation_token": (
                        "incorrect-fictional-token-123456"
                    ),
                },
            )

            assert invalid.status_code == 403

            case_id = open_case(
                client, request_id
            )["case_id"]

            invalid_source = observe(
                client,
                case_id,
                "IDENTITY",
                "AUTHORIZED_POS_EXPORT",
                "CORROBORATES",
            )

            assert invalid_source.status_code == 422

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_missing_submission_cannot_open_case():
    engine, _, request_id = setup_case_database(
        with_submission=False
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/assurance/cases",
                json={
                    "request_id": request_id,
                    "invitation_token": TEST_TOKEN,
                },
            )

            assert response.status_code == 409

    finally:
        app.dependency_overrides.clear()
        engine.dispose()
