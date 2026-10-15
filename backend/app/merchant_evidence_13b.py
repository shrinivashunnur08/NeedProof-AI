"""Chunk 13B.1: authenticated evidence tracking and append-only merchant reports.

No merchant contact is initiated. Google Place IDs are the only Maps fields stored.
These reports are never independently verified and never authorize a purchase.
Feature is off by default until Cloud SQL schema and merchant approvals are ready.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.algorithms.adaptive_replanning import (
    CandidateMerchant, CustomerRequirements, MerchantReport,
    ReadinessAssessment, ReplanInput, ReportedSubmission, evaluate_replan,
)
from app.config import get_settings
from app.db.models import Base, utc_now
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/evidence", tags=["Merchant Evidence 13B"])


class EvidenceInquiry13B(Base):
    __tablename__ = "evidence_inquiries_13b"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    requester_uid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    place_id: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    product_query: Mapped[str] = mapped_column(String(250), nullable=False)
    budget_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("budget_minor IS NULL OR budget_minor >= 0", name="ck_evidence_13b_budget"),)


class MerchantGrant13B(Base):
    __tablename__ = "merchant_grants_13b"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_uid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    place_id: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    approval_status: Mapped[str] = mapped_column(String(40), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    __table_args__ = (
        UniqueConstraint("merchant_uid", "place_id", name="uq_merchant_grant_13b"),
        CheckConstraint("approval_status IN ('OPERATOR_APPROVED_CLAIM', 'REVOKED')", name="ck_merchant_grant_13b_status"),
    )


class EvidenceRevision13B(Base):
    __tablename__ = "evidence_revisions_13b"
    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_id: Mapped[str] = mapped_column(ForeignKey("evidence_inquiries_13b.id"), nullable=False, index=True)
    merchant_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    specification_notes: Mapped[str | None] = mapped_column(Text)
    delivery_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_evidence_13b_stock"),
        CheckConstraint("price_minor IS NULL OR price_minor > 0", name="ck_evidence_13b_price"),
    )


class NewInquiry(BaseModel):
    place_id: str = Field(min_length=3, max_length=300)
    product_query: str = Field(min_length=3, max_length=250)
    budget_minor: int | None = Field(default=None, ge=0, le=100_000_000)

    @field_validator("place_id", "product_query")
    @classmethod
    def clean(cls, value: str) -> str:
        result = " ".join(value.strip().split())
        if not result or any(ord(ch) < 32 for ch in result):
            raise ValueError("Invalid text")
        return result


class NewMerchantReport(BaseModel):
    stock_quantity: int = Field(ge=0, le=1_000_000)
    price_minor: int | None = Field(default=None, ge=1, le=100_000_000)
    specification_notes: str | None = Field(default=None, max_length=1500)
    delivery_available: bool | None = None
    authorized_to_report: bool

    @model_validator(mode="after")
    def validate_report(self):
        if not self.authorized_to_report:
            raise ValueError("Confirm that you are authorized to report on this business")
        if self.stock_quantity > 0 and self.price_minor is None:
            raise ValueError("A price is required when reporting available stock")
        return self


def feature_gate() -> None:
    if os.environ.get("MERCHANT_EVIDENCE_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Merchant evidence tracking is not enabled")
    settings = get_settings()
    if (settings.environment == "production" or os.environ.get("K_SERVICE")) and settings.database_backend != "cloud_sql":
        raise HTTPException(status_code=503, detail="Production evidence storage is not configured")


def require_customer(
    authorization: str | None = Header(default=None),
    x_firebase_appcheck: str | None = Header(default=None),
) -> str:
    # Import here avoids circular import with cloud_decision_api.
    from app.cloud_decision_api import require_firebase_client
    return require_firebase_client(authorization, x_firebase_appcheck)


def require_merchant(
    authorization: str | None = Header(default=None),
    x_firebase_appcheck: str | None = Header(default=None),
) -> str:
    from app.cloud_decision_api import _firebase_app, require_firebase_client
    uid = require_firebase_client(authorization, x_firebase_appcheck)
    from firebase_admin import auth
    claims = auth.verify_id_token(authorization.removeprefix("Bearer ").strip(), app=_firebase_app())
    # Firebase email verification or a trusted non-anonymous provider is required.
    if claims.get("firebase", {}).get("sign_in_provider") == "anonymous" or not claims.get("email_verified"):
        raise HTTPException(status_code=403, detail="Verified merchant sign-in required")
    return uid


def _latest(db: Session, inquiry_id: str) -> EvidenceRevision13B | None:
    return db.scalar(select(EvidenceRevision13B).where(EvidenceRevision13B.inquiry_id == inquiry_id).order_by(EvidenceRevision13B.id.desc()).limit(1))


def _history(db: Session, inquiry_id: str) -> list[EvidenceRevision13B]:
    return list(db.scalars(select(EvidenceRevision13B).where(EvidenceRevision13B.inquiry_id == inquiry_id).order_by(EvidenceRevision13B.id.desc()).limit(30)))


def _granted(db: Session, uid: str, place_id: str) -> bool:
    return db.scalar(select(MerchantGrant13B.id).where(MerchantGrant13B.merchant_uid == uid, MerchantGrant13B.place_id == place_id, MerchantGrant13B.approval_status == "OPERATOR_APPROVED_CLAIM").limit(1)) is not None


def _serialize_revision(report: EvidenceRevision13B) -> dict:
    return {
        "revision_id": report.id, "stock_quantity": report.stock_quantity,
        "price_minor": report.price_minor, "currency": report.currency,
        "specification_notes": report.specification_notes,
        "delivery_available": report.delivery_available,
        "recorded_at": report.recorded_at.isoformat(),
        "source": "MERCHANT_REPORTED_UNVERIFIED",
        "merchant_identity_independently_verified": False,
    }


def _decision(inquiry: EvidenceInquiry13B, report: EvidenceRevision13B | None) -> dict:
    evidence = None
    if report is not None:
        age = utc_now() - _aware(report.recorded_at)
        freshness = "RECENT_REPORT" if age <= timedelta(minutes=120) else "STALE_REPORT"
        evidence = MerchantReport(
            product_query=inquiry.product_query, status="REPORTED_UNVERIFIED",
            submission=ReportedSubmission(
                product_name=inquiry.product_query,
                stock_quantity=report.stock_quantity,
                price_minor=report.price_minor,
                delivery_available=report.delivery_available,
                submitted_at=report.recorded_at,
            ),
            assessment=ReadinessAssessment(freshness=freshness),
        )
    return evaluate_replan(ReplanInput(
        customer=CustomerRequirements(product_query=inquiry.product_query, budget_minor=inquiry.budget_minor),
        merchants=[CandidateMerchant(place_id=inquiry.place_id, name="Candidate business", evidence=evidence)],
    ))


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _detail(db: Session, inquiry: EvidenceInquiry13B) -> dict:
    revisions = _history(db, inquiry.id)
    current = revisions[0] if revisions else None
    return {
        "inquiry_id": inquiry.id,
        "place_id": inquiry.place_id,
        "product_query": inquiry.product_query,
        "status": "REPORTED_UNVERIFIED" if current else ("EXPIRED" if _aware(inquiry.expires_at) <= utc_now() else "AWAITING_MERCHANT"),
        "merchant_contacted": False,  # platform sends no invitations or direct messages
        "created_at": inquiry.created_at.isoformat(),
        "expires_at": inquiry.expires_at.isoformat(),
        "current_report": _serialize_revision(current) if current else None,
        "history": [_serialize_revision(item) for item in revisions],
        "replanning": _decision(inquiry, current),
        "notice": "An inquiry does not contact a merchant. Reports, if present, are merchant-submitted and not independently verified. No purchase is authorized.",
    }


@router.post("/inquiries", status_code=201, dependencies=[Depends(feature_gate)])
def create_inquiry(payload: NewInquiry, response: Response, uid: str = Depends(require_customer), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    now = utc_now()
    cutoff = now - timedelta(hours=24)
    recent = db.scalar(select(func.count(EvidenceInquiry13B.id)).where(EvidenceInquiry13B.requester_uid == uid, EvidenceInquiry13B.created_at >= cutoff)) or 0
    if recent >= 10:
        raise HTTPException(status_code=429, detail="Daily evidence inquiry limit reached")
    duplicate = db.scalar(select(EvidenceInquiry13B).where(
        EvidenceInquiry13B.requester_uid == uid, EvidenceInquiry13B.place_id == payload.place_id,
        EvidenceInquiry13B.product_query == payload.product_query,
        EvidenceInquiry13B.created_at >= now - timedelta(minutes=10),
    ).order_by(EvidenceInquiry13B.created_at.desc()).limit(1))
    if duplicate:
        response.status_code = 200
        return _detail(db, duplicate)
    record = EvidenceInquiry13B(
        id=str(uuid4()), requester_uid=uid, place_id=payload.place_id,
        product_query=payload.product_query, budget_minor=payload.budget_minor,
        created_at=now, expires_at=now + timedelta(days=7),
    )
    db.add(record)
    db.commit()
    return _detail(db, record)


@router.get("/inquiries/{inquiry_id}", dependencies=[Depends(feature_gate)])
def get_inquiry(inquiry_id: str, response: Response, uid: str = Depends(require_customer), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    record = db.get(EvidenceInquiry13B, inquiry_id)
    if record is None or record.requester_uid != uid:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    return _detail(db, record)


@router.get("/merchant/inquiries", dependencies=[Depends(feature_gate)])
def merchant_inquiries(response: Response, uid: str = Depends(require_merchant), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    approved_places = select(MerchantGrant13B.place_id).where(MerchantGrant13B.merchant_uid == uid, MerchantGrant13B.approval_status == "OPERATOR_APPROVED_CLAIM")
    items = db.scalars(select(EvidenceInquiry13B).where(EvidenceInquiry13B.place_id.in_(approved_places), EvidenceInquiry13B.expires_at > utc_now()).order_by(EvidenceInquiry13B.created_at.desc()).limit(25)).all()
    # Don't disclose requester identities to merchant.
    return {"inquiries": [{"inquiry_id": item.id, "place_id": item.place_id, "product_query": item.product_query, "created_at": item.created_at.isoformat(), "expires_at": item.expires_at.isoformat()} for item in items], "notice": "Listings are inquiries, not confirmed customer orders."}


@router.post("/merchant/inquiries/{inquiry_id}/reports", status_code=201, dependencies=[Depends(feature_gate)])
def report_evidence(inquiry_id: str, payload: NewMerchantReport, response: Response, uid: str = Depends(require_merchant), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    record = db.get(EvidenceInquiry13B, inquiry_id)
    if record is None or not _granted(db, uid, record.place_id):
        raise HTTPException(status_code=404, detail="Inquiry not found")
    if _aware(record.expires_at) <= utc_now():
        raise HTTPException(status_code=410, detail="Inquiry has expired")
    if (db.scalar(select(func.count(EvidenceRevision13B.id)).where(EvidenceRevision13B.inquiry_id == inquiry_id)) or 0) >= 30:
        raise HTTPException(status_code=429, detail="Report history limit reached")
    report = EvidenceRevision13B(
        inquiry_id=inquiry_id, merchant_uid=uid,
        stock_quantity=payload.stock_quantity,
        price_minor=payload.price_minor,
        specification_notes=payload.specification_notes,
        delivery_available=payload.delivery_available,
        recorded_at=utc_now(),
    )
    db.add(report)
    db.commit()
    return _detail(db, record)
