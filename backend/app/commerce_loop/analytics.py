"""Shop analytics for the Business tab, using the author's 14B modules as the engine.

- 14B.1 forecast: four baselines backtested on rolling origins, best one selected
- 14B.2 customer segments (RFM k-means) and basket rules (support, confidence, lift)
- 14B.3 inventory: reported-stock reconciliation, stockout days, lead-time scenario

Two kinds of shop:
- Sample shops (fictional, source='demo'): sales history and customers are generated per shop and labelled
  sample data; daily sales scale with the city's real request volume in this app.
- Real shops (Google Places / OpenStreetMap): nothing is generated. Analytics use only the shop's uploaded
  sales file, its uploaded stock, sales confirmed in the app, and requests for its category. Each engine runs
  only when there is enough real data, and says what is missing otherwise.
"""
from __future__ import annotations

import random
from collections import Counter
from datetime import date, timedelta

from app.commerce_loop import store
from app.commerce_loop.locale import CITIES, Money
from app.inventory_intelligence_14b3 import InventoryInput14B3, evaluate_inventory_14b3
from app.retail_forecast_14b1 import ForecastInput14B1, evaluate_retail_forecast_14b1
from app.retail_segments_14b2 import (
    CommerceInsightsInput14B2,
    evaluate_commerce_insights_14b2,
)

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
    if own and own["city"] == city and own.get("source") != "demo":
        return real_shop_analytics(own)
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
        "mode": "sample",
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
                     + "Sample data: this is a fictional shop. Its sales history and customers are generated "
                       "(they scale with this city's live requests) to show how the analytics work.",
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
            "note": f"In sample shop sales, {round(100 * n / len(with_item))}% of people who buy a {SKUS[key]} also get a {SKUS[best]}"}


# ---------------- real shops: only real data ----------------
MIN_FORECAST_DAYS = 42
MIN_CUSTOMERS = 24
MIN_BASKETS = 24


def _same_product(a: str, b: str) -> bool:
    a, b = a.casefold().strip(), b.casefold().strip()
    return a == b or a in b or b in a


def real_shop_analytics(shop: dict) -> dict:
    from statistics import median

    from app.commerce_loop.categories import CATEGORIES
    from app.commerce_loop.myshop import dashboard

    city = shop["city"]
    currency = CITIES[city]["currency"]
    money = lambda v: Money(round(v, 2), currency).format()  # noqa: E731
    today = date.today()
    sales = store.sales_for(shop["id"], 180)
    for x in sales:
        x["day"] = date.fromisoformat(x["created_at"][:10])
    inventory = store.inventory_for(shop["id"])
    readiness = []

    # What shoppers asked this kind of shop for, in this app (real requests).
    dash = dashboard(shop["id"])
    asked: dict[str, dict] = {}
    for r in dash["requests"]:
        a = asked.setdefault(r["product"].casefold(), {"product": r["product"], "asks": 0, "answered": 0})
        a["asks"] += 1
        a["answered"] += r["state"] == "answered"
    demand = {"requests": dash["kpis"]["requests_reached"], "answered": dash["kpis"]["answered"],
              "top_asked": sorted(asked.values(), key=lambda x: -x["asks"])[:6], "missed": dash["missed_sales"][:5],
              "routed_elsewhere": dash["routing"]["routed_elsewhere"]}

    # Sales summary.
    units_by_product: Counter = Counter()
    for x in sales:
        units_by_product[x["product"]] += x["qty"]
    revenue = sum((x["unit_price"] or 0) * x["qty"] for x in sales)
    bills = {x["bill_id"] for x in sales if x.get("bill_id")}
    customers = {x["customer_ref"] for x in sales if x.get("customer_ref")}
    first_day = min((x["day"] for x in sales), default=None)
    summary = {"rows": len(sales), "units": sum(x["qty"] for x in sales), "revenue": money(revenue) if revenue else None,
               "first_day": first_day.isoformat() if first_day else None,
               "last_day": max(x["day"] for x in sales).isoformat() if sales else None,
               "days_with_sales": len({x["day"] for x in sales}), "bills": len(bills), "customers": len(customers),
               "uploaded_rows": sum(x.get("source") == "upload" for x in sales),
               "top_products": [{"product": p, "units": u} for p, u in units_by_product.most_common(5)]}

    # 14B.1 forecast for the best-selling product, only on real daily history.
    forecast = None
    top = units_by_product.most_common(1)[0][0] if units_by_product else None
    if top:
        first = min(x["day"] for x in sales if x["product"] == top)
        span = (today - first).days + 1
        if span >= MIN_FORECAST_DAYS:
            per_day = Counter()
            for x in sales:
                if x["product"] == top:
                    per_day[x["day"]] += x["qty"]
            start = max(first, today - timedelta(days=179))
            history = [{"day": (start + timedelta(days=i)).isoformat(), "units_sold": per_day.get(start + timedelta(days=i), 0)}
                       for i in range((today - start).days + 1)]
            stock_row = next((i for i in inventory if _same_product(i["product"], top)), None)
            try:
                fc = evaluate_retail_forecast_14b1(ForecastInput14B1(
                    product_label=top[:100] if len(top) >= 2 else top + " ", history=history, horizon_days=7,
                    on_hand_units=stock_row["stock"] if stock_row else None,
                    replenishment_lead_days=5 if stock_row else None))
                preds = fc["predictions"]
                forecast = {
                    "product": top, "selected_model": fc["selected_model"].replace("_", " "),
                    "models": [{"model": m["method"].replace("_", " "), "mae": m["mae_units"], "wape_pct": m["wape_pct"]}
                               for m in fc["model_comparison"]],
                    "next_7_days_units": round(sum(p["expected_units"] for p in preds)),
                    "daily": [{"day": p["day"], "units": p["expected_units"], "low": p["lower_heuristic_80"],
                               "high": p["upper_heuristic_80"]} for p in preds],
                    "history": [h["units_sold"] for h in history[-28:]],
                    "shortfall_before_restock": (fc.get("inventory_exposure_scenario") or {}).get("projected_shortfall_units"),
                    "method": f"14B.1 on your sales: {len(history)} days of {top}; 4 baselines backtested, lowest error wins"}
                readiness.append({"module": "Sales forecast", "ready": True, "detail": f"{len(history)} days of sales for {top}"})
            except Exception as exc:  # noqa: BLE001 - explain instead of failing the page
                readiness.append({"module": "Sales forecast", "ready": False, "detail": f"Could not run on this data: {exc}"[:160]})
        else:
            readiness.append({"module": "Sales forecast", "ready": False,
                              "detail": f"Needs {MIN_FORECAST_DAYS}+ days of sales for one product; {top} has {span}"})
    else:
        readiness.append({"module": "Sales forecast", "ready": False,
                          "detail": f"Needs {MIN_FORECAST_DAYS}+ days of sales: upload your sales file"})

    # Stock cover: uploaded stock / average daily sales (last 28 days). No stock history is invented.
    inv_card = None
    if inventory:
        recent = Counter()
        for x in sales:
            if (today - x["day"]).days < 28:
                recent[x["product"]] += x["qty"]
        rows_cover = []
        for item in inventory:
            sold28 = sum(u for p, u in recent.items() if _same_product(p, item["product"]))
            rate = sold28 / 28
            rows_cover.append({"product": item["product"], "on_hand": item["stock"],
                               "per_day": round(rate, 2), "coverage_days": round(item["stock"] / rate, 1) if rate else None})
        rows_cover.sort(key=lambda r: (r["coverage_days"] is None, r["coverage_days"] or 0))
        low = [r for r in rows_cover if r["on_hand"] == 0 or (r["coverage_days"] is not None and r["coverage_days"] < 5)]
        inv_card = {"items": rows_cover[:8], "low": len(low),
                    "method": "Your uploaded stock ÷ your average daily sales over the last 28 days; under 5 days = reorder"}
        readiness.append({"module": "Stock cover", "ready": True,
                          "detail": f"{len(inventory)} stock rows" + ("" if sales else "; add sales to see days of cover")})
    else:
        readiness.append({"module": "Stock cover", "ready": False, "detail": "Upload your stock sheet in My shop"})

    # 14B.2 customer groups + bought-together, only with enough real customers and bills.
    segments = baskets = None
    profiles = []
    for cref in customers:
        mine = [x for x in sales if x.get("customer_ref") == cref]
        last = max(x["day"] for x in mine)
        in90 = [x for x in mine if (today - x["day"]).days < 90]
        profiles.append({"recency_days": min(365, (today - last).days),
                         "orders_90d": min(200, len({x.get("bill_id") or x["day"].isoformat() for x in in90})),
                         "spend_minor_90d": min(200_000_000, int(sum((x["unit_price"] or 0) * x["qty"] for x in in90) * 100))})
    groups: dict[str, set] = {}
    for x in sales:
        key = x.get("bill_id") or (f"{x['customer_ref']}|{x['day']}" if x.get("customer_ref") else None)
        if key:
            groups.setdefault(key, set()).add(x["product"])
    top30 = [p for p, _ in units_by_product.most_common(30)]
    code = {p: f"P{i + 1}" for i, p in enumerate(top30)}
    name = {v: k for k, v in code.items()}
    bsk = [sorted(code[p] for p in g if p in code)[:8] for g in groups.values()]
    bsk = [b for b in bsk if len(b) >= 2][-200:]
    if len(profiles) >= MIN_CUSTOMERS and len(bsk) >= MIN_BASKETS and len({c for b in bsk for c in b}) >= 2:
        ins = evaluate_commerce_insights_14b2(CommerceInsightsInput14B2(
            profiles=sorted(profiles, key=lambda p: p["recency_days"])[:120], baskets=bsk, minimum_pair_orders=3))
        segments = {"items": [{"name": _segment_name(g).replace("tech ", ""), "share_pct": g["share_pct"], "count": g["count"],
                               "recency_days": round(g["mean_recency_days"]), "orders_90d": round(g["mean_orders_90d"], 1),
                               "spend_90d": Money(round(g["mean_spend_minor_90d"] / 100), currency).format()}
                              for g in ins["segmentation"].get("segments", [])],
                    "silhouette": ins["segmentation"].get("exploratory_silhouette"),
                    "method": f"14B.2 on your sales: {len(profiles)} anonymous customers, k-means on recency, orders, spend"}
        baskets = {"rules": [{"if_bought": name.get(r["antecedent_sku"], r["antecedent_sku"]),
                              "also_bought": name.get(r["consequent_sku"], r["consequent_sku"]),
                              "confidence_pct": r["confidence_pct"], "lift": r["lift"], "orders": r["cooccurring_orders"]}
                             for r in ins["basket_analysis"].get("rules", [])[:6]],
                   "basket_count": len(bsk), "method": "14B.2 on your bills: pair support, confidence, lift (Wilson lower bound)"}
        readiness.append({"module": "Customer groups and bought-together", "ready": True,
                          "detail": f"{len(profiles)} customers, {len(bsk)} bills with 2+ items"})
    else:
        readiness.append({"module": "Customer groups and bought-together", "ready": False,
                          "detail": f"Needs {MIN_CUSTOMERS}+ customers (have {len(profiles)}) and {MIN_BASKETS}+ bills with "
                                    f"2+ items (have {len(bsk)}): include Bill no and Customer columns in your sales file"})
    readiness.insert(0, {"module": "Shopper demand for your category", "ready": True,
                         "detail": f"{demand['requests']} requests in this app"})

    return {
        "mode": "real", "shop": {"id": shop["id"], "name": shop["name"], "source": shop.get("source"),
                                 "kind_label": CATEGORIES.get(shop.get("kind") or "", {}).get("label", "General store")},
        "currency": currency, "demand": demand, "sales_summary": summary, "readiness": readiness,
        "forecast": forecast, "stock_cover": inv_card, "inventory": None, "segments": segments, "baskets": baskets,
        "command_center": None, "stock_source": "uploaded inventory" if inventory else None,
        "median_budget_note": None if not sales else f"median line value {money(median([(x['unit_price'] or 0) * x['qty'] for x in sales]))}",
        "data_note": "Real shop: everything here comes from this shop's own uploaded sales and stock, sales confirmed in "
                     "the app, and shopper requests for its category. Nothing is generated; each analysis runs once "
                     "there is enough data.",
    }
