
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Response,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.merchant_onboarding import local_only
from app.db.session import get_db
from app.services.simulation_transactions import (
    SimulationError,
    get_inventory,
    get_order,
    reserve_basket,
    transition_order,
)


router = APIRouter(
    prefix="/api/transactions/simulation",
    tags=["Transaction Safety Simulation"],
    dependencies=[Depends(local_only)],
)


class ReserveBasketRequest(BaseModel):
    budget_inr: int = Field(ge=100, le=100000)
    deadline_minutes: int = Field(ge=0, le=240)
    max_merchants: int = Field(ge=1, le=3)
    ttl_seconds: int = Field(default=120, ge=10, le=300)


def run(operation):
    try:
        return operation()
    except SimulationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc


@router.get("/inventory")
def inventory(
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    return run(lambda: get_inventory(db))


@router.post("/reserve", status_code=201)
def reserve(
    payload: ReserveBasketRequest,
    response: Response,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=12,
        max_length=128,
    ),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    return run(
        lambda: reserve_basket(
            db,
            key=idempotency_key,
            request_data=payload.model_dump(),
        )
    )


@router.get("/orders/{order_id}")
def read_order(
    order_id: int,
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    return run(lambda: get_order(db, order_id))


@router.post("/orders/{order_id}/commit")
def commit(
    order_id: int,
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    return run(
        lambda: transition_order(
            db,
            order_id=order_id,
            action="commit",
        )
    )


@router.post("/orders/{order_id}/cancel")
def cancel(
    order_id: int,
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    return run(
        lambda: transition_order(
            db,
            order_id=order_id,
            action="cancel",
        )
    )
