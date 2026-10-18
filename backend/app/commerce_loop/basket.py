"""Multi-item basket across nearby shops (live listings), solved with OR-Tools CP-SAT.

Same approach as the author's 14A.2 planner (one offer per basket line, budget, max shops, stock, specs;
minimise total cost), applied to live shop listings. Listings are shop claims, so every line keeps its proof
status; a photo-verified offer wins over a merely listed one at the same price. Nothing is reserved or bought.

Baselines (as in the 17F benchmark): cheapest-item-first and single-shop, so the shopper sees what the
optimiser saved.
"""
from __future__ import annotations

from app.commerce_loop import store
from app.commerce_loop.engine import required_specs_from_text, spec_check
from app.commerce_loop.locale import CITIES, Money

VERIFIED = "PHOTO_MATCHES_REQUEST"


def _proof(city: str, shop_id: str, listing: dict) -> str:
    name = listing["product"]
    for r in store.rows(
            "SELECT r.status, r.inventory_id, q.product AS asked, q.specs AS asked_specs FROM responses r"
            " JOIN requests q ON q.id=r.request_id WHERE q.city=? AND r.shop_id=? ORDER BY r.id DESC LIMIT 10",
            (city, shop_id)):
        if r["inventory_id"]:
            item = store.inventory_item(r["inventory_id"])
            if item and ((item["brand"] + " ") if item["brand"] else "") + item["product"] == name:
                return r["status"]
        elif store.product_key(r["asked"]) == store.product_key(name, listing["specs"]):
            return r["status"]
    return "NONE"


def candidates(city: str, items: list[str], distance=None) -> dict[int, list[dict]]:
    """For each basket line: in-stock listings of the same product type that meet the line's specs."""
    out: dict[int, list[dict]] = {}
    shops = store.shops_in_city(city)
    for idx, text in enumerate(items):
        need = required_specs_from_text(text)
        key = store.product_key(text, need).split()[-1]
        rows = []
        for shop in shops:
            for listing in store.listings_for(shop["id"]):
                if store.product_key(listing["product"], listing["specs"]).split()[-1] != key:
                    continue
                if listing["stock"] <= 0 or not spec_check(need, listing["specs"])["ok"]:
                    continue
                rows.append({"line": idx, "shop_id": shop["id"], "shop": shop["name"], "area": shop["area"],
                             "lat": shop.get("lat"), "lng": shop.get("lng"),
                             "distance_km": distance(shop) if distance else None,
                             "listing": listing["product"], "price": listing["price"],
                             "stock": listing["stock"], "proof": _proof(city, shop["id"], listing)})
        out[idx] = rows
    return out


def plan(city: str, items: list[str], budget: float | None = None, max_shops: int = 2, distance=None) -> dict:
    from ortools.sat.python import cp_model

    items = [i.strip() for i in items if i and i.strip()][:6]
    currency = CITIES[city]["currency"]
    money = lambda v: Money(v, currency).format()  # noqa: E731
    cands = candidates(city, items, distance)
    missing = [items[i] for i, rows in cands.items() if not rows]
    base = {"city": city, "currency": currency, "items": items, "budget": money(budget) if budget else None,
            "max_shops": max_shops, "solver": "OR-Tools CP-SAT (14A.2 approach on live listings)",
            "purchase_allowed": False}
    if missing:
        return {**base, "status": "NO_OFFER_FOR_ITEM", "missing": missing, "lines": [], "shops": []}

    model = cp_model.CpModel()
    offers = [o for rows in cands.values() for o in rows]
    pick = [model.new_bool_var(f"o{n}") for n in range(len(offers))]
    shop_ids = sorted({o["shop_id"] for o in offers})
    use = {s: model.new_bool_var(f"s_{s}") for s in shop_ids}
    for line in range(len(items)):
        model.add_exactly_one(pick[n] for n, o in enumerate(offers) if o["line"] == line)
    for n, o in enumerate(offers):
        model.add_implication(pick[n], use[o["shop_id"]])
    model.add(sum(use.values()) <= max_shops)
    cents = [round(o["price"] * 100) for o in offers]
    if budget:
        model.add(sum(c * p for c, p in zip(cents, pick)) <= round(budget * 100))
    # Minimise cost; then prefer photo-verified offers, fewer shops, shorter distance.
    model.minimize(sum(c * 1000 * p for c, p in zip(cents, pick))
                   + sum(500 * p for o, p in zip(offers, pick) if o["proof"] != VERIFIED)
                   + sum(200 * u for u in use.values())
                   + sum(round((o["distance_km"] or 0) * 10) * p for o, p in zip(offers, pick)))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 2.0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        cheapest_total = sum(min(o["price"] for o in rows) for rows in cands.values())
        return {**base, "status": "NO_PLAN_WITHIN_LIMITS", "lines": [], "shops": [],
                "reason": (f"The cheapest possible basket is {money(cheapest_total)}"
                           + (f", above the budget of {money(budget)}" if budget and cheapest_total > budget else "")
                           + f"; or it needs more than {max_shops} shop{'s' if max_shops != 1 else ''}.")}
    chosen = [o for o, p in zip(offers, pick) if solver.value(p)]
    chosen.sort(key=lambda o: o["line"])
    total = sum(o["price"] for o in chosen)
    by_shop: dict[str, dict] = {}
    for o in chosen:
        s = by_shop.setdefault(o["shop_id"], {"shop_id": o["shop_id"], "shop": o["shop"], "area": o["area"],
                                              "lat": o["lat"], "lng": o["lng"], "distance_km": o["distance_km"],
                                              "items": [], "subtotal": 0.0})
        s["items"].append(o["listing"])
        s["subtotal"] += o["price"]

    # Baselines: cheapest item per line regardless of shops, and best single shop that has everything.
    greedy = [min(rows, key=lambda o: o["price"]) for rows in cands.values()]
    greedy_shops = len({o["shop_id"] for o in greedy})
    single = None
    for sid in shop_ids:
        lines = [min((o for o in rows if o["shop_id"] == sid), key=lambda o: o["price"], default=None)
                 for rows in cands.values()]
        if all(lines):
            t = sum(o["price"] for o in lines)
            if single is None or t < single[1]:
                single = (lines[0]["shop"], t)
    return {
        **base, "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        "lines": [{"item": items[o["line"]], "shop": o["shop"], "shop_id": o["shop_id"], "listing": o["listing"],
                   "price": money(o["price"]), "stock": o["stock"], "proof": o["proof"]} for o in chosen],
        "shops": [{**s, "subtotal": money(s["subtotal"])} for s in by_shop.values()],
        "total": money(total), "total_amount": total,
        "within_budget": (total <= budget) if budget else None,
        "verified_lines": sum(o["proof"] == VERIFIED for o in chosen),
        "baselines": {
            "cheapest_item_first": {"total": money(sum(o["price"] for o in greedy)), "shops": greedy_shops,
                                    "fits_max_shops": greedy_shops <= max_shops},
            "single_shop": {"shop": single[0], "total": money(single[1])} if single else None,
        },
        "solve_ms": round(solver.wall_time * 1000, 1),
        "note": "Prices and stock are the shops' listings (claims) until a photo is checked. Nothing is reserved.",
    }
