"""14A.2: evidence-separated multi-line basket planning.

All selected offers are explicitly synthetic test fixtures. Merchant-reported or
source-derived offers are NEVER transformed into verified product inventory.
Uses the existing OR-Tools solver when installed; small offline fixtures have
an exact bounded enumeration fallback to avoid adding production dependencies.
No I/O, network, credentials, persistence, checkout, or external API calls.
"""
from __future__ import annotations

from itertools import product
from math import prod
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Source = Literal[
    "SIMULATION_VERIFIED", "MERCHANT_REPORTED_UNVERIFIED",
    "USER_DOCUMENT_UNVERIFIED", "UNKNOWN",
]


class Item14A2(BaseModel):
    item_id: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=2, max_length=120)
    quantity: int = Field(default=1, ge=1, le=20)


class Merchant14A2(BaseModel):
    merchant_id: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=2, max_length=120)
    fulfillment_fee_minor: int = Field(ge=0, le=5_000_000)


class Offer14A2(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    item_id: str = Field(min_length=1, max_length=60)
    merchant_id: str = Field(min_length=1, max_length=60)
    product_name: str = Field(min_length=2, max_length=120)
    unit_price_minor: int = Field(ge=1, le=100_000_000)
    stock_on_hand: int = Field(ge=0, le=100_000)
    delivery_eta_minutes: int = Field(ge=0, le=100_000)
    merchant_verified: bool = False
    stock_verified: bool = False
    compatibility_verified: bool = False
    delivery_verified: bool = False
    evidence_source: Source = "UNKNOWN"
    evidence_reference: str | None = Field(default=None, max_length=160)


class BasketPlan14A2(BaseModel):
    items: list[Item14A2] = Field(min_length=1, max_length=6)
    merchants: list[Merchant14A2] = Field(min_length=1, max_length=8)
    offers: list[Offer14A2] = Field(min_length=1, max_length=30)
    budget_minor: int = Field(ge=1, le=100_000_000)
    deadline_minutes: int = Field(ge=0, le=1440)
    max_merchants: int = Field(ge=1, le=8)
    hypothetical_scenario_acknowledged: Literal[True]

    @model_validator(mode="after")
    def unique_references(self):
        for section, ids in (
            ("item", [x.item_id for x in self.items]),
            ("merchant", [x.merchant_id for x in self.merchants]),
            ("offer", [x.sku for x in self.offers]),
        ):
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {section} IDs are not allowed")
        item_ids = {x.item_id for x in self.items}
        merchant_ids = {x.merchant_id for x in self.merchants}
        if any(o.item_id not in item_ids or o.merchant_id not in merchant_ids for o in self.offers):
            raise ValueError("Every offer must refer to a supplied item and merchant")
        if self.max_merchants > len(self.merchants):
            raise ValueError("max_merchants exceeds number of available merchants")
        return self


def _eligible_checks(o: Offer14A2, quantity: int, deadline: int) -> list[str]:
    problems = []
    if o.evidence_source != "SIMULATION_VERIFIED":
        problems.append("NOT_A_VERIFIED_SYNTHETIC_FIXTURE")
    if not o.merchant_verified:
        problems.append("MERCHANT_IDENTITY_NOT_VERIFIED")
    if not o.stock_verified:
        problems.append("STOCK_NOT_VERIFIED")
    if o.stock_on_hand < quantity:
        problems.append("INSUFFICIENT_REPORTED_OR_SIMULATED_STOCK")
    if not o.compatibility_verified:
        problems.append("COMPATIBILITY_NOT_VERIFIED")
    if not o.delivery_verified:
        problems.append("DELIVERY_NOT_VERIFIED")
    if o.delivery_eta_minutes > deadline:
        problems.append("DEADLINE_NOT_MET")
    return problems


def _exact_bounded(payload: BasketPlan14A2, eligible: list[Offer14A2], exclusions: list[dict]) -> dict:
    """A bounded, exhaustive fallback; for large scenarios require OR-Tools."""
    per_item = [[o for o in eligible if o.item_id == i.item_id] for i in payload.items]
    blocked = [i.item_id for i, options in zip(payload.items, per_item) if not options]

    def impossible(reason, blocked_items):
        return {
            "mode": "SYNTHETIC_OPTIMIZATION", "status": "INFEASIBLE", "reason": reason,
            "blocked_items": blocked_items, "selected_offers": [], "used_merchants": [],
            "totals": None, "excluded_offers": exclusions, "eligible_offer_count": len(eligible),
            "notice": "Synthetic scenario only. No actual stock or purchase confirmed.",
        }
    if blocked:
        return impossible("NO_ELIGIBLE_OFFER_FOR_REQUIRED_ITEM", blocked)
    if prod(len(x) for x in per_item) > 100_000:
        return {**impossible("INSTALL_OR_TOOLS_FOR_LARGE_BASKETS", []), "status": "SOLVER_UNAVAILABLE"}
    items = {i.item_id: i for i in payload.items}
    merchants = {m.merchant_id: m for m in payload.merchants}
    best = None
    for chosen in product(*per_item):
        mids = {o.merchant_id for o in chosen}
        if len(mids) > payload.max_merchants:
            continue
        subtotal = sum(o.unit_price_minor * items[o.item_id].quantity for o in chosen)
        fees = sum(merchants[mid].fulfillment_fee_minor for mid in mids)
        total = subtotal + fees
        if total > payload.budget_minor:
            continue
        key = (total, len(mids), tuple(o.sku for o in chosen))
        if best is None or key < best[0]:
            best = (key, chosen, sorted(mids), subtotal, fees)
    if best is None:
        return impossible("NO_COMBINATION_SATISFIES_CONSTRAINTS", [])
    _, chosen, mids, subtotal, fees = best
    return {
        "mode": "SYNTHETIC_OPTIMIZATION", "status": "OPTIMAL", "reason": None,
        "blocked_items": [], "selected_offers": [
            {"sku": o.sku, "item_id": o.item_id, "item_name": items[o.item_id].name,
             "merchant": merchants[o.merchant_id].name, "quantity": items[o.item_id].quantity,
             "unit_price_minor": o.unit_price_minor,
             "line_total_minor": o.unit_price_minor * items[o.item_id].quantity,
             "delivery_eta_minutes": o.delivery_eta_minutes, "evidence_source": o.evidence_source}
            for o in chosen
        ],
        "used_merchants": [
            {"name": merchants[mid].name, "fulfillment_fee_minor": merchants[mid].fulfillment_fee_minor}
            for mid in mids
        ],
        "totals": {"subtotal_minor": subtotal, "fulfillment_fees_minor": fees,
                   "total_minor": subtotal + fees, "budget_minor": payload.budget_minor,
                   "remaining_minor": payload.budget_minor - subtotal - fees},
        "excluded_offers": exclusions, "eligible_offer_count": len(eligible),
        "notice": "An exact optimal combination for the synthetic fixture; not real inventory.",
    }


def evaluate_basket_14a2(payload: BasketPlan14A2) -> dict:
    quantities = {i.item_id: i.quantity for i in payload.items}
    merchant_names = {m.merchant_id: m.name for m in payload.merchants}
    eligible, excluded, backlog = [], [], []
    for o in payload.offers:
        issues = _eligible_checks(o, quantities[o.item_id], payload.deadline_minutes)
        if issues:
            excluded.append({"sku": o.sku, "item_id": o.item_id,
                             "merchant": merchant_names[o.merchant_id], "reasons": issues})
        else:
            eligible.append(o)
        if o.evidence_source != "SIMULATION_VERIFIED":
            backlog.append({
                "sku": o.sku, "item_id": o.item_id,
                "merchant": merchant_names[o.merchant_id],
                "evidence_source": o.evidence_source,
                "evidence_reference": o.evidence_reference,
                "reported_price_minor": o.unit_price_minor,
                "required_checks": issues,
            })

    # Defer importing OR-Tools until required. The isolated Cloud Run API must
    # still start with new routes gated OFF, even if OR-Tools is absent.
    try:
        from app.algorithms.commerce_optimizer import BasketItem, Merchant, ProductOffer, optimize_basket
    except ModuleNotFoundError as exc:
        if exc.name != "ortools" and not (exc.name or "").startswith("ortools."):
            raise
        engine = "EXACT_BOUNDED_ENUMERATOR"
        solved = _exact_bounded(payload, eligible, excluded)
    else:
        engine = "OR_TOOLS_CP_SAT"
        solved = optimize_basket(
            [BasketItem(i.item_id, i.name, i.quantity) for i in payload.items],
            [Merchant(m.merchant_id, m.name, m.fulfillment_fee_minor) for m in payload.merchants],
            [ProductOffer(o.sku, o.item_id, o.merchant_id, o.product_name,
                          o.unit_price_minor, o.stock_on_hand, o.delivery_eta_minutes,
                          o.merchant_verified, o.stock_verified, o.compatibility_verified,
                          o.delivery_verified, o.evidence_source) for o in payload.offers],
            budget_minor=payload.budget_minor, deadline_minutes=payload.deadline_minutes,
            max_merchants=payload.max_merchants,
        )
    return {
        "mode": "EVIDENCE_SEPARATED_BASKET_SCENARIO_14A2",
        "solver_engine": engine,
        "scenario_status": solved["status"],
        "purchase_allowed": False,
        "real_merchant_inventory_verified": False,
        "synthetic_optimum": solved,
        "verification_backlog": backlog,
        "disclosure": (
            "Only explicitly synthetic verified fixtures may be mathematically selected. "
            "Merchant-reported, document-sourced, or unknown stock is never accepted "
            "as independently verified. No purchase or reservation is performed."
        ),
    }
