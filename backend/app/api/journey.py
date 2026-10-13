
from fastapi import APIRouter, Depends, Response

from app.algorithms.adaptive_replanning import (
    ReplanInput,
    evaluate_replan,
)
from app.api.merchant_onboarding import local_only


router = APIRouter(
    prefix="/api/journey",
    tags=["Adaptive Customer Decisions"],
    dependencies=[Depends(local_only)],
)


@router.post("/replan")
def replan_customer_decision(
    payload: ReplanInput,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    return evaluate_replan(payload)
