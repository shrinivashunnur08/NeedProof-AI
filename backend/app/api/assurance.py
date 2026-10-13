
import secrets
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.verification import get_authorized_request
from app.config import get_settings
from app.db.models import (
    AssuranceObservation,
    MerchantAssuranceCase,
    MerchantEvidenceSubmission,
    VerificationRequest,
)
from app.db.session import get_db
from app.services.assurance_service import assess_assurance


router = APIRouter(
    prefix="/api/assurance",
    tags=["Merchant Assurance Desk"],
)


class CreateAssuranceCase(BaseModel):
    request_id: int = Field(gt=0)
    invitation_token: str = Field(
        min_length=20,
        max_length=512,
    )


class RecordObservation(BaseModel):
    check_type: Literal["IDENTITY", "STOCK", "PRICE"]

    source_type: Literal[
        "DIRECTORY_CALLBACK",
        "AUTHORIZED_POS_EXPORT",
    ]

    finding: Literal[
        "CORROBORATES",
        "CONTRADICTS",
        "INCONCLUSIVE",
    ]

    reviewer_note: str = Field(
        min_length=12,
        max_length=600,
    )


def require_assurance_operator(
    request: Request,
    x_assurance_key: str | None = Header(default=None),
):
    settings = get_settings()

    host = (
        request.client.host if request.client else ""
    )

    permitted = (
        settings.environment == "development"
        and host in ("127.0.0.1", "::1")
        and bool(settings.assurance_operator_key)
        and secrets.compare_digest(
            x_assurance_key or "",
            settings.assurance_operator_key,
        )
    )

    if not permitted:
        raise HTTPException(
            status_code=403,
            detail="Assurance operator access denied.",
        )


def load_case(
    case_id: int,
    db: Session,
) -> MerchantAssuranceCase:
    record = db.get(MerchantAssuranceCase, case_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Assurance case not found.",
        )

    return record


def case_assessment(
    case: MerchantAssuranceCase,
    db: Session,
):
    request = db.get(
        VerificationRequest,
        case.verification_request_id,
    )

    submission = db.scalar(
        select(MerchantEvidenceSubmission)
        .where(
            MerchantEvidenceSubmission.request_id
            == case.verification_request_id
        )
    )

    if request is None or submission is None:
        raise HTTPException(
            status_code=409,
            detail="The source submission is unavailable.",
        )

    observations = db.scalars(
        select(AssuranceObservation)
        .where(AssuranceObservation.case_id == case.id)
        .order_by(AssuranceObservation.id)
    ).all()

    return assess_assurance(
        case,
        request,
        submission,
        list(observations),
    )


@router.post("/cases")
def open_assurance_case(
    payload: CreateAssuranceCase,
    response: Response,
    _: None = Depends(require_assurance_operator),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    request = get_authorized_request(
        payload.request_id,
        payload.invitation_token,
        db,
    )

    submission = db.scalar(
        select(MerchantEvidenceSubmission)
        .where(
            MerchantEvidenceSubmission.request_id
            == request.id
        )
    )

    if submission is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "A merchant response must exist before "
                "opening an assurance case."
            ),
        )

    case = db.scalar(
        select(MerchantAssuranceCase)
        .where(
            MerchantAssuranceCase.verification_request_id
            == request.id
        )
    )

    if case is None:
        case = MerchantAssuranceCase(
            verification_request_id=request.id,
        )

        db.add(case)

        try:
            db.commit()
            db.refresh(case)
        except IntegrityError:
            db.rollback()
            case = db.scalar(
                select(MerchantAssuranceCase)
                .where(
                    MerchantAssuranceCase.verification_request_id
                    == request.id
                )
            )

            if case is None:
                raise HTTPException(
                    status_code=409,
                    detail="Assurance case creation conflicted.",
                )

    return case_assessment(case, db)


@router.get("/cases/{case_id}")
def get_assurance_case(
    case_id: int,
    response: Response,
    _: None = Depends(require_assurance_operator),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    return case_assessment(
        load_case(case_id, db),
        db,
    )


@router.post("/cases/{case_id}/observations")
def record_assurance_observation(
    case_id: int,
    payload: RecordObservation,
    response: Response,
    _: None = Depends(require_assurance_operator),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    case = load_case(case_id, db)

    if (
        payload.check_type == "IDENTITY"
        and payload.source_type != "DIRECTORY_CALLBACK"
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Identity attestation requires an "
                "independently sourced directory callback."
            ),
        )

    observation = AssuranceObservation(
        case_id=case.id,
        check_type=payload.check_type,
        source_type=payload.source_type,
        finding=payload.finding,
        reviewer_note=payload.reviewer_note.strip(),
    )

    db.add(observation)
    db.commit()

    return case_assessment(case, db)
