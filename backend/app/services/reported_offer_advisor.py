
from dataclasses import dataclass
from datetime import datetime

from ortools.sat.python import cp_model

from app.db.models import utc_now
from app.services.evidence_assessment import aware


@dataclass(frozen=True)
class ReportedOffer:
    request_id: int
    place_id: str
    product_query: str
    product_name: str | None
    stock_quantity: int | None
    price_minor: int | None
    delivery_available: bool | None
    submitted_at: datetime | None
    invitation_expired: bool


def normalized_query(value: str) -> str:
    return " ".join(value.casefold().split())


def plan_reported_offers(
    offers: list[ReportedOffer],
    *,
    budget_minor: int,
    quantity: int,
    delivery_required: bool,
    now: datetime | None = None,
) -> dict:
    """
    Conditional comparison of merchant-submitted claims.

    Only submitted prices and quantities are considered.
    No claim is independently verified.
    Delivery fees and taxes are not known.
    No real purchase or reservation is permitted.
    """

    if not offers:
        raise ValueError("At least one invitation is required.")

    if budget_minor <= 0 or quantity <= 0:
        raise ValueError("Budget and quantity must be positive.")

    now = now or utc_now()
    target_query = offers[0].product_query

    comparable = []
    excluded = []

    for offer in offers:
        reasons = []
        warnings = [
            "MERCHANT_IDENTITY_UNVERIFIED",
            "STOCK_AND_PRICE_MERCHANT_REPORTED",
            "COMPATIBILITY_UNVERIFIED",
            "DELIVERY_DEADLINE_NOT_VERIFIED",
            "FULFILLMENT_FEES_UNKNOWN",
        ]

        if (
            normalized_query(offer.product_query)
            != normalized_query(target_query)
        ):
            reasons.append("DIFFERENT_PRODUCT_REQUEST")

        if offer.invitation_expired:
            reasons.append("INVITATION_EXPIRED")

        if (
            offer.price_minor is None
            or offer.stock_quantity is None
            or offer.submitted_at is None
        ):
            reasons.append("NO_COMPLETE_PRICE_STOCK_REPORT")
            age_minutes = None
        else:
            age_minutes = max(
                0,
                int(
                    (now - aware(offer.submitted_at))
                    .total_seconds() // 60
                ),
            )

            if offer.stock_quantity < quantity:
                reasons.append("REPORTED_STOCK_INSUFFICIENT")

            if offer.price_minor <= 0:
                reasons.append("INVALID_REPORTED_PRICE")

            elif offer.price_minor * quantity > budget_minor:
                reasons.append("ITEM_SUBTOTAL_EXCEEDS_BUDGET")

            if age_minutes > 120:
                warnings.append("REPORT_OLDER_THAN_120_MINUTES")

        if delivery_required:
            if offer.delivery_available is False:
                reasons.append("MERCHANT_REPORTED_NO_DELIVERY")

            elif offer.delivery_available is None:
                warnings.append("DELIVERY_NOT_CONFIRMED")

            else:
                warnings.append("DELIVERY_REPORTED_NOT_VERIFIED")

        report = {
            "request_id": offer.request_id,
            "place_id": offer.place_id,
            "product_query": offer.product_query,
            "product_name": offer.product_name,
            "price_minor": offer.price_minor,
            "stock_quantity": offer.stock_quantity,
            "report_age_minutes": age_minutes,
            "delivery_available": offer.delivery_available,
            "warnings": warnings,
            "purchase_eligible": False,
        }

        if reasons:
            excluded.append({
                **report,
                "reasons": reasons,
            })
        else:
            comparable.append(report)

    if not comparable:
        return {
            "mode": "REAL_REPORTED_ADVISORY",
            "status": "NO_COMPARABLE_REPORTS",
            "target_product": target_query,
            "purchase_allowed": False,
            "selected": None,
            "alternatives": [],
            "excluded": excluded,
            "budget_minor": budget_minor,
            "quantity": quantity,
            "total_including_fees_minor": None,
            "notice": (
                "No comparable reported offer satisfies the "
                "preliminary filters. No purchase is authorized."
            ),
        }

    model = cp_model.CpModel()

    variables = [
        model.new_bool_var(f"choose_{i}")
        for i in range(len(comparable))
    ]

    # Select exactly one provisional offer.
    model.add(sum(variables) == 1)

    # Minimize reported item subtotal.
    # Secondary deterministic tie-break by candidate order.
    scale = len(comparable) + 1

    model.minimize(
        sum(
            (
                int(offer["price_minor"])
                * quantity * scale + i
            ) * variables[i]
            for i, offer in enumerate(comparable)
        )
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 3.0
    solver.parameters.num_search_workers = 1

    result = solver.solve(model)

    if result not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            "The advisory optimizer could not produce a result."
        )

    selected = next(
        offer
        for i, offer in enumerate(comparable)
        if solver.value(variables[i]) == 1
    )

    alternatives = [
        offer
        for offer in comparable
        if offer["request_id"] != selected["request_id"]
    ]

    selected = {
        **selected,
        "reported_item_subtotal_minor": (
            int(selected["price_minor"]) * quantity
        ),
    }

    return {
        "mode": "REAL_REPORTED_ADVISORY",
        "status": (
            "LOWEST_REPORTED_ITEM_PRICE"
            if result == cp_model.OPTIMAL
            else "CONDITIONAL_OFFER_FOUND"
        ),
        "target_product": target_query,
        "purchase_allowed": False,
        "selected": selected,
        "alternatives": alternatives,
        "excluded": excluded,
        "budget_minor": budget_minor,
        "quantity": quantity,
        "total_including_fees_minor": None,
        "headroom_before_unknown_fees_minor": (
            budget_minor
            - selected["reported_item_subtotal_minor"]
        ),
        "notice": (
            "This is a conditional comparison of submitted "
            "item prices, not a verified recommendation. "
            "Merchant identity, availability, compatibility, "
            "delivery deadline and final charges require "
            "further evidence. No order was created."
        ),
    }
