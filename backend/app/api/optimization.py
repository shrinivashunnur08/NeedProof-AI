
from fastapi import APIRouter, Query

from app.algorithms.commerce_demo import demo_plan


router = APIRouter(
    prefix="/api/optimization",
    tags=["Commerce Optimization"],
)


@router.get("/demo-plan")
def get_demo_optimization(
    budget_inr: int = Query(1800, ge=100, le=100000),
    deadline_minutes: int = Query(60, ge=0, le=240),
    max_merchants: int = Query(2, ge=1, le=3),
):
    """
    Solve a synthetic multi-merchant basket.

    No real offers are accepted or processed here.
    No payments, orders or stock reservations occur.
    """
    return demo_plan(
        budget_inr=budget_inr,
        deadline_minutes=deadline_minutes,
        max_merchants=max_merchants,
    )
