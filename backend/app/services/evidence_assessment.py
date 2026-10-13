
from datetime import datetime, timezone

from app.db.models import (
    MerchantEvidenceSubmission,
    VerificationRequest,
    utc_now,
)

# A demonstration policy, not an industry-standard
# guarantee of inventory freshness.
REPORT_FRESHNESS_MINUTES = 120


def aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def assess_evidence(
    record: VerificationRequest,
    submission: MerchantEvidenceSubmission | None,
    now: datetime | None = None,
) -> dict:
    now = now or utc_now()

    if submission is None:
        expired = now > aware(record.expires_at)

        return {
            "request_id": record.id,
            "mode": "EVIDENCE_READINESS",
            "status": (
                "INVITATION_EXPIRED"
                if expired
                else "AWAITING_RESPONSE"
            ),
            "reported_fields": 0,
            "total_fields": 4,
            "report_age_minutes": None,
            "freshness": "NOT_REPORTED",
            "merchant_identity_verified": False,
            "eligible_for_commitment": False,
            "checks": [],
            "recommended_next_action": {
                "code": (
                    "CREATE_NEW_INVITATION"
                    if expired
                    else "REQUEST_MERCHANT_RESPONSE"
                ),
                "label": (
                    "Create a new invitation"
                    if expired
                    else "Obtain an authorized merchant response"
                ),
            },
            "notice": (
                "No product evidence has been received. "
                "Do not infer price, stock, or compatibility."
            ),
        }

    age_minutes = max(
        0,
        int(
            (now - aware(submission.submitted_at))
            .total_seconds() // 60
        ),
    )

    freshness = (
        "RECENTLY_REPORTED"
        if age_minutes <= REPORT_FRESHNESS_MINUTES
        else "STALE_REPORT"
    )

    has_price = submission.price_minor is not None
    has_specs = bool(
        (submission.specification_notes or "").strip()
    )
    has_delivery = submission.delivery_available is not None

    # Stock quantity is required by our merchant form,
    # so a zero count is still a reported observation.
    reported_fields = (
        1
        + int(has_price)
        + int(has_specs)
        + int(has_delivery)
    )

    checks = [
        {
            "field": "Merchant identity",
            "status": "UNVERIFIED",
            "detail": (
                "Invitation possession and a checkbox "
                "do not prove business ownership."
            ),
        },
        {
            "field": "Stock availability",
            "status": (
                "REPORTED_ZERO"
                if submission.stock_quantity == 0
                else "REPORTED_UNVERIFIED"
            ),
            "detail": (
                f"{submission.stock_quantity} unit(s) "
                "reported by the respondent."
            ),
        },
        {
            "field": "Selling price",
            "status": (
                "REPORTED_UNVERIFIED"
                if has_price
                else "UNKNOWN"
            ),
            "detail": (
                f"INR {submission.price_minor / 100:.2f} "
                "quoted by the respondent."
                if has_price
                else "No selling price supplied."
            ),
        },
        {
            "field": "Compatibility",
            "status": "NOT_VERIFIED",
            "detail": (
                "Published or reported specifications "
                "do not establish device compatibility."
            ),
        },
        {
            "field": "Delivery feasibility",
            "status": (
                "REPORTED_YES_UNVERIFIED"
                if submission.delivery_available is True
                else "REPORTED_NO"
                if submission.delivery_available is False
                else "UNKNOWN"
            ),
            "detail": (
                "Delivery response is not an independently "
                "verified deadline commitment."
            ),
        },
    ]

    if submission.stock_quantity == 0:
        next_action = {
            "code": "FIND_ALTERNATIVE_OFFER",
            "label": (
                "Find another offer; respondent reports zero stock"
            ),
        }

    elif freshness == "STALE_REPORT":
        next_action = {
            "code": "REFRESH_MERCHANT_EVIDENCE",
            "label": (
                "Request a fresh stock and price confirmation"
            ),
        }

    elif not has_price:
        next_action = {
            "code": "REQUEST_PRICE",
            "label": "Obtain the current selling price",
        }

    elif not has_specs:
        next_action = {
            "code": "REQUEST_PRODUCT_SPECIFICATIONS",
            "label": (
                "Obtain the precise product model and specifications"
            ),
        }

    elif not has_delivery:
        next_action = {
            "code": "CONFIRM_DELIVERY",
            "label": (
                "Obtain a delivery feasibility response"
            ),
        }

    else:
        next_action = {
            "code": "VERIFY_MERCHANT_IDENTITY",
            "label": (
                "Verify the respondent's business authority"
            ),
        }

    return {
        "request_id": record.id,
        "mode": "EVIDENCE_READINESS",
        "status": "REPORTED_UNVERIFIED",
        "reported_fields": reported_fields,
        "total_fields": 4,
        "report_age_minutes": age_minutes,
        "freshness": freshness,
        "merchant_identity_verified": False,
        "eligible_for_commitment": False,
        "checks": checks,
        "recommended_next_action": next_action,
        "notice": (
            "This assessment checks evidence completeness "
            "and freshness, not its truth. An invitation "
            "response is not independent merchant authentication."
        ),
    }
