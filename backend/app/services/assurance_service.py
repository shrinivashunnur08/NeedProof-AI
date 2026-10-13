
from datetime import datetime, timezone

from app.db.models import (
    AssuranceObservation,
    MerchantAssuranceCase,
    MerchantEvidenceSubmission,
    VerificationRequest,
    utc_now,
)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def assess_assurance(
    case: MerchantAssuranceCase,
    request: VerificationRequest,
    submission: MerchantEvidenceSubmission,
    observations: list[AssuranceObservation],
    now: datetime | None = None,
) -> dict:
    now = now or utc_now()

    age_minutes = max(
        0,
        int(
            (now - as_utc(submission.submitted_at))
            .total_seconds() // 60
        ),
    )

    fresh = age_minutes <= 120

    def has(check_type: str, finding: str) -> bool:
        return any(
            observation.check_type == check_type
            and observation.finding == finding
            for observation in observations
        )

    identity_conflict = has("IDENTITY", "CONTRADICTS")

    identity_attested = (
        not identity_conflict
        and any(
            observation.check_type == "IDENTITY"
            and observation.source_type == "DIRECTORY_CALLBACK"
            and observation.finding == "CORROBORATES"
            for observation in observations
        )
    )

    identity_status = (
        "CONFLICT_RECORDED"
        if identity_conflict
        else "OPERATOR_ATTESTED"
        if identity_attested
        else "UNVERIFIED"
    )

    def claim_status(
        check_type: str,
        claim_present: bool,
    ) -> str:
        if has(check_type, "CONTRADICTS"):
            return "CONFLICT_RECORDED"

        if not claim_present:
            return "UNKNOWN"

        if not fresh:
            return "STALE_REPORT"

        if identity_conflict:
            return "BLOCKED_IDENTITY_CONFLICT"

        if (
            identity_attested
            and has(check_type, "CORROBORATES")
        ):
            return "OPERATOR_CORROBORATED"

        return "REPORTED_UNVERIFIED"

    stock_status = claim_status("STOCK", True)
    price_status = claim_status(
        "PRICE",
        submission.price_minor is not None,
    )

    if submission.stock_quantity == 0:
        if stock_status != "CONFLICT_RECORDED":
            stock_status = "REPORTED_ZERO_STOCK"

    any_conflict = any(
        observation.finding == "CONTRADICTS"
        for observation in observations
    )

    if any_conflict:
        next_action = {
            "code": "RESOLVE_CONFLICT",
            "label": "Investigate the contradictory evidence",
        }

    elif not identity_attested:
        next_action = {
            "code": "ESTABLISH_INDEPENDENT_CONTACT",
            "label": (
                "Confirm business authority using an "
                "independently sourced contact channel"
            ),
        }

    elif submission.stock_quantity == 0:
        next_action = {
            "code": "FIND_ALTERNATIVE",
            "label": "Find an alternative offer",
        }

    elif not fresh:
        next_action = {
            "code": "REFRESH_MERCHANT_REPORT",
            "label": "Obtain a fresh stock and price report",
        }

    elif stock_status != "OPERATOR_CORROBORATED":
        next_action = {
            "code": "CORROBORATE_STOCK",
            "label": "Obtain a corroborating stock observation",
        }

    elif submission.price_minor is None:
        next_action = {
            "code": "OBTAIN_PRICE",
            "label": "Obtain the merchant's selling price",
        }

    elif price_status != "OPERATOR_CORROBORATED":
        next_action = {
            "code": "CORROBORATE_PRICE",
            "label": "Obtain a corroborating price observation",
        }

    else:
        next_action = {
            "code": "VERIFY_COMPATIBILITY_AND_DELIVERY",
            "label": (
                "Verify device compatibility and "
                "deadline-specific fulfillment"
            ),
        }

    return {
        "mode": "OPERATOR_ASSURANCE_REVIEW",
        "case_id": case.id,
        "request_id": request.id,
        "place_id": request.place_id,
        "product_query": request.product_query,
        "reported_product": submission.product_name,
        "report_age_minutes": age_minutes,
        "report_freshness": (
            "RECENT_REPORT" if fresh else "STALE_REPORT"
        ),
        "status": (
            "CONFLICT_RECORDED"
            if any_conflict
            else "OPERATOR_REVIEWED"
            if observations
            else "REPORTED_UNVERIFIED"
        ),
        "field_status": {
            "merchant_identity": identity_status,
            "stock": stock_status,
            "price": price_status,
            "compatibility": "NOT_VERIFIED",
            "delivery": "NOT_VERIFIED",
        },
        "observations": [
            {
                "id": observation.id,
                "check_type": observation.check_type,
                "source_type": observation.source_type,
                "finding": observation.finding,
                "reviewer_note": observation.reviewer_note,
                "recorded_at": observation.recorded_at,
            }
            for observation in observations
        ],
        "recommended_next_action": next_action,
        "purchase_allowed": False,
        "independently_authenticated_merchant": False,
        "notice": (
            "All review observations are local operator "
            "attestations. They do not provide independently "
            "authenticated merchant identity or authorize "
            "payment, reservation or purchase."
        ),
    }
