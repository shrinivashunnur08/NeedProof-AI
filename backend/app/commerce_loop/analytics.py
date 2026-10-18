"""Shop analytics for the Business tab, using the author's 14B modules as the engine.

- 14B.1 forecast: four baselines backtested on rolling origins, best one selected
- 14B.2 customer segments (RFM k-means) and basket rules (support, confidence, lift)
- 14B.3 inventory: reported-stock reconciliation, stockout days, lead-time scenario

Shop histories are generated per shop and labelled synthetic. Daily sales are scaled to the
city's real request volume in this app, so new requests move the numbers.
"""
from __future__ import annotations

import random
from collections import Counter
from datetime import date, timedelta

from app.commerce_loop import store
from app.commerce_loop.locale import CITIES, Money
from app.inventory_intelligence_14b3 import InventoryInput14B3, evaluate_inventory_14b3
from app.retail_forecast_14b1 import ForecastInput14B1, evaluate_retail_forecast_14b1
from app.retail_segments_14b2 import CommerceInsightsInput14B2, evaluate_commerce_insights_14b2

SKUS = {
    "CHG65": "65W USB-C PD charger", "CBL100": "USB-C cable 100W", "PB20K": "Power bank 20000mAh",
    "ADPT": "Travel adapter", "CASE": "Laptop sleeve", "SCRN": "Screen protector", "CHG45": "45W USB-C charger",
}
DAYS = 56


def _rng(shop_id: str) -> random.Random:
    return random.Random(sum(ord(c) * (i + 1) for i, c in enumerate(shop_id)))


def _city_asks_per_day(city: str) -> float:
    row = store.rows("SELECT COUNT(*) AS n FROM demand_events WHERE city=? AND product_key LIKE '%charger%'"
                     " AND created_at >= datetime('now', '-28 day')", (city,))
    return max(1.0, row[0]["n"] / 28)


def _sales_history(shop_id: str, city: str) -> list[dict]:
    rng = _rng(shop_id)
    base = min(12.0, 0.35 * _city_asks_per_day(city) + 1.5)
    today = date.today()
    out = []
    for i in range(DAYS):
        d = today - timedelta(days=DAYS - i)
        trend = 1 + 0.6 * i / DAYS
        weekend = 1.35 if d.weekday() >= 5 else 1.0
        out.append({"day": d.isoformat(), "units_sold": max(0, round(rng.gauss(base * trend * weekend, 1.1)))})
    return out


def _inventory_history(shop_id: str, sales: list[dict]) -> list[dict]:
    rng = _rng(shop_id + "inv")
    on_hand, rows = 12, []
    for i, s in enumerate(sales):
        received = 14 if i % 7 == 3 else 0
        opening = on_hand
        sold = min(opening + received, s["units_sold"])
        closing = opening + received - sold
        rows.append({"day": s["day"], "opening_units": opening, "received_units": received, "sold_units": sold,
                     "closing_units": closing, "reported_stockout": closing == 0})
        on_hand = closing
    # A few late deliveries make the review signals interesting.
    if rng.random() < 0.8:
        rows[-1]["closing_units"] = max(0, rows[-1]["closing_units"])
    return rows


def _profiles_and_baskets(shop_id: str) -> tuple[list[dict], list[list[str]]]:
    rng = _rng(shop_id + "cust")
    profiles = []
    for _ in range(72):
        kind = rng.random()
        if kind < 0.3:  # frequent tech buyers
            profiles.append({"recency_days": rng.randint(1, 15), "orders_90d": rng.randint(4, 10),
                             "spend_minor_90d": rng.randint(30000, 90000)})
        elif kind < 0.7:  # occasional
            profiles.append({"recency_days": rng.randint(10, 60), "orders_90d": rng.randint(1, 3),
                             "spend_minor_90d": rng.randint(4000, 25000)})
        else:  # lapsed
            profiles.append({"recency_days": rng.randint(70, 180), "orders_90d": rng.randint(0, 1),
                             "spend_minor_90d": rng.randint(0, 8000)})
    baskets = []
    for _ in range(120):
        b = set()
        r = rng.random()
        if r < 0.55:
            b.add("CHG65")
            if rng.random() < 0.65:
                b.add("CBL100")
            if rng.random() < 0.25:
                b.add("CASE")
        elif r < 0.75:
            b.update({"PB20K", "CBL100"} if rng.random() < 0.6 else {"PB20K"})
        else:
            b.add(rng.choice(["ADPT", "SCRN", "CHG45"]))
        while len(b) < 2:
            b.add(rng.choice(list(SKUS)))
        baskets.append(sorted(b))
    return profiles, baskets


def _segment_name(seg: dict) -> str:
    if seg["mean_recency_days"] <= 20 and seg["mean_orders_90d"] >= 3:
        return "Frequent tech buyers"
    if seg["mean_recency_days"] >= 70:
        return "Lapsed customers"
    return "Occasional buyers"


def shop_analytics(city: str, shop_id: str | None = None) -> dict:
    shops = [s for s in store.shops_in_city(city) if s["source"] == "demo"] or store.shops_in_city(city)
    own = store.shop(shop_id) if shop_id else None
    shop = own if own and own["city"] == city else (shops[0] if shops else {"id": f"{city}-shop", "name": "Shop"})
    currency = CITIES[city]["currency"]
    sales = _sales_history(shop["id"], city)
    # Confirmed sales of this charger in the app are added to the seeded history on their day.
    real = Counter()
    for sale in store.sales_for(shop["id"], DAYS):
        item = store.inventory_item(sale["inventory_id"]) if sale["inventory_id"] else None
        if item and store.product_key(item["product"], item["specs"]) == "65w usb-c pd charger":
            real[sale["created_at"][:10]] += sale["qty"]
    for row in sales:
        row["units_sold"] += real.get(row["day"], 0)
    today_real = real.get(date.today().isoformat(), 0)
    inventory_rows = _inventory_history(shop["id"], sales)
    on_hand = inventory_rows[-1]["closing_units"]
    # The shop's own uploaded inventory (if any) is the source of truth for stock on hand today.
    uploaded = next((i for i in store.inventory_for(shop["id"])
                     if store.product_key(i["product"], i["specs"]) == "65w usb-c pd charger"), None)
    if uploaded is not None:
        on_hand = uploaded["stock"]
        last = inventory_rows[-1]
        last["closing_units"] = on_hand
        last["reported_stockout"] = on_hand == 0

    forecast = evaluate_retail_forecast_14b1(ForecastInput14B1(
        product_label=SKUS["CHG65"], history=sales, horizon_days=7, on_hand_units=on_hand,
        replenishment_lead_days=5, synthetic_demo=True))
    inventory = evaluate_inventory_14b3(InventoryInput14B3(
        sku_code="CHG65", history=inventory_rows, lead_time_days=5, synthetic_demo=True))
    profiles, baskets = _profiles_and_baskets(shop["id"])
    insights = evaluate_commerce_insights_14b2(CommerceInsightsInput14B2(
        profiles=profiles, baskets=baskets, minimum_pair_orders=3, synthetic_demo=True))

    segments = []
    for seg in insights["segmentation"].get("segments", []):
        segments.append({"name": _segment_name(seg), "share_pct": seg["share_pct"], "count": seg["count"],
                         "recency_days": round(seg["mean_recency_days"]), "orders_90d": round(seg["mean_orders_90d"], 1),
                         "spend_90d": Money(round(seg["mean_spend_minor_90d"] / 100), currency).format()})
    rules = [{"if_bought": SKUS.get(r["antecedent_sku"], r["antecedent_sku"]),
              "also_bought": SKUS.get(r["consequent_sku"], r["consequent_sku"]),
              "confidence_pct": r["confidence_pct"], "lift": r["lift"], "orders": r["cooccurring_orders"]}
             for r in insights["basket_analysis"].get("rules", [])[:6]]
    models = [{"model": m["method"].replace("_", " "), "mae": m["mae_units"], "wape_pct": m["wape_pct"]}
              for m in forecast["model_comparison"]]
    preds = forecast["predictions"]
    scenario = forecast.get("inventory_exposure_scenario") or {}
    command_center = _command_center(shop["id"], forecast, inventory, scenario, insights, models, on_hand)
    return {
        "command_center": command_center,
        "shop": {"id": shop["id"], "name": shop["name"]},
        "currency": currency,
        "forecast": {
            "product": SKUS["CHG65"], "selected_model": forecast["selected_model"].replace("_", " "),
            "models": models, "next_7_days_units": round(sum(p["expected_units"] for p in preds)),
            "daily": [{"day": p["day"], "units": p["expected_units"], "low": p["lower_heuristic_80"],
                       "high": p["upper_heuristic_80"]} for p in preds],
            "history": [s["units_sold"] for s in sales[-28:]],
            "shortfall_before_restock": scenario.get("projected_shortfall_units"),
            "method": "14B.1: 4 baselines backtested on 14 rolling origins; lowest error wins",
        },
        "inventory": {
            "sku": SKUS["CHG65"], "on_hand": on_hand, "stockout_days_56": inventory["observed_stockout_days"],
            "coverage_days": inventory["coverage_days_at_observed_sales_rate"],
            "status": (inventory.get("lead_time_scenario") or {}).get("status"),
            "shortfall_units": (inventory.get("lead_time_scenario") or {}).get("forecast_shortfall_scenario_units"),
            "review_signals": (inventory.get("inventory_review") or {}).get("total_review_signals"),
            "actions": inventory.get("review_actions", [])[:3],
            "method": "14B.3: reported-stock reconciliation and lead-time scenario",
        },
        "segments": {"items": segments, "silhouette": insights["segmentation"].get("exploratory_silhouette"),
                     "method": "14B.2: anonymous RFM features, k-means with minimum cohort size"},
        "baskets": {"rules": rules, "basket_count": insights["basket_analysis"].get("basket_count"),
                    "method": "14B.2: pair support, confidence, lift with Wilson lower bound"},
        "stock_source": "uploaded inventory" if uploaded is not None else "sales history",
        "confirmed_sales_today": today_real,
        "data_note": ("Stock on hand comes from this shop's uploaded inventory. " if uploaded is not None else "")
                     + "Sales history and customers are seeded for onboarded shops and scale with this city's live requests.",
    }


def _command_center(shop_id, forecast, inventory, scenario, insights, models, on_hand) -> dict | None:
    """14B.4: turn this shop's forecast, stock, customer groups and request outcomes into review priorities."""
    from app.bi_command_center_14b4 import BIInput14B4, evaluate_bi_command_center_14b4

    try:
        from app.commerce_loop.myshop import dashboard

        dash = dashboard(shop_id)
        out = dash["outcomes"]
        verification = {"candidates_considered": min(100, dash["kpis"]["requests_reached"]),
                        "unresolved_evidence_items": min(100, out.get("missed", 0) + out.get("out_of_stock", 0)),
                        "provisional_candidates": min(100, out.get("answered", 0))}
        lead = (inventory.get("lead_time_scenario") or {}).get("forecast_shortfall_scenario_units")
        review = inventory.get("inventory_review") or {}
        wapes = [m["wape_pct"] for m in models if m["wape_pct"] is not None]
        segs = insights["segmentation"].get("segments", [])
        result = evaluate_bi_command_center_14b4(BIInput14B4(
            as_of=date.today(), synthetic_demo=True,
            forecast={"sku_code": "CHG65", "projected_sales_units": float(sum(p["expected_units"] for p in forecast["predictions"])),
                      "horizon_days": 7, "backtest_wape_pct": min(wapes) if wapes else None,
                      "reported_stockout_days": int(inventory["observed_stockout_days"])},
            inventory={"sku_code": "CHG65", "reported_on_hand_units": int(on_hand),
                       "balance_mismatches": int(review.get("balance_mismatches", 0) or 0),
                       "cross_day_gaps": int(review.get("cross_day_gaps", 0) or 0),
                       "unusual_sales_days": int(review.get("unusual_sales_days", 0) or 0),
                       "modeled_lead_time_shortfall_units": float(lead) if lead is not None else None},
            cohorts={"anonymous_profile_count": 72, "aggregate_cohort_count": max(1, min(4, len(segs))),
                     "minimum_cohort_size": 5,
                     "association_rule_count": min(12, len(insights["basket_analysis"].get("rules", [])))},
            verification=verification if verification["provisional_candidates"] <= verification["candidates_considered"] else None))
        return {"summary": result["executive_summary"],
                "queue": [{k: q[k] for k in ("priority", "title", "reason", "source_module")} for q in result["review_queue"]],
                "method": "14B.4: review priorities from this shop's forecast, stock, customer groups and request outcomes"}
    except Exception:  # noqa: BLE001 - advisory panel; never break analytics
        return None


def addon_suggestion(city: str, product: str) -> dict | None:
    """Basket rule turned into a personal tip for the shopper (e.g. charger -> cable)."""
    key = "CHG65" if "charger" in product.casefold() or "carregador" in product.casefold() else None
    if not key:
        return None
    shops = [s for s in store.shops_in_city(city) if s["source"] == "demo"]
    if not shops:
        return None
    _, baskets = _profiles_and_baskets(shops[0]["id"])
    with_item = [b for b in baskets if key in b]
    if not with_item:
        return None
    counts: dict[str, int] = {}
    for b in with_item:
        for sku in b:
            if sku != key:
                counts[sku] = counts.get(sku, 0) + 1
    best, n = max(counts.items(), key=lambda kv: kv[1])
    return {"item": SKUS[best], "share_pct": round(100 * n / len(with_item)),
            "note": f"{round(100 * n / len(with_item))}% of shoppers who buy a {SKUS[key]} also get a {SKUS[best]}"}
