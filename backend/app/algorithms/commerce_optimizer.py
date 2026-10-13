
from dataclasses import dataclass

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class BasketItem:
    item_id: str
    name: str
    quantity: int = 1


@dataclass(frozen=True)
class Merchant:
    merchant_id: str
    name: str
    fulfillment_fee_minor: int


@dataclass(frozen=True)
class ProductOffer:
    sku: str
    item_id: str
    merchant_id: str
    product_name: str
    unit_price_minor: int
    stock_on_hand: int
    delivery_eta_minutes: int

    merchant_verified: bool
    stock_verified: bool
    compatibility_verified: bool
    delivery_verified: bool

    evidence_source: str


def optimize_basket(
    items: list[BasketItem],
    merchants: list[Merchant],
    offers: list[ProductOffer],
    *,
    budget_minor: int,
    deadline_minutes: int,
    max_merchants: int,
) -> dict:
    """
    Select one offer for every requested basket line.

    Hard constraints:
      - Each item must be fulfilled entirely.
      - Evidence requirements must pass.
      - Sufficient simulated stock must exist.
      - Every offer must meet the deadline.
      - Total item + merchant fees <= budget.
      - Number of merchants <= max_merchants.

    Objective: minimize total monetary cost.
    Secondary tie-break: use fewer merchants.

    This prototype accepts only synthetic verified
    fixtures. Real merchant reports are not eligible.
    """

    if (
        budget_minor <= 0
        or deadline_minutes < 0
        or max_merchants < 1
    ):
        raise ValueError("Invalid optimization constraints.")

    if not items:
        raise ValueError("At least one basket item is required.")

    item_map = {item.item_id: item for item in items}
    merchant_map = {
        merchant.merchant_id: merchant
        for merchant in merchants
    }

    if len(item_map) != len(items):
        raise ValueError("Duplicate basket item IDs.")

    if len(merchant_map) != len(merchants):
        raise ValueError("Duplicate merchant IDs.")

    if len({offer.sku for offer in offers}) != len(offers):
        raise ValueError("Duplicate offer SKUs.")

    if any(item.quantity <= 0 for item in items):
        raise ValueError("Basket quantities must be positive.")

    if any(
        merchant.fulfillment_fee_minor < 0
        for merchant in merchants
    ):
        raise ValueError("Merchant fees cannot be negative.")

    eligible: list[ProductOffer] = []
    exclusions = []

    for offer in offers:
        if (
            offer.item_id not in item_map
            or offer.merchant_id not in merchant_map
        ):
            raise ValueError(
                f"Invalid item or merchant reference: {offer.sku}"
            )

        if (
            offer.unit_price_minor < 0
            or offer.stock_on_hand < 0
            or offer.delivery_eta_minutes < 0
        ):
            raise ValueError("Negative offer values are invalid.")

        reasons = []
        item = item_map[offer.item_id]

        if offer.evidence_source != "SIMULATION_VERIFIED":
            reasons.append("UNVERIFIED_EVIDENCE_SOURCE")

        if not offer.merchant_verified:
            reasons.append("MERCHANT_IDENTITY_NOT_VERIFIED")

        if not offer.stock_verified:
            reasons.append("STOCK_NOT_VERIFIED")

        if offer.stock_on_hand < item.quantity:
            reasons.append("INSUFFICIENT_STOCK")

        if not offer.compatibility_verified:
            reasons.append("COMPATIBILITY_NOT_VERIFIED")

        if not offer.delivery_verified:
            reasons.append("DELIVERY_NOT_VERIFIED")

        if offer.delivery_eta_minutes > deadline_minutes:
            reasons.append("DEADLINE_NOT_MET")

        if reasons:
            exclusions.append({
                "sku": offer.sku,
                "item_id": offer.item_id,
                "merchant": merchant_map[
                    offer.merchant_id
                ].name,
                "reasons": reasons,
            })
        else:
            eligible.append(offer)

    def infeasible(
        reason: str,
        blocked_items: list[str],
    ) -> dict:
        return {
            "mode": "SYNTHETIC_OPTIMIZATION",
            "status": "INFEASIBLE",
            "reason": reason,
            "blocked_items": blocked_items,
            "selected_offers": [],
            "used_merchants": [],
            "totals": None,
            "excluded_offers": exclusions,
            "eligible_offer_count": len(eligible),
            "notice": (
                "Synthetic scenario only. No real order "
                "or inventory reservation was created."
            ),
        }

    blocked = [
        item.item_id
        for item in items
        if not any(
            offer.item_id == item.item_id
            for offer in eligible
        )
    ]

    if blocked:
        return infeasible(
            "NO_ELIGIBLE_OFFER_FOR_REQUIRED_ITEM",
            blocked,
        )

    model = cp_model.CpModel()

    selected = {
        offer.sku: model.new_bool_var(
            f"select_{offer.sku}"
        )
        for offer in eligible
    }

    participating_merchants = sorted({
        offer.merchant_id
        for offer in eligible
    })

    merchant_used = {
        merchant_id: model.new_bool_var(
            f"use_{merchant_id}"
        )
        for merchant_id in participating_merchants
    }

    # Exactly one offer for every basket item.
    for item in items:
        matching = [
            selected[offer.sku]
            for offer in eligible
            if offer.item_id == item.item_id
        ]

        model.add(sum(matching) == 1)

    # Charge each merchant's fixed fee once,
    # even if several products come from that merchant.
    for merchant_id in participating_merchants:
        merchant_offers = [
            selected[offer.sku]
            for offer in eligible
            if offer.merchant_id == merchant_id
        ]

        for offer_var in merchant_offers:
            model.add(
                offer_var <= merchant_used[merchant_id]
            )

        model.add(
            merchant_used[merchant_id]
            <= sum(merchant_offers)
        )

    model.add(
        sum(merchant_used.values()) <= max_merchants
    )

    product_cost = sum(
        offer.unit_price_minor
        * item_map[offer.item_id].quantity
        * selected[offer.sku]
        for offer in eligible
    )

    fulfillment_cost = sum(
        merchant_map[merchant_id].fulfillment_fee_minor
        * merchant_used[merchant_id]
        for merchant_id in participating_merchants
    )

    total_cost = product_cost + fulfillment_cost

    model.add(total_cost <= budget_minor)

    # Monetary cost is always the primary objective.
    # Fewer merchants break ties when cost is equal.
    tie_break_scale = len(merchants) + 1

    model.minimize(
        total_cost * tie_break_scale
        + sum(merchant_used.values())
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    solver.parameters.num_search_workers = 1

    status = solver.solve(model)

    if status == cp_model.INFEASIBLE:
        return infeasible(
            "NO_COMBINATION_SATISFIES_CONSTRAINTS",
            [],
        )

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            **infeasible("SOLVER_DID_NOT_RETURN_A_PLAN", []),
            "status": solver.status_name(status),
        }

    chosen = [
        offer
        for offer in eligible
        if solver.value(selected[offer.sku]) == 1
    ]

    used_ids = [
        merchant_id
        for merchant_id in participating_merchants
        if solver.value(merchant_used[merchant_id]) == 1
    ]

    subtotal_minor = sum(
        offer.unit_price_minor
        * item_map[offer.item_id].quantity
        for offer in chosen
    )

    fees_minor = sum(
        merchant_map[mid].fulfillment_fee_minor
        for mid in used_ids
    )

    total_minor = subtotal_minor + fees_minor

    return {
        "mode": "SYNTHETIC_OPTIMIZATION",
        "status": solver.status_name(status),
        "reason": None,
        "blocked_items": [],
        "selected_offers": [
            {
                "sku": offer.sku,
                "item_id": offer.item_id,
                "item_name": item_map[
                    offer.item_id
                ].name,
                "merchant": merchant_map[
                    offer.merchant_id
                ].name,
                "quantity": item_map[
                    offer.item_id
                ].quantity,
                "unit_price_minor": offer.unit_price_minor,
                "line_total_minor": (
                    offer.unit_price_minor
                    * item_map[offer.item_id].quantity
                ),
                "delivery_eta_minutes": (
                    offer.delivery_eta_minutes
                ),
                "evidence_source": offer.evidence_source,
            }
            for offer in chosen
        ],
        "used_merchants": [
            {
                "name": merchant_map[mid].name,
                "fulfillment_fee_minor": (
                    merchant_map[mid].fulfillment_fee_minor
                ),
            }
            for mid in used_ids
        ],
        "totals": {
            "subtotal_minor": subtotal_minor,
            "fulfillment_fees_minor": fees_minor,
            "total_minor": total_minor,
            "budget_minor": budget_minor,
            "remaining_minor": budget_minor - total_minor,
        },
        "excluded_offers": exclusions,
        "eligible_offer_count": len(eligible),
        "notice": (
            "This is an optimal synthetic basket if status "
            "is OPTIMAL. It does not represent real "
            "merchant inventory or a committed purchase."
        ),
    }
