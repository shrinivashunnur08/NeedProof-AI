
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.algorithms.compatibility import (
    CompatibilityInput,
    evaluate_compatibility,
)
from app.api.assurance import (
    load_case,
    require_assurance_operator,
)
from app.db.models import (
    AssuranceConflictReview,
    AssuranceObservation,
    TechnicalCompatibilityReview,
)
from app.db.session import get_db


router = APIRouter(
    prefix="/api/technical",
    tags=["Technical & Conflict Review"],
)


class ConflictInvestigationInput(BaseModel):
    check_type: Literal["IDENTITY", "STOCK", "PRICE"]

    investigation_note: str = Field(
        min_length=12,
        max_length=1000,
    )

    evidence_reference: str = Field(
        min_length=5,
        max_length=300,
    )


def serialize_compatibility(
    review: TechnicalCompatibilityReview | None,
):
    if review is None:
        return None

    return {
        "id": review.id,
        "status": review.result,
        "device_input": review.device_input,
        "charger_input": review.charger_input,
        "reasons": review.reasons,
        "recorded_at": review.recorded_at,
        "purchase_allowed": False,
    }


@router.get("/cases/{case_id}")
def get_technical_case(
    case_id: int,
    response: Response,
    _: None = Depends(require_assurance_operator),
    db: Session = Depends(get_db),
):
    load_case(case_id, db)

    response.headers["Cache-Control"] = "no-store"

    latest = db.scalar(
        select(TechnicalCompatibilityReview)
        .where(
            TechnicalCompatibilityReview.case_id == case_id
        )
        .order_by(TechnicalCompatibilityReview.id.desc())
        .limit(1)
    )

    reviews = db.scalars(
        select(AssuranceConflictReview)
        .where(AssuranceConflictReview.case_id == case_id)
        .order_by(AssuranceConflictReview.id)
    ).all()

    return {
        "case_id": case_id,
        "latest_compatibility": serialize_compatibility(
            latest
        ),
        "conflict_investigations": [
            {
                "id": review.id,
                "check_type": review.check_type,
                "investigation_note": review.investigation_note,
                "evidence_reference": review.evidence_reference,
                "status": review.status,
                "recorded_at": review.recorded_at,
            }
            for review in reviews
        ],
        "purchase_allowed": False,
        "notice": (
            "Technical results are conditional on input data. "
            "Conflict investigations do not automatically "
            "resolve contradictory evidence."
        ),
    }


@router.post("/cases/{case_id}/compatibility")
def run_compatibility_review(
    case_id: int,
    payload: CompatibilityInput,
    response: Response,
    _: None = Depends(require_assurance_operator),
    db: Session = Depends(get_db),
):
    load_case(case_id, db)
    response.headers["Cache-Control"] = "no-store"

    result = evaluate_compatibility(payload)

    review = TechnicalCompatibilityReview(
        case_id=case_id,
        device_input={
            "device_model": payload.device_model,
            "device_supports_usb_pd": (
                payload.device_supports_usb_pd
            ),
            "device_required_power_w": (
                payload.device_required_power_w
            ),
            "device_required_voltage_v": (
                payload.device_required_voltage_v
            ),
        },
        charger_input={
            "charger_supports_usb_pd": (
                payload.charger_supports_usb_pd
            ),
            "charger_profiles": [
                profile.model_dump()
                for profile in payload.charger_profiles
            ],
            "cable_current_rating_a": (
                payload.cable_current_rating_a
            ),
        },
        result=result["status"],
        reasons=result["reasons"],
    )

    db.add(review)
    db.commit()
    db.refresh(review)

    return {
        "review_id": review.id,
        **result,
    }


@router.post("/cases/{case_id}/conflict-investigations")
def record_conflict_investigation(
    case_id: int,
    payload: ConflictInvestigationInput,
    response: Response,
    _: None = Depends(require_assurance_operator),
    db: Session = Depends(get_db),
):
    load_case(case_id, db)
    response.headers["Cache-Control"] = "no-store"

    contradiction = db.scalar(
        select(AssuranceObservation.id)
        .where(
            AssuranceObservation.case_id == case_id,
            AssuranceObservation.check_type
            == payload.check_type,
            AssuranceObservation.finding == "CONTRADICTS",
        )
        .limit(1)
    )

    if contradiction is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "No recorded contradiction exists "
                "for this check type."
            ),
        )

    review = AssuranceConflictReview(
        case_id=case_id,
        check_type=payload.check_type,
        investigation_note=(
            payload.investigation_note.strip()
        ),
        evidence_reference=(
            payload.evidence_reference.strip()
        ),
        status="REVIEWED_PENDING_INDEPENDENT_PROOF",
    )

    db.add(review)
    db.commit()
    db.refresh(review)

    return {
        "review_id": review.id,
        "case_id": case_id,
        "check_type": review.check_type,
        "status": review.status,
        "recorded_at": review.recorded_at,
        "conflict_resolved": False,
        "purchase_allowed": False,
        "message": (
            "Investigation recorded. The original "
            "contradiction remains unresolved."
        ),
    }
