
from datetime import timezone
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

from app.api.assurance import require_assurance_operator
from app.db.models import (
    MerchantAccount,
    MerchantLoginSession,
    MerchantOwnershipClaim,
    utc_now,
)
from app.db.session import get_db
from app.services.merchant_auth import (
    authenticate,
    create_session,
    get_account_for_token,
    hash_password,
    hash_token,
    normalize_email,
)


router = APIRouter(
    prefix="/api/onboarding",
    tags=["Merchant Onboarding"],
)


def local_only(request: Request):
    from app.config import get_settings

    settings = get_settings()
    host = request.client.host if request.client else ""

    if (
        settings.environment != "development"
        or host not in ("127.0.0.1", "::1")
    ):
        raise HTTPException(
            status_code=403,
            detail="Local onboarding only.",
        )


class RegisterInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)


class LoginInput(BaseModel):
    email: str
    password: str


class ClaimInput(BaseModel):
    place_id: str = Field(min_length=3, max_length=300)


class ClaimDecisionInput(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    reviewer_note: str = Field(min_length=12, max_length=600)


def require_merchant(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> MerchantAccount:
    if (
        not authorization
        or not authorization.startswith("Bearer ")
    ):
        raise HTTPException(
            status_code=401,
            detail="Merchant login required.",
        )

    token = authorization.removeprefix("Bearer ").strip()

    account = get_account_for_token(db, token)

    if account is None:
        raise HTTPException(
            status_code=401,
            detail="Session invalid or expired.",
        )

    return account


def claim_json(claim: MerchantOwnershipClaim) -> dict:
    return {
        "id": claim.id,
        "place_id": claim.place_id,
        "status": claim.status,
        "created_at": claim.created_at,
        "reviewed_at": claim.reviewed_at,
        "reviewer_note": claim.reviewer_note,
        "business_ownership_independently_verified": False,
    }


@router.post("/register", status_code=201)
def register(
    payload: RegisterInput,
    response: Response,
    _: None = Depends(local_only),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    email = normalize_email(payload.email)

    # Basic email-format check, not proof of inbox ownership.
    if (
        "@" not in email
        or email.startswith("@")
        or "." not in email.rsplit("@", 1)[-1]
    ):
        raise HTTPException(
            status_code=422,
            detail="Enter a valid email address.",
        )

    account = MerchantAccount(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
    )

    db.add(account)

    try:
        db.commit()
        db.refresh(account)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Account already exists.",
        ) from exc

    return {
        "id": account.id,
        "display_name": account.display_name,
        "status": "ACCOUNT_CREATED_NOT_BUSINESS_VERIFIED",
    }


@router.post("/login")
def login(
    payload: LoginInput,
    response: Response,
    _: None = Depends(local_only),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    account = authenticate(
        db, payload.email, payload.password
    )

    if account is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials.",
        )

    token, expires_at = create_session(db, account)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "merchant": {
            "id": account.id,
            "display_name": account.display_name,
            "email": account.email,
        },
    }


@router.get("/me")
def me(
    response: Response,
    _: None = Depends(local_only),
    account: MerchantAccount = Depends(require_merchant),
):
    response.headers["Cache-Control"] = "no-store"

    return {
        "id": account.id,
        "display_name": account.display_name,
        "email": account.email,
        "business_ownership_independently_verified": False,
    }


@router.post("/logout")
def logout(
    response: Response,
    authorization: str | None = Header(default=None),
    _: None = Depends(local_only),
    account: MerchantAccount = Depends(require_merchant),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    token = authorization.removeprefix("Bearer ").strip()

    session = db.scalar(
        select(MerchantLoginSession).where(
            MerchantLoginSession.token_hash
            == hash_token(token),
            MerchantLoginSession.merchant_account_id
            == account.id,
        )
    )

    if session is not None:
        session.revoked_at = utc_now()
        db.commit()

    return {"status": "LOGGED_OUT"}


@router.post("/claims", status_code=201)
def create_claim(
    payload: ClaimInput,
    response: Response,
    _: None = Depends(local_only),
    account: MerchantAccount = Depends(require_merchant),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    existing = db.scalar(
        select(MerchantOwnershipClaim).where(
            MerchantOwnershipClaim.merchant_account_id
            == account.id,
            MerchantOwnershipClaim.place_id
            == payload.place_id,
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="You already have a claim for this place.",
        )

    claim = MerchantOwnershipClaim(
        merchant_account_id=account.id,
        place_id=payload.place_id.strip(),
        status="PENDING_REVIEW",
    )

    db.add(claim)
    db.commit()
    db.refresh(claim)

    return claim_json(claim)


@router.get("/claims")
def my_claims(
    response: Response,
    _: None = Depends(local_only),
    account: MerchantAccount = Depends(require_merchant),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    claims = db.scalars(
        select(MerchantOwnershipClaim)
        .where(
            MerchantOwnershipClaim.merchant_account_id
            == account.id
        )
        .order_by(MerchantOwnershipClaim.id.desc())
    ).all()

    return [claim_json(claim) for claim in claims]


@router.get("/operator/claims")
def operator_claims(
    response: Response,
    _: None = Depends(require_assurance_operator),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    claims = db.scalars(
        select(MerchantOwnershipClaim)
        .order_by(MerchantOwnershipClaim.id.desc())
        .limit(100)
    ).all()

    return [claim_json(claim) for claim in claims]


@router.post("/operator/claims/{claim_id}/decision")
def decide_claim(
    claim_id: int,
    payload: ClaimDecisionInput,
    response: Response,
    _: None = Depends(require_assurance_operator),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    claim = db.get(MerchantOwnershipClaim, claim_id)

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    if claim.status != "PENDING_REVIEW":
        raise HTTPException(
            status_code=409,
            detail="Claim already reviewed.",
        )

    if payload.decision == "APPROVE":
        # Block approval if another account already
        # has an operator-approved claim for this place.
        existing = db.scalar(
            select(MerchantOwnershipClaim).where(
                MerchantOwnershipClaim.place_id
                == claim.place_id,
                MerchantOwnershipClaim.status
                == "OPERATOR_APPROVED_CLAIM",
                MerchantOwnershipClaim.id != claim.id,
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Another claim is already approved.",
            )

    claim.status = (
        "OPERATOR_APPROVED_CLAIM"
        if payload.decision == "APPROVE"
        else "REJECTED"
    )

    claim.reviewed_at = utc_now()
    claim.reviewer_note = payload.reviewer_note.strip()

    db.commit()
    db.refresh(claim)

    return claim_json(claim)
