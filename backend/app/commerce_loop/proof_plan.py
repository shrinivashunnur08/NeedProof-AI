"""Is asking a shop for photo proof worth it? One-step EVSI (the author's 14A.1 / app.algorithms.evsi) on live offers.

For every shop that could have the item but has not proven it yet, we estimate:
  prior          - how likely the shop really has a matching item (assumption by evidence level, shown in the UI)
  response rate  - how often this shop has replied to requests in this city (live; 0.6 assumed with no history)
  delay          - this shop's median reply time (live; 5 minutes assumed with no history)
and the EVSI engine returns the expected value of asking minus the cost of waiting. Shops with a positive value
are worth asking first; a shop that already proved it makes asking others less valuable.
"""
from __future__ import annotations

import statistics
from datetime import datetime
from decimal import Decimal

from app.algorithms.evsi import Offer, VerificationAction, plan_verifications
from app.commerce_loop import store

VERIFIED = "PHOTO_MATCHES_REQUEST"
PRIOR = {"listed_ok": Decimal("0.75"), "listed_no_stock": Decimal("0.15"), "map_shop": Decimal("0.30")}
PRIOR_TEXT = {"listed_ok": "listed in stock and meets the specs", "listed_no_stock": "listed but out of stock",
              "map_shop": "real shop nearby, no online listing"}


def _shop_history(city: str, shop_id: str) -> tuple[Decimal, int, bool]:
    asked = store.rows("SELECT COUNT(*) AS n FROM requests WHERE city=?", (city,))[0]["n"]
    replies = store.rows("SELECT r.created_at AS a, q.created_at AS b FROM responses r JOIN requests q ON q.id=r.request_id"
                         " WHERE q.city=? AND r.shop_id=?", (city, shop_id))
    if asked < 3 or not replies:
        return Decimal("0.6"), 5, False
    rate = Decimal(str(round(min(1.0, len(replies) / asked), 2)))
    minutes = statistics.median(
        max(0.0, (datetime.fromisoformat(r["a"]) - datetime.fromisoformat(r["b"])).total_seconds() / 60) for r in replies)
    return max(rate, Decimal("0.05")), max(1, round(minutes)), True


def plan(city: str, offers: list[dict], nearby: list[dict], budget: float | None, currency: str) -> dict:
    prices = [o["price_amount"] for o in offers if o.get("price_amount")]
    budget_value = budget or (max(prices) * 1.5 if prices else 100.0)
    budget_minor = round(budget_value * 100)
    evsi_offers, actions, meta = [], [], {}
    for n, o in enumerate(offers):
        if not o["spec_check"]["ok"]:
            continue
        sku = f"o{n}"
        proven = o["photo_proof"] == VERIFIED
        evsi_offers.append(Offer(sku, o["shop"], round(o["price_amount"] * 100), o["listed_stock"],
                                 proven, proven, proven))
        if proven:
            continue
        level = "listed_ok" if o["listed_stock"] > 0 else "listed_no_stock"
        rate, delay, live = _shop_history(city, o["shop_id"])
        actions.append(VerificationAction(f"ask-{sku}", sku, PRIOR[level], rate, 0, delay))
        meta[f"ask-{sku}"] = {"shop": o["shop"], "shop_id": o["shop_id"], "basis": PRIOR_TEXT[level],
                              "history": "live" if live else "assumed", "price": o["price"]}
    for n, s in enumerate(nearby[:6]):
        if s.get("photo_proof") == VERIFIED:
            continue
        sku = f"m{n}"
        # Price unknown for map shops: assume the median listed price.
        price = round((statistics.median(prices) if prices else budget_value * 0.8) * 100)
        evsi_offers.append(Offer(sku, s["shop"], price, 1, False, False, False))
        rate, delay, live = _shop_history(city, s["shop_id"])
        actions.append(VerificationAction(f"ask-{sku}", sku, PRIOR["map_shop"], rate, 0, delay))
        meta[f"ask-{sku}"] = {"shop": s["shop"], "shop_id": s["shop_id"], "basis": PRIOR_TEXT["map_shop"],
                              "history": "live" if live else "assumed", "price": None}
    if not actions:
        return {"engine": "EVSI one-step (14A.1)", "ranked": [], "verified_available": any(
            o["photo_proof"] == VERIFIED for o in offers), "advice": "Nothing left to verify."}
    result = plan_verifications(evsi_offers, actions, budget_minor=budget_minor, deadline_minutes=24 * 60,
                                fulfillment_value_minor=budget_minor,
                                delay_cost_minor_per_minute=max(1, budget_minor // 500))
    ranked = []
    for ev in result["actions"]:
        m = meta[ev["action_id"]]
        net = float(ev["net_evsi_inr"])
        ranked.append({**m, "p_has_it": ev["prior_feasible"],
                       "reply_chance": ev["response_probability"], "net_value": round(net, 2),
                       "worth_asking": net > 0 and not ev.get("skip_reason"),
                       "skip_reason": ev.get("skip_reason")})
    ranked.sort(key=lambda r: -r["net_value"])
    verified = any(o["photo_proof"] == VERIFIED for o in offers)
    worth = [r for r in ranked if r["worth_asking"]]
    advice = (f"Ask {worth[0]['shop']} first: best chance of a useful answer for the wait."
              if worth else "A shop has already proven it; asking others adds little." if verified
              else "No shop is clearly worth waiting for; consider the nearest listed shop.")
    return {"engine": "EVSI one-step (14A.1, app.algorithms.evsi)", "ranked": ranked[:6], "advice": advice,
            "verified_available": verified, "currency": currency,
            "assumptions": "Chance a shop has it is assumed from its evidence level; reply chance and wait use "
                           "the shop's live history in this app when it has one."}
