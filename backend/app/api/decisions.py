
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.algorithms.evsi import (
    Offer,
    VerificationAction,
    bayes_update,
    plan_verifications,
)


router = APIRouter(
    prefix="/api/decisions",
    tags=["Evidence Decision Intelligence"],
)


class BayesianUpdateInput(BaseModel):
    prior: Decimal = Field(ge=0, le=1)
    sensitivity: Decimal = Field(ge=0, le=1)
    specificity: Decimal = Field(ge=0, le=1)
    observed_positive: bool


@router.post("/bayesian-update")
def update_belief(payload: BayesianUpdateInput):
    try:
        posterior = bayes_update(
            payload.prior,
            payload.sensitivity,
            payload.specificity,
            payload.observed_positive,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "prior_probability": float(payload.prior),
        "posterior_probability": float(posterior),
        "observation_positive": payload.observed_positive,
        "notice": (
            "This is a probability update, "
            "not independent proof of a product claim."
        ),
    }


@router.get("/demo-plan")
def demo_evidence_plan(
    budget_inr: int = Query(1000, ge=100, le=10000),
    deadline_minutes: int = Query(15, ge=0, le=120),
    a_verification_cost_inr: int = Query(
        8, ge=0, le=1000
    ),
    a_prior: float = Query(0.65, ge=0, le=1),
    a_response_probability: float = Query(
        0.80, ge=0, le=1
    ),
):
    """
    Research fixture for the Active Evidence Engine.

    Does not access live merchant records.
    Does not execute a real verification.
    """

    offers = [
        Offer(
            sku="CHG-A-65",
            merchant="Harbor Electronics",
            price_minor=72000,
            stock_on_hand=2,
            stock_verified=False,
            compatibility_verified=False,
            delivery_verified=False,
        ),
        Offer(
            sku="CHG-B-65",
            merchant="Metro Gadgets",
            price_minor=87000,
            stock_on_hand=3,
            stock_verified=True,
            compatibility_verified=False,
            delivery_verified=False,
        ),
        Offer(
            sku="CHG-C-65",
            merchant="City Tech",
            price_minor=89500,
            stock_on_hand=5,
            stock_verified=True,
            compatibility_verified=True,
            delivery_verified=True,
        ),
    ]

    actions = [
        VerificationAction(
            action_id="VERIFY_A",
            sku="CHG-A-65",
            prior_feasible=Decimal(str(a_prior)),
            response_probability=Decimal(
                str(a_response_probability)
            ),
            cost_minor=a_verification_cost_inr * 100,
            delay_minutes=3,
        ),
        VerificationAction(
            action_id="VERIFY_B",
            sku="CHG-B-65",
            prior_feasible=Decimal("0.75"),
            response_probability=Decimal("0.85"),
            cost_minor=600,
            delay_minutes=2,
        ),
    ]

    return plan_verifications(
        offers,
        actions,
        budget_minor=budget_inr * 100,
        deadline_minutes=deadline_minutes,
    )
