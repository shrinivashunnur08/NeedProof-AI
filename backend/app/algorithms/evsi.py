
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class Offer:
    sku: str
    merchant: str
    price_minor: int
    stock_on_hand: int
    stock_verified: bool
    compatibility_verified: bool
    delivery_verified: bool


@dataclass(frozen=True)
class VerificationAction:
    action_id: str
    sku: str
    prior_feasible: Decimal
    response_probability: Decimal
    cost_minor: int
    delay_minutes: int


def bayes_update(
    prior: Decimal,
    sensitivity: Decimal,
    specificity: Decimal,
    observed_positive: bool,
) -> Decimal:
    """
    Update a binary belief after receiving evidence.

    A posterior probability is not independent
    proof that a commerce requirement is satisfied.
    """

    for probability in (prior, sensitivity, specificity):
        if not Decimal("0") <= probability <= Decimal("1"):
            raise ValueError(
                "Probabilities must be between 0 and 1."
            )

    likelihood_if_true = (
        sensitivity if observed_positive else 1 - sensitivity
    )

    likelihood_if_false = (
        1 - specificity if observed_positive else specificity
    )

    numerator = likelihood_if_true * prior

    denominator = (
        numerator
        + likelihood_if_false * (1 - prior)
    )

    if denominator == 0:
        raise ValueError(
            "Observation has zero probability under the model."
        )

    return numerator / denominator


def money(amount_minor: Decimal | int) -> str:
    """Convert minor currency units into decimal INR."""

    return str(
        (Decimal(amount_minor) / 100).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    )


def plan_verifications(
    offers: list[Offer],
    actions: list[VerificationAction],
    *,
    budget_minor: int,
    deadline_minutes: int,
    fulfillment_value_minor: int = 20000,
    delay_cost_minor_per_minute: int = 60,
) -> dict:
    """
    Compute one-step net EVSI for synthetic verification
    actions.

    Assumptions for this research fixture:
    - Verification tests the complete feasibility
      of an offer with perfect accuracy.
    - Non-response does not establish feasibility.
    - An uncertain offer cannot be committed before
      its mandatory requirements are verified.
    - Utility includes a synthetic fulfillment benefit.
    """

    if (
        budget_minor <= 0
        or deadline_minutes < 0
        or fulfillment_value_minor < 0
        or delay_cost_minor_per_minute < 0
    ):
        raise ValueError(
            "Invalid budget, deadline or utility assumption."
        )

    by_sku = {offer.sku: offer for offer in offers}

    if len(by_sku) != len(offers):
        raise ValueError("Duplicate offer SKU.")

    def utility(offer: Offer) -> int:
        if (
            offer.price_minor > budget_minor
            or offer.price_minor < 0
        ):
            return 0

        return (
            fulfillment_value_minor
            + budget_minor
            - offer.price_minor
        )

    # Only explicitly verified offers can be
    # used as the current committed baseline.
    eligible = [
        offer
        for offer in offers
        if (
            offer.stock_verified
            and offer.compatibility_verified
            and offer.delivery_verified
            and offer.stock_on_hand > 0
            and offer.price_minor <= budget_minor
        )
    ]

    best = max(
        eligible,
        key=utility,
        default=None,
    )

    baseline = utility(best) if best else 0

    evaluations = []

    for action in actions:
        if action.sku not in by_sku:
            raise ValueError(
                f"Unknown offer SKU: {action.sku}"
            )

        if not (
            0 <= action.prior_feasible <= 1
            and 0 <= action.response_probability <= 1
        ):
            raise ValueError(
                "Probabilities must be between 0 and 1."
            )

        if action.cost_minor < 0 or action.delay_minutes < 0:
            raise ValueError(
                "Costs and delays cannot be negative."
            )

        offer = by_sku[action.sku]
        skip_reason = None

        if offer in eligible:
            skip_reason = "ALREADY_ELIGIBLE"

        elif offer.price_minor > budget_minor:
            skip_reason = "OUTSIDE_BUDGET"

        elif action.delay_minutes > deadline_minutes:
            skip_reason = "DEADLINE_INFEASIBLE"

        elif action.response_probability == 0:
            skip_reason = "NO_EXPECTED_RESPONSE"

        # Possible verification outcomes.
        p_pass = (
            action.prior_feasible
            * action.response_probability
        )

        p_fail = (
            (1 - action.prior_feasible)
            * action.response_probability
        )

        p_no_response = 1 - action.response_probability

        # Utility improvement if full verification
        # succeeds and the offer becomes eligible.
        upside = max(
            0,
            utility(offer) - baseline,
        )

        gross = p_pass * Decimal(upside)

        cost = Decimal(
            action.cost_minor
            + action.delay_minutes
            * delay_cost_minor_per_minute
        )

        net = (
            gross - cost
            if skip_reason is None
            else Decimal(0)
        )

        evaluations.append({
            "action_id": action.action_id,
            "merchant": offer.merchant,
            "sku": offer.sku,
            "prior_feasible": float(
                action.prior_feasible
            ),
            "response_probability": float(
                action.response_probability
            ),
            "p_pass": float(p_pass),
            "p_fail": float(p_fail),
            "p_no_response": float(p_no_response),
            "gross_evsi_inr": (
                money(gross)
                if skip_reason is None
                else "0.00"
            ),
            "verification_cost_inr": money(
                action.cost_minor
            ),
            "delay_cost_inr": money(
                action.delay_minutes
                * delay_cost_minor_per_minute
            ),
            "net_evsi_inr": money(net),
            "_net": net,
            "skip_reason": skip_reason,
        })

    positive_actions = [
        item
        for item in evaluations
        if (
            item["skip_reason"] is None
            and item["_net"] > 0
        )
    ]

    selected = max(
        positive_actions,
        key=lambda item: item["_net"],
        default=None,
    )

    evaluations.sort(
        key=lambda item: item["_net"],
        reverse=True,
    )

    for item in evaluations:
        del item["_net"]

    return {
        "mode": "SYNTHETIC_RESEARCH_SCENARIO",
        "baseline": (
            {
                "merchant": best.merchant,
                "sku": best.sku,
                "price_inr": money(best.price_minor),
            }
            if best
            else None
        ),
        "baseline_utility_inr": money(baseline),
        "recommended_action_id": (
            selected["action_id"] if selected else None
        ),
        "stopping_reason": (
            None
            if selected
            else "NO_POSITIVE_FEASIBLE_VERIFICATION_VALUE"
        ),
        "actions": evaluations,
        "assumptions": [
            "Synthetic priors and response probabilities.",
            "Complete verification is perfectly accurate in this fixture.",
            "Unknown or unverified offers are not eligible for commitment.",
            "Non-response never establishes eligibility.",
            "No actual merchant is contacted.",
            "Utility is synthetic, not measured profit or customer welfare.",
        ],
    }
