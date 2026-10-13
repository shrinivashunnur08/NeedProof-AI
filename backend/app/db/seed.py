
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EvidenceClaim,
    InventoryRecord,
    Merchant,
    Product,
    utc_now,
)
from app.db.session import get_session_factory


DEMO_PRODUCTS = [
    (
        "Harbor Electronics", "Thane",
        "CHG-A-65", "65W USB-C PD Charger — A",
        "charger", 72000, 2, 48,
        "STALE", "UNVERIFIED",
    ),
    (
        "Metro Gadgets", "Dombivli",
        "CHG-B-65", "65W USB-C PD Charger — B",
        "charger", 87000, 3, 2,
        "VERIFIED", "UNVERIFIED",
    ),
    (
        "City Tech", "Kalyan",
        "CHG-C-65", "65W USB-C PD Charger — C",
        "charger", 89500, 5, 1,
        "VERIFIED", "VERIFIED",
    ),
    (
        "Harbor Electronics", "Thane",
        "CABLE-A", "USB-C PD Cable",
        "cable", 19900, 8, 6,
        "VERIFIED", "VERIFIED",
    ),
    (
        "Metro Gadgets", "Dombivli",
        "HUB-B", "USB-C Multiport Hub",
        "adapter", 129900, 4, 26,
        "STALE", "UNVERIFIED",
    ),
    (
        "City Tech", "Kalyan",
        "MOUSE-C", "Wireless Mouse",
        "accessory", 59900, 9, 4,
        "VERIFIED", "VERIFIED",
    ),
]


def seed_data(db: Session) -> int:
    if db.scalar(select(Merchant.id).limit(1)) is not None:
        return 0

    merchants: dict[str, Merchant] = {}
    now = utc_now()

    for (
        name, area, sku, product_name, category,
        price, stock, hours, stock_status, spec_status
    ) in DEMO_PRODUCTS:

        if name not in merchants:
            merchant = Merchant(
                name=name,
                area=area,
                is_demo=True,
            )

            db.add(merchant)
            db.flush()

            merchants[name] = merchant

        specs = (
            {
                "power_w": 65,
                "connector": "USB-C",
                "protocol": "USB PD",
            }
            if category == "charger"
            else {}
        )

        product = Product(
            merchant_id=merchants[name].id,
            sku=sku,
            name=product_name,
            category=category,
            price_minor=price,
            currency="INR",
            specifications=specs,
        )

        db.add(product)
        db.flush()

        observed_at = now - timedelta(hours=hours)

        db.add(
            InventoryRecord(
                product_id=product.id,
                stock_on_hand=stock,
                stock_reserved=0,
                updated_at=observed_at,
                last_checked_at=observed_at,
            )
        )

        db.add(
            EvidenceClaim(
                product_id=product.id,
                claim_type="stock_count",
                claimed_value=str(stock),
                status=stock_status,
                source="SYNTHETIC_MERCHANT_RECORD",
                observed_at=observed_at,
                notes="Fictional demonstration inventory.",
            )
        )

        db.add(
            EvidenceClaim(
                product_id=product.id,
                claim_type="published_specification",
                claimed_value=(
                    "USB-C PD, 65W"
                    if category == "charger"
                    else "Catalog specification"
                ),
                status=spec_status,
                source="SYNTHETIC_CATALOG",
                observed_at=observed_at,
                notes=(
                    "Does not prove compatibility with "
                    "a particular laptop."
                ),
            )
        )

    db.commit()
    return len(DEMO_PRODUCTS)


if __name__ == "__main__":
    with get_session_factory()() as session:
        count = seed_data(session)
        print(
            f"Seeded {count} products "
            "(0 means already initialized)."
        )
