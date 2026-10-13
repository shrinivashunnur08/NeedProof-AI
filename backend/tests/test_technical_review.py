
import hashlib
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.algorithms.compatibility import (
    CompatibilityInput,
    evaluate_compatibility,
)
from app.api.assurance import require_assurance_operator
from app.db.models import (
    AssuranceConflictReview,
    AssuranceObservation,
    Base,
    MerchantAssuranceCase,
    MerchantEvidenceSubmission,
    TechnicalCompatibilityReview,
    VerificationRequest,
    utc_now,
)
from app.db.session import get_db
from app.main import app


def payload(current_ma=3250, cable=5):
    return {
        "device_model": "TEST-LAPTOP-65W",
        "device_supports_usb_pd": True,
        "device_required_power_w": 65,
        "device_required_voltage_v": 20,
        "charger_supports_usb_pd": True,
        "charger_profiles": [
            {
                "voltage_v": 20,
                "current_ma": current_ma,
            }
        ],
        "cable_current_rating_a": cable,
    }


def setup_case(with_conflict=False):
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
            place_id="TEST_TECHNICAL_STORE",
            product_query="65W USB-C PD charger",
            invitation_hash=hashlib.sha256(
                b"fictional-technical-test"
            ).hexdigest(),
            status="REPORTED_UNVERIFIED",
            expires_at=utc_now() + timedelta(hours=24),
        )

        db.add(request)
        db.flush()

        db.add(
            MerchantEvidenceSubmission(
                request_id=request.id,
                product_name="Test Charger",
                stock_quantity=3,
                price_minor=89900,
                currency="INR",
                specification_notes="Synthetic test specifications",
                delivery_available=None,
                evidence_status="MERCHANT_REPORTED_UNVERIFIED",
            )
        )

        case = MerchantAssuranceCase(
            verification_request_id=request.id
        )

        db.add(case)
        db.flush()

        case_id = case.id

        if with_conflict:
            db.add(
                AssuranceObservation(
                    case_id=case_id,
                    check_type="STOCK",
                    source_type="DIRECTORY_CALLBACK",
                    finding="CONTRADICTS",
                    reviewer_note=(
                        "Synthetic contradictory observation."
                    ),
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

    return engine, factory, case_id


def test_conditional_compatibility_match():
    result = evaluate_compatibility(
        CompatibilityInput(**payload())
    )

    assert result["status"] == "CONDITIONAL_SPEC_MATCH"
    assert result["purchase_allowed"] is False
    assert result["specification_source_verified"] is False


def test_insufficient_charger_power():
    result = evaluate_compatibility(
        CompatibilityInput(**payload(current_ma=3000))
    )

    assert result["status"] == "REPORTED_SPEC_MISMATCH"


def test_unknown_cable_cannot_prove_65w():
    result = evaluate_compatibility(
        CompatibilityInput(**payload(cable=None))
    )

    assert result["status"] == "INSUFFICIENT_SPEC_INPUT"


def test_api_saves_compatibility_review():
    engine, factory, case_id = setup_case()

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/technical/cases/{case_id}/compatibility",
                json=payload(),
            )

            assert response.status_code == 200
            assert (
                response.json()["status"]
                == "CONDITIONAL_SPEC_MATCH"
            )

            saved = client.get(
                f"/api/technical/cases/{case_id}"
            )

            assert saved.status_code == 200

            result = saved.json()
            assert result["purchase_allowed"] is False

            assert (
                result["latest_compatibility"]["status"]
                == "CONDITIONAL_SPEC_MATCH"
            )

        with factory() as db:
            reviews = db.scalars(
                select(TechnicalCompatibilityReview)
            ).all()

            assert len(reviews) == 1

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_conflict_investigation_preserves_dispute():
    engine, factory, case_id = setup_case(
        with_conflict=True
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/technical/cases/{case_id}/conflict-investigations",
                json={
                    "check_type": "STOCK",
                    "investigation_note": (
                        "Synthetic follow-up investigation recorded."
                    ),
                    "evidence_reference": "TEST-REF-001",
                },
            )

            assert response.status_code == 200
            assert response.json()["conflict_resolved"] is False

            history = client.get(
                f"/api/technical/cases/{case_id}"
            ).json()

            assert len(
                history["conflict_investigations"]
            ) == 1

        with factory() as db:
            original_conflict = db.scalar(
                select(AssuranceObservation)
                .where(
                    AssuranceObservation.case_id == case_id,
                    AssuranceObservation.finding == "CONTRADICTS",
                )
            )

            assert original_conflict is not None

            reviews = db.scalars(
                select(AssuranceConflictReview)
            ).all()

            assert len(reviews) == 1

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_cannot_investigate_nonexistent_conflict():
    engine, _, case_id = setup_case(
        with_conflict=False
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/technical/cases/{case_id}/conflict-investigations",
                json={
                    "check_type": "STOCK",
                    "investigation_note": (
                        "Synthetic follow-up without a conflict."
                    ),
                    "evidence_reference": "TEST-REF-002",
                },
            )

            assert response.status_code == 409

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_operator_authorization_required():
    engine, _, case_id = setup_case()

    try:
        # Remove only the test bypass of the operator guard.
        app.dependency_overrides.pop(
            require_assurance_operator, None
        )

        with TestClient(app) as client:
            response = client.get(
                f"/api/technical/cases/{case_id}"
            )

            assert response.status_code == 403

    finally:
        app.dependency_overrides.clear()
        engine.dispose()
