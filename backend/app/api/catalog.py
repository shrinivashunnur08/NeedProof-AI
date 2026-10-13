
from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import (
    EvidenceClaim,
    InventoryRecord,
    Merchant,
    Product,
    utc_now,
)
from app.db.session import get_db


router = APIRouter(
    prefix="/api/catalog",
    tags=["Catalog & Evidence"],
)


class StockUpdate(BaseModel):
    stock_on_hand: int = Field(ge=0, le=1_000_000)


def stock_freshness(checked_at: datetime | None) -> str:
    if checked_at is None:
        return "UNCHECKED"

    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)

    age_seconds = (utc_now() - checked_at).total_seconds()

    if 0 <= age_seconds < 24 * 3600:
        return "RECENTLY_CHECKED"

    return "STALE"


@router.get("/health")
def catalog_health(
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings),
):
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": cfg.database_backend,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable.",
        ) from exc


@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings),
):
    return {
        "merchant_count": (
            db.scalar(select(func.count(Merchant.id))) or 0
        ),
        "product_count": (
            db.scalar(select(func.count(Product.id))) or 0
        ),
        "evidence_count": (
            db.scalar(select(func.count(EvidenceClaim.id))) or 0
        ),
        "data_mode": (
            "DEMO"
            if cfg.environment == "development"
            else "MIXED"
        ),
    }


@router.get("/merchants")
def merchants(db: Session = Depends(get_db)):
    results = db.scalars(
        select(Merchant).order_by(Merchant.name)
    ).all()

    return [
        {
            "id": m.id,
            "name": m.name,
            "area": m.area,
            "is_demo": m.is_demo,
            "is_active": m.is_active,
        }
        for m in results
    ]


@router.get("/products")
def products(
    category: str | None = None,
    db: Session = Depends(get_db),
):
    query = (
        select(Product, Merchant, InventoryRecord)
        .join(Merchant, Product.merchant_id == Merchant.id)
        .join(
            InventoryRecord,
            Product.id == InventoryRecord.product_id,
        )
    )

    if category:
        query = query.where(Product.category == category)

    query = query.order_by(Product.price_minor)

    results = []

    for product, merchant, inventory in db.execute(query).all():
        claims = db.scalars(
            select(EvidenceClaim)
            .where(EvidenceClaim.product_id == product.id)
            .order_by(EvidenceClaim.id)
        ).all()

        results.append({
            "id": product.id,
            "merchant_id": merchant.id,
            "merchant_name": merchant.name,
            "merchant_area": merchant.area,
            "is_demo": merchant.is_demo,
            "sku": product.sku,
            "name": product.name,
            "category": product.category,
            "price_minor": product.price_minor,
            "currency": product.currency,
            "specifications": product.specifications,
            "inventory_id": inventory.id,
            "stock_on_hand": inventory.stock_on_hand,
            "stock_reserved": inventory.stock_reserved,
            "stock_available": (
                inventory.stock_on_hand
                - inventory.stock_reserved
            ),
            "last_checked_at": inventory.last_checked_at,
            "stock_freshness": stock_freshness(
                inventory.last_checked_at
            ),
            "evidence": [
                {
                    "claim_type": claim.claim_type,
                    "status": claim.status,
                    "source": claim.source,
                }
                for claim in claims
            ],
        })

    return results


@router.get("/evidence")
def evidence(
    product_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = select(EvidenceClaim).order_by(EvidenceClaim.id)

    if product_id is not None:
        query = query.where(
            EvidenceClaim.product_id == product_id
        )

    claims = db.scalars(query.limit(100)).all()

    return [
        {
            "id": claim.id,
            "product_id": claim.product_id,
            "claim_type": claim.claim_type,
            "claimed_value": claim.claimed_value,
            "status": claim.status,
            "source": claim.source,
            "observed_at": claim.observed_at,
            "expires_at": claim.expires_at,
            "notes": claim.notes,
        }
        for claim in claims
    ]


@router.patch("/inventory/{inventory_id}")
def update_demo_inventory(
    inventory_id: int,
    payload: StockUpdate,
    x_demo_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings),
):
    # Strictly local development use.
    if (
        cfg.environment != "development"
        or not cfg.demo_write_key
        or not secrets.compare_digest(
            x_demo_key or "",
            cfg.demo_write_key,
        )
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Demo inventory editing is disabled "
                "or unauthorized."
            ),
        )

    record = db.get(InventoryRecord, inventory_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory record not found.",
        )

    if payload.stock_on_hand < record.stock_reserved:
        raise HTTPException(
            status_code=409,
            detail=(
                "Stock cannot be reduced below "
                "existing reservations."
            ),
        )

    record.stock_on_hand = payload.stock_on_hand
    record.updated_at = utc_now()

    # Manual data entry does not prove physical stock.
    record.last_checked_at = None

    db.add(
        EvidenceClaim(
            product_id=record.product_id,
            claim_type="operator_stock_update",
            claimed_value=str(payload.stock_on_hand),
            status="UNVERIFIED",
            source="DEMO_OPERATOR_EDIT",
            observed_at=utc_now(),
            notes=(
                "Manual demo change; physical "
                "count not verified."
            ),
        )
    )

    db.commit()

    return {
        "id": record.id,
        "stock_on_hand": record.stock_on_hand,
        "stock_reserved": record.stock_reserved,
        "stock_freshness": "UNCHECKED",
    }
