
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.verification import (
    get_authorized_request,
    require_local_operator,
)
from app.db.models import (
    MerchantEvidenceSubmission,
    utc_now,
)
from app.db.session import get_db
from app.services.evidence_assessment import aware
from app.services.reported_offer_advisor import (
    ReportedOffer,
    plan_reported_offers,
)


router = APIRouter(
    prefix="/api/optimization",
    tags=["Real-World Advisory Optimization"],
)


class InvitationReference(BaseModel):
    request_id: int = Field(gt=0)
    invitation_token: str = Field(
        min_length=20,
        max_length=512,
    )


class AdvisoryRequest(BaseModel):
    budget_inr: int = Field(ge=1, le=1000000)
    quantity: int = Field(ge=1, le=100)
    delivery_required: bool = True
    invitations: list[InvitationReference] = Field(
        min_length=1,
        max_length=12,
    )

    @model_validator(mode="after")
    def validate_references(self):
        ids = [item.request_id for item in self.invitations]

        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate verification request IDs.")

        return self


@router.post("/reported-offers")
def compare_reported_offers(
    payload: AdvisoryRequest,
    response: Response,
    _: None = Depends(require_local_operator),
    db: Session = Depends(get_db),
):
    """
    Local operator-only comparison.

    Invitation tokens are read transiently and are
    never returned or stored by this endpoint.
    """

    response.headers["Cache-Control"] = "no-store"

    candidates = []

    for reference in payload.invitations:
        record = get_authorized_request(
            reference.request_id,
            reference.invitation_token,
            db,
        )

        submission = db.scalar(
            select(MerchantEvidenceSubmission)
            .where(
                MerchantEvidenceSubmission.request_id
                == record.id
            )
        )

        candidates.append(
            ReportedOffer(
                request_id=record.id,
                place_id=record.place_id,
                product_query=record.product_query,
                product_name=(
                    submission.product_name
                    if submission else None
                ),
                stock_quantity=(
                    submission.stock_quantity
                    if submission else None
                ),
                price_minor=(
                    submission.price_minor
                    if submission else None
                ),
                delivery_available=(
                    submission.delivery_available
                    if submission else None
                ),
                submitted_at=(
                    submission.submitted_at
                    if submission else None
                ),
                invitation_expired=(
                    utc_now() > aware(record.expires_at)
                ),
            )
        )

    try:
        return plan_reported_offers(
            candidates,
            budget_minor=payload.budget_inr * 100,
            quantity=payload.quantity,
            delivery_required=payload.delivery_required,
        )

    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
