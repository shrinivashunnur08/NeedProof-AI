"""Engine room: the author's NeedProof engines, what each does, where it runs in the app, and a live run.

Each 'run' uses the app's current live data where the engine has a place in the flow (listings, shop analytics,
requests), so judges can see the engine behind each screen. Retired showcase panels are listed with what
replaced them, so no dead buttons remain.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.commerce_loop import store

SAMPLE_SHEET = ("VoltPro VP-65C GaN laptop charger, 65W max. USB PD supported. Output 20V/3250mA. "
                "Supplied cable rated 5A.")


def _run_decision() -> dict:
    from app.commerce_loop.engine import evaluate_offer

    listing = next(item for s in store.shops_in_city("singapore") for item in store.listings_for(s["id"])
                   if "65W" in item["product"])
    d = evaluate_offer(listing["product"], 60, listing["price"], listing["stock"])
    return {"input": f"{listing['product']} at S${listing['price']:g}, listed stock {listing['stock']}, budget S$60",
            "result": {"decision": d["state_text"], "trust_state": d["trust_state"], "next_best_proof": d["next_best_proof"],
                       "unresolved": d["unresolved"][:3], "purchase_allowed": d["purchase_allowed"]}}


def _offers_for(product: str) -> list[dict]:
    from app.commerce_loop.engine import required_specs_from_text, spec_check

    need = required_specs_from_text(product)
    out = []
    for s in store.shops_in_city("singapore"):
        for item in store.listings_for(s["id"]):
            if store.product_key(item["product"], item["specs"]).split()[-1] != "charger":
                continue
            out.append({"shop": s["name"], "shop_id": s["id"], "price_amount": item["price"], "price": f"S${item['price']:g}",
                        "listed_stock": item["stock"], "spec_check": spec_check(need, item["specs"]), "photo_proof": "NONE"})
    return out


def _run_evsi() -> dict:
    from app.commerce_loop.proof_plan import plan

    p = plan("singapore", _offers_for("65W USB-C PD charger"), [], 60, "SGD")
    return {"input": "65W USB-C PD charger, budget S$60, live Singapore listings",
            "result": {"advice": p["advice"], "ranked": [{k: r[k] for k in ("shop", "p_has_it", "net_value", "worth_asking")}
                                                          for r in p["ranked"]]}}


def _run_basket() -> dict:
    from app.commerce_loop.basket import plan

    b = plan("singapore", ["65W USB-C PD charger", "USB-C cable", "power bank"], 120, 2)
    return {"input": "charger + cable + power bank, budget S$120, at most 2 shops",
            "result": {"status": b["status"], "total": b.get("total"), "lines": [f"{ln['shop']}: {ln['listing']} {ln['price']}"
                                                                               for ln in b.get("lines", [])],
                       "baselines": b.get("baselines"), "solver": b["solver"]}}


def _analytics() -> dict:
    from app.commerce_loop.analytics import shop_analytics

    return shop_analytics("singapore", "sg-harbour")


def _run_forecast() -> dict:
    f = _analytics()["forecast"]
    return {"input": "Harbour Tech, 56 days of 65W charger sales", "result": {
        "selected_model": f["selected_model"], "next_7_days_units": f["next_7_days_units"],
        "models": f["models"]}}


def _run_segments() -> dict:
    a = _analytics()
    return {"input": "Harbour Tech customers (anonymous RFM) and 120 baskets", "result": {
        "segments": [{k: s[k] for k in ("name", "share_pct")} for s in a["segments"]["items"]],
        "top_rules": [f"{r['if_bought']} → {r['also_bought']} ({round(r['confidence_pct'])}%)" for r in a["baskets"]["rules"][:3]]}}


def _run_inventory() -> dict:
    i = _analytics()["inventory"]
    return {"input": "Harbour Tech stock history, 5-day supplier lead time", "result": {
        k: i[k] for k in ("on_hand", "stockout_days_56", "status", "shortfall_units", "review_signals")}}


def _run_command() -> dict:
    c = _analytics()["command_center"] or {}
    return {"input": "Harbour Tech forecast + stock + customer groups + request outcomes",
            "result": {"summary": c.get("summary"), "queue": [q["title"] for q in c.get("queue", [])]}}


def _run_research() -> dict:
    from app.product_retrieval_13c2 import RetrievalInput, retrieve_and_review

    d = retrieve_and_review(RetrievalInput(query="65W USB-C PD charger for Dell XPS 13", review={
        "product_label": "VoltPro VP-65C 65W charger", "device_model": "Dell XPS 13", "device_supports_usb_pd": True,
        "required_power_w": 45, "required_voltage_v": 20,
        "sources": [{"source_id": "voltpro-sheet", "title": "VoltPro VP-65C spec sheet",
                     "captured_at": datetime.now(timezone.utc).isoformat(), "excerpt": SAMPLE_SHEET, "facts": []}]}))
    r = d["review"]
    return {"input": f"Spec sheet excerpt: “{SAMPLE_SHEET}” vs a Dell XPS 13 (needs 20V, 45W, USB PD)",
            "result": {"status": r["status"], "cited_facts": [f"{f['kind']}: {f['quote']}" for f in r["cited_facts"]],
                       "gaps": [g["kind"] for g in r["evidence_gaps"]],
                       "next": r["compatibility"]["recommended_next_action"], "retrieval": d["retrieval_method"]}}


def _run_benchmark() -> dict:
    from app.commerce_loop.trust import _benchmarks

    b = _benchmarks()
    ev = {k: f"net value ₹{v['average_realized_net_utility_inr']}, {v['average_checks']} checks, "
             f"{v['failed_selection_rate_pct']}% wrong picks" for k, v in (b.get("evidence") or {}).items()}
    bk = {k: f"{v['feasibility_rate_pct']}% feasible, ₹{v['mean_extra_cost_vs_needproof_inr']} extra vs NeedProof"
          for k, v in (b.get("basket") or {}).items()}
    return {"input": "Seeded simulation: 500 evidence trials, 30 basket scenarios",
            "result": {"when to ask for proof": ev, "building a basket": bk}}


ENGINES = [
    {"id": "decision", "chunk": "17C · 17D · 17E", "name": "Decision engine, Evidence Passport, Next-best proof",
     "what": "Turns an offer into a decision state, a trust level, open checks and the single most useful next proof.",
     "used_in": "Shopper → every offer card → 'Why this answer? See the evidence'", "status": "live", "run": _run_decision},
    {"id": "evsi", "chunk": "14A.1", "name": "Proof planner (EVSI)",
     "what": "Decides which shops are worth asking for proof: expected value of an answer minus the cost of waiting.",
     "used_in": "Shopper → 'Who is worth asking for proof first'", "status": "live", "run": _run_evsi},
    {"id": "basket", "chunk": "14A.2", "name": "Multi-item basket optimiser (OR-Tools)",
     "what": "Cheapest way to buy several items across shops within a budget and a maximum number of shops.",
     "used_in": "Shopper → ask for several items at once", "status": "live", "run": _run_basket},
    {"id": "forecast", "chunk": "14B.1", "name": "Sales forecast",
     "what": "Backtests four forecasting methods on rolling origins and keeps the most accurate one.",
     "used_in": "Business → Shop analytics → Sales forecast", "status": "live", "run": _run_forecast},
    {"id": "segments", "chunk": "14B.2", "name": "Customer groups and basket analysis",
     "what": "Anonymous recency-frequency-spend groups (k-means) and bought-together rules with confidence and lift.",
     "used_in": "Business → Customer segments, Basket analysis; Shopper → add-on tip", "status": "live", "run": _run_segments},
    {"id": "inventory", "chunk": "14B.3", "name": "Inventory review",
     "what": "Checks the stock record for gaps and stockouts and models the shortfall before the next delivery.",
     "used_in": "Business → Inventory risk; Shop → My shop", "status": "live", "run": _run_inventory},
    {"id": "command", "chunk": "14B.4", "name": "Business command centre",
     "what": "Combines forecast, stock, customer groups and request outcomes into ranked review priorities.",
     "used_in": "Business → Review priorities", "status": "live", "run": _run_command},
    {"id": "research", "chunk": "13C.1 · 13C.2", "name": "Spec-sheet check (product research)",
     "what": "Finds the cited passages in a spec sheet and checks voltage, power and USB PD against the device.",
     "used_in": "Engine room only for now (needs a spec sheet from the shop)", "status": "available", "run": _run_research},
    {"id": "benchmark", "chunk": "17F", "name": "Benchmarks",
     "what": "Seeded comparison of NeedProof's policies against simple alternatives.",
     "used_in": "Trust report → Decision engine benchmarks", "status": "live", "run": _run_benchmark},
]

RETIRED = [
    {"chunk": "13B", "name": "Merchant evidence desk and onboarding", "replaced_by": "Shop → inventory upload and photo replies with AI drafts"},
    {"chunk": "16A · 16C", "name": "Guided journey and judge replay", "replaced_by": "The live Shopper → Shop → Business flow"},
    {"chunk": "17G", "name": "Jury evidence page", "replaced_by": "Trust report"},
    {"chunk": "Cloud preview", "name": "Panels that called the separate Firebase-authenticated cloud API",
     "replaced_by": "One backend on Cloud Run with Vertex AI (this app)"},
    {"chunk": "Desks", "name": "Assurance, transaction-safety and technical review desks",
     "replaced_by": "Evidence Passport on every offer, safeguards in the Trust report"},
]


def catalog() -> dict:
    return {"engines": [{k: v for k, v in e.items() if k != "run"} for e in ENGINES], "retired": RETIRED}


def run(engine_id: str) -> dict:
    import time

    engine = next((e for e in ENGINES if e["id"] == engine_id), None)
    if engine is None:
        raise LookupError("Unknown engine")
    started = time.perf_counter()
    out = engine["run"]()
    return {"id": engine_id, "ms": round((time.perf_counter() - started) * 1000, 1), **out}
