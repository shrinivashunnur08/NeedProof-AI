
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator


MAX_REPORT_AGE_MINUTES = 120


class CustomerRequirements(BaseModel):
    product_query: str = Field(min_length=3, max_length=250)
    budget_minor: int | None = Field(
        default=None, ge=0, le=100_000_000
    )
    required_quantity: int = Field(default=1, ge=1, le=20)
    delivery_required: bool = False


class ReportedSubmission(BaseModel):
    product_name: str
    stock_quantity: int = Field(ge=0, le=1_000_000)
    price_minor: int | None = Field(default=None, ge=1)
    currency: str = "INR"
    delivery_available: bool | None = None
    submitted_at: datetime | None = None


class ReadinessAssessment(BaseModel):
    status: str = "REPORTED_UNVERIFIED"
    freshness: str = "UNKNOWN"
    eligible_for_commitment: bool = False


class MerchantReport(BaseModel):
    product_query: str
    status: str
    submission: ReportedSubmission | None = None
    assessment: ReadinessAssessment | None = None


class CandidateMerchant(BaseModel):
    place_id: str = Field(min_length=3, max_length=300)
    name: str = Field(min_length=1, max_length=250)
    evidence: MerchantReport | None = None


class ReplanInput(BaseModel):
    customer: CustomerRequirements
    merchants: list[CandidateMerchant] = Field(
        default_factory=list, max_length=25
    )

    @model_validator(mode="after")
    def unique_merchants(self):
        identifiers = [
            merchant.place_id for merchant in self.merchants
        ]

        if len(identifiers) != len(set(identifiers)):
            raise ValueError(
                "Duplicate merchant Place IDs are not allowed."
            )

        return self


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def evaluate_replan(
    payload: ReplanInput,
    now: datetime | None = None,
) -> dict:
    now = to_utc(now or datetime.now(timezone.utc))
    customer = payload.customer
    candidates = []

    for merchant in payload.merchants:
        errors: list[str] = []
        gaps: list[str] = []
        subtotal_minor: int | None = None

        evidence = merchant.evidence
        submission = evidence.submission if evidence else None

        if evidence is None:
            state = "AWAITING_EVIDENCE"
            gaps.append("MERCHANT_NOT_CONTACTED")

        elif evidence.status == "EXPIRED" and submission is None:
            state = "EXCLUDED"
            errors.append("INVITATION_EXPIRED")

        elif submission is None:
            state = "AWAITING_EVIDENCE"
            gaps.append("MERCHANT_RESPONSE_MISSING")

        else:
            if normalize(evidence.product_query) != normalize(
                customer.product_query
            ):
                errors.append("PRODUCT_REQUEST_MISMATCH")

            if evidence.status != "REPORTED_UNVERIFIED":
                errors.append("SUBMISSION_STATUS_UNEXPECTED")

            if submission.stock_quantity < customer.required_quantity:
                errors.append("REPORTED_STOCK_INSUFFICIENT")

            if submission.currency.upper() != "INR":
                errors.append("CURRENCY_NOT_INR")

            if submission.price_minor is None:
                gaps.append("PRICE_MISSING")
            else:
                subtotal_minor = (
                    submission.price_minor * customer.required_quantity
                )

                if (
                    customer.budget_minor is not None
                    and subtotal_minor > customer.budget_minor
                ):
                    errors.append("ITEM_SUBTOTAL_EXCEEDS_BUDGET")

            if customer.budget_minor is None:
                gaps.append("BUDGET_NOT_ESTABLISHED")

            if (
                customer.delivery_required
                and submission.delivery_available is False
            ):
                errors.append("DELIVERY_REPORTED_UNAVAILABLE")

            if (
                customer.delivery_required
                and submission.delivery_available is None
            ):
                gaps.append("DELIVERY_NOT_CONFIRMED")

            if submission.submitted_at is None:
                gaps.append("SUBMISSION_TIMESTAMP_MISSING")
            else:
                age = now - to_utc(submission.submitted_at)

                if age < -timedelta(minutes=5):
                    errors.append("SUBMISSION_TIME_INVALID")
                elif age > timedelta(
                    minutes=MAX_REPORT_AGE_MINUTES
                ):
                    errors.append("STALE_SUBMISSION")

            assessment = evidence.assessment

            if assessment is None:
                gaps.append("READINESS_ASSESSMENT_REQUIRED")

            else:
                freshness = assessment.freshness.upper()

                if "STALE" in freshness:
                    errors.append("ASSESSMENT_REPORTS_STALE")
                elif freshness != "RECENT_REPORT":
                    gaps.append("FRESHNESS_NOT_ASSESSED")

            gaps.extend([
                "MERCHANT_IDENTITY_NOT_AUTHENTICATED",
                "COMPATIBILITY_NOT_INDEPENDENTLY_VERIFIED",
                "FULFILLMENT_FEES_NOT_CONFIRMED",
            ])

            if errors:
                state = "EXCLUDED"
            elif any(
                code in gaps
                for code in [
                    "PRICE_MISSING",
                    "BUDGET_NOT_ESTABLISHED",
                    "SUBMISSION_TIMESTAMP_MISSING",
                    "READINESS_ASSESSMENT_REQUIRED",
                    "FRESHNESS_NOT_ASSESSED",
                ]
            ):
                state = "NEEDS_REVIEW"
            else:
                state = "PROVISIONAL"

        candidates.append({
            "place_id": merchant.place_id,
            "name": merchant.name,
            "status": state,
            "reported_subtotal_minor": subtotal_minor,
            "reasons": sorted(set(errors)),
            "evidence_gaps": sorted(set(gaps)),
        })

    provisional = sorted(
        [
            candidate for candidate in candidates
            if candidate["status"] == "PROVISIONAL"
        ],
        key=lambda item: (
            item["reported_subtotal_minor"],
            item["place_id"],
        ),
    )

    selected = provisional[0] if provisional else None

    if not payload.merchants:
        next_action = "DISCOVER_MERCHANTS"

    elif selected is not None:
        next_action = "VERIFY_IDENTITY_COMPATIBILITY_AND_DELIVERY"

    elif any(
        candidate["status"] == "NEEDS_REVIEW"
        for candidate in candidates
    ):
        next_action = "REVIEW_MISSING_EVIDENCE"

    elif any(
        candidate["status"] == "AWAITING_EVIDENCE"
        for candidate in candidates
    ):
        next_action = "REQUEST_MERCHANT_RESPONSES"

    else:
        next_action = "FIND_OR_REFRESH_ALTERNATIVE_OFFERS"

    return {
        "mode": "CLIENT_SNAPSHOT_REPLANNING",
        "decision_status": (
            "PROVISIONAL_OFFER_FOUND"
            if selected
            else "NO_PROVISIONAL_OFFER"
        ),
        "selected": selected,
        "candidates": candidates,
        "evaluated_at": now.isoformat(),
        "recommended_next_action": next_action,
        "purchase_allowed": False,
        "notice": (
            "The evaluator uses a client-provided snapshot "
            "of merchant-reported claims. No merchant identity, "
            "product compatibility, final delivery cost or "
            "actual inventory is independently authenticated."
        ),
    }
