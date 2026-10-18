"""'My shop': one shopkeeper's own inventory, demand, missed sales, sales and customers, from live data.

Every request in the shop's city reaches the shop. For each one we work out what happened from this
shop's point of view:
  answered      - this shop replied
  missed        - the shop stocks a matching item (in stock, within budget) but did not reply
  out_of_stock  - the shop lists a matching item but has none left
  over_budget   - the shop's matching item costs more than the shopper's budget
  not_stocked   - the shop has nothing that fits (this is the 'missed sales' list)
Matching uses the same rules as reply drafts (item type, required specs).
"""
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime

from pydantic import BaseModel, Field

from app.commerce_loop import store
from app.commerce_loop.engine import spec_check
from app.commerce_loop.gemini import Gemini, GeminiUnavailable
from app.commerce_loop.inventory import _kind
from app.commerce_loop.locale import CITIES, Money


def _ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _match(req: dict, inventory: list[dict]) -> dict | None:
    """Best inventory row of the same item type that meets the request's specs (ignoring stock and price)."""
    want = _kind(req["product"])
    best = None
    for it in inventory:
        kind = _kind(f"{it['brand'] or ''} {it['product']}")
        if want and kind != want:
            continue
        if not want and store.product_key(it["product"], it["specs"]) != store.product_key(req["product"], req["specs"]):
            continue
        if not spec_check(req["specs"], it["specs"])["ok"]:
            continue
        if best is None or (it["stock"] > 0, -it["price"]) > (best["stock"] > 0, -best["price"]):
            best = it
    return best


def dashboard(shop_id: str, days: int = 28) -> dict:
    shop = store.shop(shop_id)
    if not shop:
        raise LookupError("Shop not found")
    city = shop["city"]
    currency = CITIES[city]["currency"]
    money = lambda v: Money(v, currency).format() if v is not None else None  # noqa: E731
    inventory = store.inventory_for(shop_id)
    from app.commerce_loop.categories import CATEGORIES, shop_serves

    all_reqs = store.rows("SELECT * FROM requests WHERE city=? AND created_at >= datetime('now', ?) ORDER BY id",
                          (city, f"-{days} day"))
    kind = shop.get("kind") or "general"
    # Only requests routed to this kind of shop (Gemini's shop_category vs the shop's Google Places type):
    # an electronics shop's demand and missed sales never include potatoes or shirts.
    reqs = [r for r in all_reqs if shop_serves(kind, r.get("category"))]
    elsewhere = Counter((r.get("category") or "general").replace("|", " + ") for r in all_reqs
                        if not shop_serves(kind, r.get("category")))
    mine = {r["request_id"]: r for r in store.rows(
        "SELECT request_id, MIN(created_at) AS created_at, MAX(status) AS status FROM responses WHERE shop_id=?"
        " GROUP BY request_id", (shop_id,))}
    outcome = Counter()
    missed_sales: dict[str, dict] = {}
    reply_minutes, rows_out = [], []
    item_demand: dict[int, list[float | None]] = defaultdict(list)
    for r in reqs:
        r["specs"] = json.loads(r["specs"] or "{}")
        hit = _match(r, inventory)
        if r["id"] in mine:
            state = "answered"
            reply_minutes.append((_ts(mine[r["id"]]["created_at"]) - _ts(r["created_at"])).total_seconds() / 60)
        elif hit is None:
            state = "not_stocked"
        elif hit["stock"] <= 0:
            state = "out_of_stock"
        elif r["budget"] and hit["price"] > r["budget"]:
            state = "over_budget"
        else:
            state = "missed"
        outcome[state] += 1
        if hit is not None:
            item_demand[hit["id"]].append(r["budget"])
        if state == "not_stocked":
            key = store.product_key(r["product"], r["specs"])
            m = missed_sales.setdefault(key, {"product": r["product"], "specs": r["specs"], "asks": 0, "budgets": []})
            m["asks"] += 1
            if r["budget"]:
                m["budgets"].append(r["budget"])
        rows_out.append({"request_id": r["id"], "product": r["product"], "budget": money(r["budget"]),
                         "state": state, "created_at": r["created_at"],
                         "matched_item": (f"{hit['brand'] + ' ' if hit['brand'] else ''}{hit['product']}" if hit else None),
                         "returning_shopper": bool(r.get("shopper_id")) and store.rows(
                             "SELECT COUNT(*) AS n FROM requests WHERE shopper_id=? AND id<?",
                             (r["shopper_id"], r["id"]))[0]["n"] > 0})

    sales = store.sales_for(shop_id, days)
    units_by_item = Counter()
    for s in sales:
        if s["inventory_id"]:
            units_by_item[s["inventory_id"]] += s["qty"]
    revenue = sum((s["unit_price"] or 0) * s["qty"] for s in sales)

    items = []
    for it in inventory:
        budgets = [b for b in item_demand.get(it["id"], []) if b]
        asks = len(item_demand.get(it["id"], []))
        weekly_need = max(asks, units_by_item.get(it["id"], 0)) * 7 / days
        items.append({
            "id": it["id"], "product": it["product"], "brand": it["brand"], "sku": it["sku"], "specs": it["specs"],
            "price": it["price"], "price_text": money(it["price"]), "stock": it["stock"],
            "image_url": f"/api/v2/loop/media/{shop_id}/{it['image_file']}" if it["image_file"] else None,
            "asks": asks, "sold": units_by_item.get(it["id"], 0),
            "budget_fit_pct": round(100 * sum(b >= it["price"] for b in budgets) / len(budgets)) if budgets else None,
            "median_budget": money(statistics.median(budgets)) if budgets else None,
            "low_stock": it["stock"] == 0 or (asks > 0 and it["stock"] < max(2, round(weekly_need))),
            "updated_at": it["updated_at"],
        })

    missed = sorted(({"product": m["product"], "asks": m["asks"],
                      "median_budget": money(statistics.median(m["budgets"])) if m["budgets"] else None,
                      "suggestion": f"Consider stocking: {m['asks']} shopper{'s' if m['asks'] != 1 else ''} asked"
                                    + (f", typical budget {money(statistics.median(m['budgets']))}" if m["budgets"] else "")}
                     for m in missed_sales.values()), key=lambda x: -x["asks"])

    customers = store.rows(
        "SELECT q.shopper_id, COUNT(DISTINCT q.id) AS requests, MAX(q.created_at) AS last_seen FROM requests q"
        " JOIN responses r ON r.request_id=q.id AND r.shop_id=? WHERE q.shopper_id IS NOT NULL GROUP BY q.shopper_id",
        (shop_id,))
    total = len(reqs)
    reachable = total - outcome["not_stocked"]
    return {
        "shop": {"id": shop["id"], "name": shop["name"], "area": shop["area"], "city": city, "currency": currency,
                 "kind": kind, "kind_label": CATEGORIES.get(kind, {}).get("label", "General store"),
                 "source": shop.get("source")},
        "routing": {"shop_category": kind, "counted": len(reqs),
                    "routed_elsewhere": [{"category": c, "requests": n} for c, n in elsewhere.most_common()],
                    "how": "Gemini picks the shop category for each request; this shop's category comes from its "
                           "Google Places type. Only matching requests count here."},
        "period_days": days,
        "kpis": {
            "requests_reached": total,
            "answered": outcome["answered"],
            "could_serve": reachable,
            "reply_rate_pct": round(100 * outcome["answered"] / reachable) if reachable else None,
            "median_reply_minutes": round(statistics.median(reply_minutes), 1) if reply_minutes else None,
            "units_sold": sum(s["qty"] for s in sales), "revenue": money(revenue) if sales else None,
            "missed_sales_requests": outcome["not_stocked"],
        },
        "outcomes": dict(outcome),
        "inventory": items,
        "missed_sales": missed[:8],
        "requests": list(reversed(rows_out))[:25],
        "customers": {"known": len(customers), "returning": sum(c["requests"] > 1 for c in customers)},
        "sales": [{"product": s["product"], "qty": s["qty"], "price": money(s["unit_price"]), "at": s["created_at"]}
                  for s in reversed(sales)][:10],
        "note": "Live data from this app: requests for this kind of shop in this city, this shop's replies, its "
                "inventory and confirmed sales.",
    }


class ShopBrief(BaseModel):
    headline: str = Field(description="One sentence for this shop owner")
    actions: list[str] = Field(description="Three concrete actions for this week, naming products and numbers")
    watch_out: str = Field(description="One risk to watch (stock, price or missed replies)")


SHOP_BRIEF_SYSTEM = """You coach the owner of one small shop (its category is given). Use only the numbers given.
Only suggest products that fit the shop's category.
Name products, counts and prices. Plain language. Write in the requested language."""


def shop_brief(shop_id: str, language: str = "en", gemini: Gemini | None = None) -> dict:
    d = dashboard(shop_id)
    facts = {"shop": d["shop"]["name"], "shop_category": d["shop"]["kind_label"], "kpis": d["kpis"], "outcomes": d["outcomes"],
             "missed_sales": d["missed_sales"][:4],
             "inventory": [{k: i[k] for k in ("product", "price_text", "stock", "asks", "sold", "budget_fit_pct", "low_stock")}
                           for i in d["inventory"]][:10]}
    gemini = gemini or Gemini()
    if not gemini.is_mock:
        try:
            brief, meta = gemini.generate_json(f"Language: {language}\nShop data: {json.dumps(facts, ensure_ascii=False)}",
                                               ShopBrief, system=SHOP_BRIEF_SYSTEM)
            return {"brief": brief.model_dump(), "mode": "gemini", "model": meta}
        except GeminiUnavailable as exc:
            meta = {"error": str(exc)}
    else:
        meta = {}
    k = d["kpis"]
    top_missed = d["missed_sales"][0] if d["missed_sales"] else None
    low = [i["product"] for i in d["inventory"] if i["low_stock"]]
    actions = []
    if top_missed:
        actions.append(f"Stock {top_missed['product']}: {top_missed['asks']} shopper{'s' if top_missed['asks'] != 1 else ''} asked and you had none.")
    if low:
        actions.append(f"Reorder {', '.join(low[:2])}: stock is low for current demand.")
    if k["could_serve"] and (k["reply_rate_pct"] or 0) < 100:
        actions.append(f"Reply faster: you answered {k['answered']} of {k['could_serve']} requests you could serve.")
    brief = ShopBrief(headline=f"{k['requests_reached']} shoppers near {d['shop']['name']} asked for items in the last "
                               f"{d['period_days']} days; you answered {k['answered']}.",
                      actions=actions[:3] or ["Upload your inventory so NeedProof can match requests to your stock."],
                      watch_out="Based on requests made in this app only.")
    return {"brief": brief.model_dump(), "mode": "mock" if gemini.is_mock else "fallback_mock", "model": meta}
