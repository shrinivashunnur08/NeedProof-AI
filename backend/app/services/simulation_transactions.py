
import hashlib
import json
from datetime import timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.algorithms.commerce_demo import demo_plan
from app.db.models import (
    SimulationInventory,
    SimulationOrder,
    SimulationOrderEvent,
    utc_now,
)


# Dedicated fictional stock. None of these SKUs represent
# actual inventory at a Google-listed merchant.
INITIAL_STOCK = {
    "CHG-A": 5,
    "CHG-B": 5,
    "CHG-C": 5,
    "CBL-A": 5,
    "CBL-B": 5,
    "CBL-C": 5,
    "MOU-A": 5,
    "MOU-B": 5,
    "MOU-C": 5,
}


class SimulationError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def utc_aware(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def fingerprint(payload: dict) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def seed_inventory(db: Session):
    missing = [
        SimulationInventory(
            sku=sku,
            initial_quantity=quantity,
            available_quantity=quantity,
        )
        for sku, quantity in INITIAL_STOCK.items()
        if db.get(SimulationInventory, sku) is None
    ]

    if not missing:
        return

    db.add_all(missing)

    try:
        db.commit()
    except IntegrityError:
        # Another local request may have initialized the
        # same fixture concurrently. Its rows win.
        db.rollback()


def add_event(
    db: Session,
    order_id: int,
    event_type: str,
):
    db.add(
        SimulationOrderEvent(
            order_id=order_id,
            event_type=event_type,
        )
    )


def release_reserved_stock(
    db: Session,
    order: SimulationOrder,
):
    for offer in order.plan_snapshot["selected_offers"]:
        quantity = int(offer["quantity"])

        db.execute(
            update(SimulationInventory)
            .where(
                SimulationInventory.sku == offer["sku"]
            )
            .values(
                available_quantity=(
                    SimulationInventory.available_quantity
                    + quantity
                )
            )
        )


def expire_due_orders(db: Session):
    """
    Lazy expiration: cleanup occurs on the next relevant
    API request, not on a background timer.
    """
    now = utc_now()

    candidates = db.scalars(
        select(SimulationOrder).where(
            SimulationOrder.status == "RESERVED"
        )
    ).all()

    changed = False

    for order in candidates:
        if utc_aware(order.expires_at) > now:
            continue

        transition = db.execute(
            update(SimulationOrder)
            .where(
                SimulationOrder.id == order.id,
                SimulationOrder.status == "RESERVED",
            )
            .values(
                status="EXPIRED",
                finalized_at=now,
            )
        )

        if transition.rowcount != 1:
            continue

        release_reserved_stock(db, order)
        add_event(db, order.id, "EXPIRED")
        changed = True

    if changed:
        db.commit()


def serialize_order(
    db: Session,
    order: SimulationOrder,
) -> dict:
    events = db.scalars(
        select(SimulationOrderEvent)
        .where(SimulationOrderEvent.order_id == order.id)
        .order_by(SimulationOrderEvent.id)
    ).all()

    return {
        "mode": "SYNTHETIC_TRANSACTION",
        "order_id": order.id,
        "status": order.status,
        "created_at": order.created_at,
        "expires_at": order.expires_at,
        "finalized_at": order.finalized_at,
        "plan": order.plan_snapshot,
        "events": [
            {
                "id": event.id,
                "type": event.event_type,
                "recorded_at": event.recorded_at,
            }
            for event in events
        ],
        "payment_executed": False,
        "real_merchant_inventory_reserved": False,
        "notice": (
            "Simulation only. No external order, payment "
            "or real merchant inventory reservation."
        ),
    }


def get_order(db: Session, order_id: int) -> dict:
    expire_due_orders(db)

    order = db.get(SimulationOrder, order_id)

    if order is None:
        raise SimulationError(404, "Simulation order not found.")

    return serialize_order(db, order)


def get_inventory(db: Session) -> dict:
    seed_inventory(db)
    expire_due_orders(db)

    rows = db.scalars(
        select(SimulationInventory).order_by(
            SimulationInventory.sku
        )
    ).all()

    return {
        "mode": "SYNTHETIC_INVENTORY",
        "items": [
            {
                "sku": row.sku,
                "initial_quantity": row.initial_quantity,
                "available_quantity": row.available_quantity,
            }
            for row in rows
        ],
        "notice": (
            "Quantities are stored in a local sandbox, "
            "not synchronized with any merchant."
        ),
    }


def reserve_basket(
    db: Session,
    *,
    key: str,
    request_data: dict,
) -> dict:
    seed_inventory(db)
    expire_due_orders(db)

    request_hash = fingerprint(request_data)

    existing = db.scalar(
        select(SimulationOrder).where(
            SimulationOrder.idempotency_key == key
        )
    )

    if existing is not None:
        if existing.request_fingerprint != request_hash:
            raise SimulationError(
                409,
                "Idempotency key already belongs to "
                "a different request.",
            )

        return serialize_order(db, existing)

    plan = demo_plan(
        budget_inr=request_data["budget_inr"],
        deadline_minutes=request_data["deadline_minutes"],
        max_merchants=request_data["max_merchants"],
    )

    if plan["status"] != "OPTIMAL":
        raise SimulationError(
            422,
            "The synthetic basket is not proven feasible "
            f"and optimal: {plan['reason'] or plan['status']}",
        )

    now = utc_now()

    order = SimulationOrder(
        idempotency_key=key,
        request_fingerprint=request_hash,
        status="RESERVED",
        plan_snapshot=plan,
        created_at=now,
        expires_at=now + timedelta(
            seconds=request_data["ttl_seconds"]
        ),
    )

    try:
        db.add(order)
        db.flush()

        # Atomic conditional UPDATE prevents two requests
        # from consuming the same remaining stock.
        for offer in sorted(
            plan["selected_offers"],
            key=lambda value: value["sku"],
        ):
            sku = offer["sku"]
            quantity = int(offer["quantity"])

            reservation = db.execute(
                update(SimulationInventory)
                .where(
                    SimulationInventory.sku == sku,
                    SimulationInventory.available_quantity
                    >= quantity,
                )
                .values(
                    available_quantity=(
                        SimulationInventory.available_quantity
                        - quantity
                    )
                )
            )

            if reservation.rowcount != 1:
                db.rollback()
                raise SimulationError(
                    409,
                    f"Synthetic inventory unavailable for {sku}.",
                )

        add_event(db, order.id, "RESERVED")
        db.commit()
        db.refresh(order)

        return serialize_order(db, order)

    except IntegrityError:
        db.rollback()

        # A concurrent request could have won the unique
        # idempotency-key constraint.
        winner = db.scalar(
            select(SimulationOrder).where(
                SimulationOrder.idempotency_key == key
            )
        )

        if (
            winner is not None
            and winner.request_fingerprint == request_hash
        ):
            return serialize_order(db, winner)

        raise SimulationError(
            409,
            "Reservation conflict. Check inventory and retry.",
        )


def transition_order(
    db: Session,
    *,
    order_id: int,
    action: str,
) -> dict:
    expire_due_orders(db)

    order = db.get(SimulationOrder, order_id)

    if order is None:
        raise SimulationError(404, "Simulation order not found.")

    target = {
        "commit": "COMMITTED_SIMULATED",
        "cancel": "CANCELLED",
    }[action]

    # Repeating an already completed operation is safe.
    if order.status == target:
        return serialize_order(db, order)

    if order.status != "RESERVED":
        raise SimulationError(
            409,
            f"Cannot {action} an order with status "
            f"{order.status}.",
        )

    now = utc_now()

    if utc_aware(order.expires_at) <= now:
        expire_due_orders(db)
        raise SimulationError(
            409,
            "Reservation has expired.",
        )

    changed = db.execute(
        update(SimulationOrder)
        .where(
            SimulationOrder.id == order_id,
            SimulationOrder.status == "RESERVED",
        )
        .values(
            status=target,
            finalized_at=now,
        )
    )

    if changed.rowcount != 1:
        db.rollback()
        raise SimulationError(
            409, "The reservation changed concurrently."
        )

    if action == "cancel":
        release_reserved_stock(db, order)

    add_event(db, order_id, target)
    db.commit()

    return get_order(db, order_id)
