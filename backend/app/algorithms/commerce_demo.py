
from app.algorithms.commerce_optimizer import (
    BasketItem,
    Merchant,
    ProductOffer,
    optimize_basket,
)


def make_offer(
    sku: str,
    item: str,
    merchant: str,
    price_inr: int,
    *,
    stock: int = 5,
    eta: int = 20,
    verified: bool = True,
) -> ProductOffer:
    return ProductOffer(
        sku=sku,
        item_id=item,
        merchant_id=merchant,
        product_name=item,
        unit_price_minor=price_inr * 100,
        stock_on_hand=stock,
        delivery_eta_minutes=eta,
        merchant_verified=verified,
        stock_verified=verified,
        compatibility_verified=verified,
        delivery_verified=verified,
        evidence_source=(
            "SIMULATION_VERIFIED"
            if verified
            else "MERCHANT_REPORTED_UNVERIFIED"
        ),
    )


def demo_plan(
    budget_inr: int = 1800,
    deadline_minutes: int = 60,
    max_merchants: int = 2,
) -> dict:
    basket = [
        BasketItem("charger", "65W USB-C PD Charger"),
        BasketItem("cable", "USB-C Cable"),
        BasketItem("mouse", "Wireless Mouse"),
    ]

    merchants = [
        Merchant("harbor", "Harbor Electronics", 8000),
        Merchant("metro", "Metro Gadgets", 4000),
        Merchant("city", "City Tech", 0),
    ]

    offers = [
        make_offer(
            "CHG-A", "charger", "harbor", 720, eta=15
        ),
        make_offer(
            "CHG-B", "charger", "metro", 870
        ),
        make_offer(
            "CHG-C", "charger", "city", 895, eta=30
        ),

        make_offer(
            "CBL-A", "cable", "harbor", 199, eta=15
        ),
        make_offer(
            "CBL-B", "cable", "metro", 180
        ),
        make_offer(
            "CBL-C", "cable", "city", 240, eta=30
        ),

        make_offer(
            "MOU-A", "mouse", "harbor", 599, eta=15
        ),
        make_offer(
            "MOU-B", "mouse", "metro", 540
        ),
        make_offer(
            "MOU-C", "mouse", "city", 575, eta=30
        ),

        # Intentionally unverified low-price offer.
        make_offer(
            "CHG-UNVERIFIED",
            "charger",
            "harbor",
            600,
            verified=False,
        ),

        # A cheap but out-of-stock cable.
        make_offer(
            "CBL-OUT-OF-STOCK",
            "cable",
            "metro",
            99,
            stock=0,
        ),
    ]

    return optimize_basket(
        basket,
        merchants,
        offers,
        budget_minor=budget_inr * 100,
        deadline_minutes=deadline_minutes,
        max_merchants=max_merchants,
    )
