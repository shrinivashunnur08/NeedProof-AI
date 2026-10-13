
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.services.evidence_assessment import assess_evidence
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import (
    MerchantEvidenceSubmission,
    VerificationRequest,
    utc_now,
)
from app.db.session import get_db


router = APIRouter(
    prefix="/api/verification",
    tags=["Merchant Verification"],
)


class CreateInvitation(BaseModel):
    place_id: str = Field(min_length=3, max_length=300)
    product_query: str = Field(min_length=5, max_length=250)


class MerchantSubmissionInput(BaseModel):
    product_name: str = Field(min_length=2, max_length=200)
    stock_quantity: int = Field(ge=0, le=1000000)
    price_minor: int | None = Field(
        default=None, ge=1, le=100000000
    )
    specification_notes: str | None = Field(
        default=None, max_length=2000
    )
    delivery_available: bool | None = None

    authorized_to_respond: bool

    @model_validator(mode="after")
    def check_submission(self):
        if not self.authorized_to_respond:
            raise ValueError(
                "You must confirm that you are authorized "
                "to provide this information."
            )

        if self.stock_quantity > 0 and self.price_minor is None:
            raise ValueError(
                "A selling price is required when stock is available."
            )

        return self


def require_local_operator(request: Request):
    settings = get_settings()

    client_host = (
        request.client.host if request.client else ""
    )

    if (
        settings.environment != "development"
        or client_host not in ("127.0.0.1", "::1")
    ):
        raise HTTPException(
            status_code=403,
            detail="Operator invitations are local-only in Chunk 4B.",
        )


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_authorized_request(
    request_id: int,
    token: str | None,
    db: Session,
) -> VerificationRequest:
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invitation token is required.",
        )

    record = db.get(VerificationRequest, request_id)

    if record is None or not hmac.compare_digest(
        record.invitation_hash,
        token_hash(token),
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid verification invitation.",
        )

    return record


def serialize_submission(
    submission: MerchantEvidenceSubmission | None,
):
    if submission is None:
        return None

    return {
        "product_name": submission.product_name,
        "stock_quantity": submission.stock_quantity,
        "price_minor": submission.price_minor,
        "currency": submission.currency,
        "specification_notes": submission.specification_notes,
        "delivery_available": submission.delivery_available,
        "submitted_at": submission.submitted_at,
        "evidence_status": submission.evidence_status,
        "merchant_identity_verified": False,
    }


@router.post("/invitations", status_code=201)
def create_invitation(
    payload: CreateInvitation,
    _: None = Depends(require_local_operator),
    db: Session = Depends(get_db),
):
    token = secrets.token_urlsafe(32)

    record = VerificationRequest(
        place_id=payload.place_id,
        product_query=payload.product_query.strip(),
        invitation_hash=token_hash(token),
        status="AWAITING_RESPONSE",
        expires_at=utc_now() + timedelta(hours=48),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    # The token is returned once to the local operator.
    # Only its SHA-256 digest is stored in the database.
    return {
        "request_id": record.id,
        "status": record.status,
        "invitation_token": token,
        "expires_at": record.expires_at,
        "message": (
            "Invitation created. No merchant has been contacted."
        ),
    }


@router.get("/requests/{request_id}")
def get_verification_request(
    request_id: int,
    x_verification_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    record = get_authorized_request(
        request_id, x_verification_token, db
    )

    submission = db.query(
        MerchantEvidenceSubmission
    ).filter(
        MerchantEvidenceSubmission.request_id == request_id
    ).first()

    status = record.status

    if (
        status == "AWAITING_RESPONSE"
        and utc_now() > ensure_utc(record.expires_at)
    ):
        status = "EXPIRED"

    return {
        "request_id": record.id,
        "product_query": record.product_query,
        "status": status,
        "expires_at": record.expires_at,
        "submission": serialize_submission(submission),
        "notice": (
            "Submitted information is merchant-reported. "
            "The respondent's business identity has not "
            "been independently verified."
        ),
    }


@router.post("/requests/{request_id}/respond")
def submit_merchant_evidence(
    request_id: int,
    payload: MerchantSubmissionInput,
    x_verification_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    record = get_authorized_request(
        request_id, x_verification_token, db
    )

    if utc_now() > ensure_utc(record.expires_at):
        raise HTTPException(
            status_code=410,
            detail="This verification invitation has expired.",
        )

    if record.status != "AWAITING_RESPONSE":
        raise HTTPException(
            status_code=409,
            detail="This invitation has already been used.",
        )

    # Atomically claim the pending invitation. The same
    # request cannot successfully receive two submissions.
    result = db.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.id == request_id,
            VerificationRequest.status == "AWAITING_RESPONSE",
        )
        .values(
            status="REPORTED_UNVERIFIED",
            responded_at=utc_now(),
        )
    )

    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This invitation has already been completed.",
        )

    submission = MerchantEvidenceSubmission(
        request_id=request_id,
        product_name=payload.product_name.strip(),
        stock_quantity=payload.stock_quantity,
        price_minor=payload.price_minor,
        currency="INR",
        specification_notes=payload.specification_notes,
        delivery_available=payload.delivery_available,
        evidence_status="MERCHANT_REPORTED_UNVERIFIED",
    )

    db.add(submission)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A response already exists for this request.",
        ) from exc

    return {
        "status": "REPORTED_UNVERIFIED",
        "message": (
            "Submission saved. The evidence is merchant-reported "
            "and has not been independently verified."
        ),
        "submission": serialize_submission(submission),
    }

@router.get("/requests/{request_id}/assessment")
def get_evidence_assessment(
    request_id: int,
    response: Response,
    x_verification_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # Only an invitation holder can access this assessment.
    record = get_authorized_request(
        request_id,
        x_verification_token,
        db,
    )

    submission = db.scalar(
        select(MerchantEvidenceSubmission).where(
            MerchantEvidenceSubmission.request_id == request_id
        )
    )

    response.headers["Cache-Control"] = "no-store"

    return assess_evidence(record, submission)
