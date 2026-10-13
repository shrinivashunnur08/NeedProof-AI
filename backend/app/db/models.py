
from datetime import datetime, timezone
from typing import Any
from typing import Any
from sqlalchemy import Integer
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=False
    )

    area: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    is_demo: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)

    merchant_id: Mapped[int] = mapped_column(
        ForeignKey("merchants.id"),
        nullable=False,
        index=True,
    )

    sku: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(80), nullable=False, index=True
    )

    # Currency stored in minor units:
    # ₹720 = 72000 paise.
    price_minor: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    currency: Mapped[str] = mapped_column(
        String(3), default="INR", nullable=False
    )

    specifications: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "price_minor >= 0",
            name="ck_product_nonnegative_price",
        ),
    )


class InventoryRecord(Base):
    __tablename__ = "inventory_records"

    id: Mapped[int] = mapped_column(primary_key=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        unique=True,
        nullable=False,
    )

    stock_on_hand: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    stock_reserved: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "stock_on_hand >= 0 AND "
            "stock_reserved >= 0 AND "
            "stock_reserved <= stock_on_hand",
            name="ck_inventory_quantities",
        ),
    )


class EvidenceClaim(Base):
    __tablename__ = "evidence_claims"

    id: Mapped[int] = mapped_column(primary_key=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
        index=True,
    )

    claim_type: Mapped[str] = mapped_column(
        String(80), nullable=False
    )

    claimed_value: Mapped[str] = mapped_column(
        String(500), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    source: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'VERIFIED', 'UNVERIFIED', 'STALE', "
            "'CONTRADICTORY', 'REJECTED', 'EXPIRED'"
            ")",
            name="ck_evidence_status",
        ),
    )



class VerificationRequest(Base):
    __tablename__ = "verification_requests"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Google Place ID only — not Google Places name/address.
    place_id: Mapped[str] = mapped_column(
        String(300), nullable=False, index=True
    )

    product_query: Mapped[str] = mapped_column(
        String(250), nullable=False
    )

    invitation_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(40),
        default="AWAITING_RESPONSE",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MerchantEvidenceSubmission(Base):
    __tablename__ = "merchant_evidence_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)

    request_id: Mapped[int] = mapped_column(
        ForeignKey("verification_requests.id"),
        unique=True,
        nullable=False,
    )

    product_name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )

    stock_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    price_minor: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    currency: Mapped[str] = mapped_column(
        String(3), default="INR", nullable=False
    )

    specification_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    delivery_available: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    evidence_status: Mapped[str] = mapped_column(
        String(45),
        default="MERCHANT_REPORTED_UNVERIFIED",
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "stock_quantity >= 0",
            name="ck_submission_stock_nonnegative",
        ),
        CheckConstraint(
            "price_minor IS NULL OR price_minor > 0",
            name="ck_submission_price_positive",
        ),
    )

class MerchantAssuranceCase(Base):
    __tablename__ = "merchant_assurance_cases"

    id: Mapped[int] = mapped_column(primary_key=True)

    verification_request_id: Mapped[int] = mapped_column(
        ForeignKey("verification_requests.id"),
        unique=True,
        index=True,
        nullable=False,
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class AssuranceObservation(Base):
    __tablename__ = "assurance_observations"

    id: Mapped[int] = mapped_column(primary_key=True)

    case_id: Mapped[int] = mapped_column(
        ForeignKey("merchant_assurance_cases.id"),
        index=True,
        nullable=False,
    )

    # IDENTITY, STOCK or PRICE
    check_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    # DIRECTORY_CALLBACK or AUTHORIZED_POS_EXPORT
    source_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )

    # CORROBORATES, CONTRADICTS or INCONCLUSIVE
    finding: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    reviewer_note: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "check_type IN ('IDENTITY', 'STOCK', 'PRICE')",
            name="ck_assurance_check_type",
        ),
        CheckConstraint(
            "source_type IN "
            "('DIRECTORY_CALLBACK', 'AUTHORIZED_POS_EXPORT')",
            name="ck_assurance_source_type",
        ),
        CheckConstraint(
            "finding IN "
            "('CORROBORATES', 'CONTRADICTS', 'INCONCLUSIVE')",
            name="ck_assurance_finding",
        ),
    )

class TechnicalCompatibilityReview(Base):
    __tablename__ = "technical_compatibility_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)

    case_id: Mapped[int] = mapped_column(
        ForeignKey("merchant_assurance_cases.id"),
        index=True,
        nullable=False,
    )

    device_input: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )

    charger_input: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )

    result: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    reasons: Mapped[list[str]] = mapped_column(
        JSON, nullable=False
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class AssuranceConflictReview(Base):
    __tablename__ = "assurance_conflict_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)

    case_id: Mapped[int] = mapped_column(
        ForeignKey("merchant_assurance_cases.id"),
        index=True,
        nullable=False,
    )

    check_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    investigation_note: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    evidence_reference: Mapped[str] = mapped_column(
        String(300), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(60),
        default="REVIEWED_PENDING_INDEPENDENT_PROOF",
        nullable=False,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "check_type IN ('IDENTITY', 'STOCK', 'PRICE')",
            name="ck_conflict_review_check_type",
        ),
    )

class MerchantAccount(Base):
    __tablename__ = "merchant_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(
        String(254), unique=True, nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        String(500), nullable=False
    )

    display_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class MerchantLoginSession(Base):
    __tablename__ = "merchant_login_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    merchant_account_id: Mapped[int] = mapped_column(
        ForeignKey("merchant_accounts.id"),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MerchantOwnershipClaim(Base):
    __tablename__ = "merchant_ownership_claims"

    id: Mapped[int] = mapped_column(primary_key=True)

    merchant_account_id: Mapped[int] = mapped_column(
        ForeignKey("merchant_accounts.id"),
        nullable=False,
        index=True,
    )

    # Google Place ID; do not persist Places name/address.
    place_id: Mapped[str] = mapped_column(
        String(300), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        String(40),
        default="PENDING_REVIEW",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    reviewer_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'PENDING_REVIEW',"
            "'OPERATOR_APPROVED_CLAIM',"
            "'REJECTED')",
            name="ck_merchant_ownership_status",
        ),
    )

class SimulationInventory(Base):
    __tablename__ = "simulation_inventory"

    sku: Mapped[str] = mapped_column(
        String(60), primary_key=True
    )

    initial_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    available_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "initial_quantity >= 0",
            name="ck_sim_inventory_initial",
        ),
        CheckConstraint(
            "available_quantity >= 0",
            name="ck_sim_inventory_nonnegative",
        ),
    )


class SimulationOrder(Base):
    __tablename__ = "simulation_orders"

    id: Mapped[int] = mapped_column(primary_key=True)

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
    )

    request_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False
    )

    # Immutable snapshot of the synthetic optimizer result.
    plan_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'RESERVED',"
            "'COMMITTED_SIMULATED',"
            "'CANCELLED',"
            "'EXPIRED')",
            name="ck_sim_order_status",
        ),
    )


class SimulationOrderEvent(Base):
    __tablename__ = "simulation_order_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    order_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_orders.id"),
        index=True,
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
