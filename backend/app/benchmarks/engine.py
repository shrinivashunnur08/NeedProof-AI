
import random
from statistics import mean

from app.algorithms.commerce_optimizer import (
    BasketItem,
    Merchant,
    ProductOffer,
    optimize_basket,
)


BASKET_POLICIES = (
    "NEEDPROOF_ORTOOLS",
    "CHEAPEST_FIRST",
    "SINGLE_MERCHANT",
)

EVIDENCE_POLICIES = (
    "EVSI_ONE_STEP",
    "VERIFY_EVERYTHING",
    "NO_VERIFICATION",
)


def make_basket_scenario(rng: random.Random):
    """Reproducible fictional stores, products and constraints."""

    items = [
        BasketItem("charger", "65W USB-C PD Charger"),
        BasketItem("cable", "USB-C Cable"),
        BasketItem("mouse", "Wireless Mouse"),
    ]

    merchant_specs = [
        ("harbor", "Harbor Electronics", 80, 15),
        ("metro", "Metro Gadgets", 40, 20),
        ("city", "City Tech", 0, 30),
    ]

    merchants = [
        Merchant(
            merchant_id=merchant_id,
            name=name,
            fulfillment_fee_minor=max(
                0, base_fee + rng.randrange(-20, 21, 5)
            ) * 100,
        )
        for merchant_id, name, base_fee, _ in merchant_specs
    ]

    prices = {
        "charger": [720, 870, 895],
        "cable": [199, 180, 240],
        "mouse": [599, 540, 575],
    }

    offers = []

    for item in items:
        for index, merchant_spec in enumerate(merchant_specs):
            merchant_id, _, _, base_eta = merchant_spec

            price = max(
                1,
                prices[item.item_id][index]
                + rng.randrange(-80, 81, 5),
            )

            stock = rng.choices(
                [0, 1, 3],
                weights=[10, 30, 60],
            )[0]

            verified = rng.random() >= 0.08
            compatible = rng.random() >= 0.08
            delivery_verified = rng.random() >= 0.05

            offers.append(
                ProductOffer(
                    sku=f"{item.item_id}-{merchant_id}",
                    item_id=item.item_id,
                    merchant_id=merchant_id,
                    product_name=item.name,
                    unit_price_minor=price * 100,
                    stock_on_hand=stock,
                    delivery_eta_minutes=max(
                        1, base_eta + rng.choice([-5, 0, 5])
                    ),
                    merchant_verified=verified,
                    stock_verified=verified,
                    compatibility_verified=compatible,
                    delivery_verified=delivery_verified,
                    evidence_source=(
                        "SIMULATION_VERIFIED"
                        if verified and compatible
                        and delivery_verified
                        else "SIMULATION_UNVERIFIED"
                    ),
                )
            )

    constraints = {
        "budget_minor": rng.choice(
            [1450, 1550, 1650, 1800, 1950, 2150]
        ) * 100,
        "deadline_minutes": rng.choice(
            [10, 15, 20, 30, 45, 60]
        ),
        "max_merchants": rng.choice([1, 2, 3]),
    }

    return items, merchants, offers, constraints


def baseline_basket(
    items,
    merchants,
    offers,
    eligible_skus: set[str],
    constraints,
    strategy: str,
):
    """Compare simple strategies using the SAME eligible offers."""

    eligible = [
        offer for offer in offers
        if offer.sku in eligible_skus
    ]

    merchant_map = {
        merchant.merchant_id: merchant
        for merchant in merchants
    }

    choices = []

    if strategy == "CHEAPEST_FIRST":
        for item in items:
            candidates = [
                offer for offer in eligible
                if offer.item_id == item.item_id
            ]

            if not candidates:
                return {
                    "feasible": False,
                    "total_minor": None,
                    "reason": "NO_ELIGIBLE_OFFER",
                }

            choices.append(
                min(
                    candidates,
                    key=lambda offer: (
                        offer.unit_price_minor,
                        offer.sku,
                    ),
                )
            )

    elif strategy == "SINGLE_MERCHANT":
        candidates = []

        for merchant in merchants:
            merchant_choices = []

            for item in items:
                options = [
                    offer for offer in eligible
                    if offer.item_id == item.item_id
                    and offer.merchant_id == merchant.merchant_id
                ]

                if not options:
                    break

                merchant_choices.append(
                    min(
                        options,
                        key=lambda offer: (
                            offer.unit_price_minor,
                            offer.sku,
                        ),
                    )
                )

            if len(merchant_choices) == len(items):
                price = sum(
                    offer.unit_price_minor * item.quantity
                    for item, offer in zip(
                        items, merchant_choices
                    )
                )

                price += merchant.fulfillment_fee_minor
                candidates.append(
                    (price, merchant.merchant_id, merchant_choices)
                )

        if not candidates:
            return {
                "feasible": False,
                "total_minor": None,
                "reason": "NO_SINGLE_MERCHANT_CAN_FULFILL",
            }

        choices = min(candidates, key=lambda row: (
            row[0], row[1]
        ))[2]

    else:
        raise ValueError("Unknown baseline strategy.")

    used = {offer.merchant_id for offer in choices}

    total = sum(
        offer.unit_price_minor * item.quantity
        for item, offer in zip(items, choices)
    ) + sum(
        merchant_map[merchant_id].fulfillment_fee_minor
        for merchant_id in used
    )

    if len(used) > constraints["max_merchants"]:
        reason = "MERCHANT_LIMIT_EXCEEDED"
    elif total > constraints["budget_minor"]:
        reason = "BUDGET_EXCEEDED"
    else:
        reason = None

    return {
        "feasible": reason is None,
        "total_minor": total if reason is None else None,
        "reason": reason,
    }


def run_basket_trial(rng: random.Random, trial_id: int):
    items, merchants, offers, constraints = (
        make_basket_scenario(rng)
    )

    optimized = optimize_basket(
        items,
        merchants,
        offers,
        **constraints,
    )

    excluded_skus = {
        entry["sku"]
        for entry in optimized["excluded_offers"]
    }

    eligible_skus = {
        offer.sku for offer in offers
        if offer.sku not in excluded_skus
    }

    np_feasible = (
        optimized["status"] in ("OPTIMAL", "FEASIBLE")
    )

    results = {
        "NEEDPROOF_ORTOOLS": {
            "feasible": np_feasible,
            "total_minor": (
                optimized["totals"]["total_minor"]
                if np_feasible else None
            ),
            "reason": optimized["reason"],
            "solver_status": optimized["status"],
        }
    }

    for strategy in (
        "CHEAPEST_FIRST",
        "SINGLE_MERCHANT",
    ):
        results[strategy] = baseline_basket(
            items,
            merchants,
            offers,
            eligible_skus,
            constraints,
            strategy,
        )

    return {
        "trial_id": trial_id,
        "budget_inr": constraints["budget_minor"] // 100,
        "deadline_minutes": constraints["deadline_minutes"],
        "max_merchants": constraints["max_merchants"],
        "results": results,
    }


def summarize_baskets(trials: list[dict]) -> dict:
    summary = {}

    for policy in BASKET_POLICIES:
        feasible = [
            trial["results"][policy]
            for trial in trials
            if trial["results"][policy]["feasible"]
        ]

        paired = [
            (
                trial["results"]["NEEDPROOF_ORTOOLS"],
                trial["results"][policy],
            )
            for trial in trials
            if trial["results"]["NEEDPROOF_ORTOOLS"]["feasible"]
            and trial["results"][policy]["feasible"]
        ]

        extra_cost = [
            (baseline["total_minor"] - optimized["total_minor"])
            / 100
            for optimized, baseline in paired
        ]

        missed = sum(
            trial["results"]["NEEDPROOF_ORTOOLS"]["feasible"]
            and not trial["results"][policy]["feasible"]
            for trial in trials
        )

        summary[policy] = {
            "feasible_count": len(feasible),
            "feasibility_rate_pct": round(
                100 * len(feasible) / len(trials), 2
            ),
            "average_cost_inr_on_feasible": (
                round(
                    mean(
                        result["total_minor"] / 100
                        for result in feasible
                    ), 2
                )
                if feasible else None
            ),
            "paired_cases": len(paired),
            "mean_extra_cost_vs_needproof_inr": (
                round(mean(extra_cost), 2)
                if extra_cost else None
            ),
            "missed_feasible_cases": missed,
        }

    return summary


def best_choice(values: dict[str, float]) -> str:
    # Fixed order makes ties deterministic.
    return max(
        ("SAFE", "A", "B"),
        key=lambda name: values[name],
    )


def run_evidence_trial(rng: random.Random, trial_id: int):
    """
    Two uncertain offers and one guaranteed safe fallback.
    Perfect checks are SIMULATED, not real-world evidence.
    """

    safe_value = 90.0

    scenario = {
        name: {
            "prior": round(rng.uniform(0.25, 0.85), 4),
            "success_value": rng.randint(180, 300),
            "failure_value": -rng.randint(40, 180),
            "verification_cost": rng.randint(5, 60),
        }
        for name in ("A", "B")
    }

    actual_success = {
        name: rng.random() < scenario[name]["prior"]
        for name in ("A", "B")
    }

    expected = {
        name: (
            info["prior"] * info["success_value"]
            + (1 - info["prior"]) * info["failure_value"]
        )
        for name, info in scenario.items()
    }

    expected["SAFE"] = safe_value

    realized = {
        name: (
            scenario[name]["success_value"]
            if actual_success[name]
            else scenario[name]["failure_value"]
        )
        for name in ("A", "B")
    }
    realized["SAFE"] = safe_value

    def record(
        selected: str,
        checks: list[str],
    ):
        cost = sum(
            scenario[name]["verification_cost"]
            for name in checks
        )

        return {
            "selected": selected,
            "checks": len(checks),
            "verification_cost_inr": cost,
            "realized_net_utility_inr": (
                realized[selected] - cost
            ),
            "failed_selection": (
                selected != "SAFE"
                and not actual_success[selected]
            ),
        }

    # Baseline 1: make the best prior-expected decision
    # without checking either candidate.
    no_check_choice = best_choice(expected)

    no_verification = record(
        no_check_choice,
        [],
    )

    # Baseline 2: check both candidates regardless of cost.
    verify_all = record(
        best_choice(realized),
        ["A", "B"],
    )

    # NeedProof policy: calculate the expected net value
    # of perfectly checking EACH candidate separately.
    # Then perform at most one worthwhile check.
    current_best = max(expected.values())
    evsi_options = {}

    for candidate in ("A", "B"):
        other = "B" if candidate == "A" else "A"
        info = scenario[candidate]

        after_positive = max(
            safe_value,
            info["success_value"],
            expected[other],
        )

        after_negative = max(
            safe_value,
            info["failure_value"],
            expected[other],
        )

        expected_after = (
            info["prior"] * after_positive
            + (1 - info["prior"]) * after_negative
        )

        evsi_options[candidate] = (
            expected_after
            - current_best
            - info["verification_cost"]
        )

    best_check = max(
        ("A", "B"),
        key=lambda name: evsi_options[name],
    )

    if evsi_options[best_check] > 0:
        # The checked candidate's state becomes known.
        # The other candidate retains its prior estimate.
        updated = dict(expected)
        updated[best_check] = realized[best_check]

        evsi_result = record(
            best_choice(updated),
            [best_check],
        )
    else:
        evsi_result = record(
            no_check_choice,
            [],
        )

    return {
        "trial_id": trial_id,
        "prior_a": scenario["A"]["prior"],
        "prior_b": scenario["B"]["prior"],
        "actual_a_success": actual_success["A"],
        "actual_b_success": actual_success["B"],
        "results": {
            "EVSI_ONE_STEP": evsi_result,
            "VERIFY_EVERYTHING": verify_all,
            "NO_VERIFICATION": no_verification,
        },
    }


def summarize_evidence(trials: list[dict]) -> dict:
    summary = {}

    for policy in EVIDENCE_POLICIES:
        rows = [
            trial["results"][policy]
            for trial in trials
        ]

        summary[policy] = {
            "average_realized_net_utility_inr": round(
                mean(
                    row["realized_net_utility_inr"]
                    for row in rows
                ), 2
            ),
            "average_verification_cost_inr": round(
                mean(
                    row["verification_cost_inr"]
                    for row in rows
                ), 2
            ),
            "average_checks": round(
                mean(row["checks"] for row in rows), 3
            ),
            "failed_selection_rate_pct": round(
                100 * sum(
                    row["failed_selection"]
                    for row in rows
                ) / len(rows), 2
            ),
        }

    return summary


def run_benchmarks(
    *,
    seed: int = 42,
    basket_scenarios: int = 30,
    evidence_trials: int = 500,
):
    if not (1 <= basket_scenarios <= 80):
        raise ValueError("Basket scenarios must be 1–80.")

    if not (10 <= evidence_trials <= 2000):
        raise ValueError("Evidence trials must be 10–2000.")

    # Independent random streams so changing one trial
    # count does not change the other benchmark.
    basket_rng = random.Random(seed)
    evidence_rng = random.Random(seed + 1_000_003)

    baskets = [
        run_basket_trial(basket_rng, i + 1)
        for i in range(basket_scenarios)
    ]

    evidence = [
        run_evidence_trial(evidence_rng, i + 1)
        for i in range(evidence_trials)
    ]

    return {
        "mode": "SYNTHETIC_BENCHMARK",
        "seed": seed,
        "basket_scenarios": basket_scenarios,
        "evidence_trials": evidence_trials,
        "basket": {
            "summary": summarize_baskets(baskets),
            "trials": baskets,
        },
        "evidence": {
            "summary": summarize_evidence(evidence),
            "trials": evidence,
        },
        "assumptions": {
            "data": "Fully synthetic and seeded",
            "basket_comparison": (
                "All basket strategies use the same eligible "
                "offers, prices, deadlines and merchant fees."
            ),
            "cheapest_first": (
                "Chooses lowest eligible unit price per item "
                "without optimizing merchant fees or store count."
            ),
            "single_merchant": (
                "Selects the cheapest eligible single-store "
                "basket if one is possible."
            ),
            "evidence_comparison": (
                "Two independent uncertain offers, one safe "
                "fallback, simulated perfect checks and "
                "monetary utility scores."
            ),
            "evsi_scope": (
                "Tests a one-step EVSI decision policy. "
                "It is a separate policy-level simulation, "
                "not a test of real merchant response accuracy."
            ),
            "cost_metric": (
                "Average basket cost uses feasible cases only. "
                "Paired comparisons use the same feasible cases."
            ),
        },
    }
