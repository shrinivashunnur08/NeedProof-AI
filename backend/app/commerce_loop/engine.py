"""Bridge to the existing 17C-17E decision engine (the authority for decision states)."""
from __future__ import annotations

import re

from app.commerce_loop.locale import engine_scale
from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c

STATE_TEXT = {
    "PROVISIONAL_VERIFICATION_NEEDED": "Listed in stock, still needs proof",
    "MORE_EVIDENCE_NEEDED": "Not usable yet: out of stock or over budget",
    "DISCOVERY_NEEDED": "No shop offer to evaluate",
    "RESEARCH_CONFLICT": "Conflicting specifications",
}


def spec_check(required: dict, offered: dict) -> dict:
    """Deterministic spec comparison between what the shopper needs and what a shop claims."""
    issues, matches = [], []
    need_w, have_w = required.get("wattage_w"), offered.get("wattage_w")
    if need_w:
        if have_w is None:
            issues.append(f"Wattage not stated (need {need_w}W)")
        elif have_w < need_w:
            issues.append(f"{have_w}W is below the required {need_w}W")
        else:
            matches.append(f"{have_w}W meets {need_w}W")
    need_c, have_c = required.get("connector"), offered.get("connector")
    if need_c and have_c:
        (matches if need_c.casefold() == have_c.casefold() else issues).append(
            f"Connector {have_c}" if need_c.casefold() == have_c.casefold() else f"Connector {have_c}, need {need_c}")
    if required.get("usb_pd"):
        if offered.get("usb_pd") is False:
            issues.append("No USB Power Delivery")
        elif offered.get("usb_pd"):
            matches.append("USB Power Delivery")
    return {"ok": not issues, "issues": issues, "matches": matches}


def required_specs_from_text(text: str) -> dict:
    specs: dict = {}
    m = re.search(r"(\d{2,3})\s*(?:w|watt|watts|瓦)\b", text, re.IGNORECASE)
    if m:
        specs["wattage_w"] = int(m.group(1))
    if re.search(r"usb[\s-]?c|type[\s-]?c", text, re.IGNORECASE):
        specs["connector"] = "USB-C"
    if re.search(r"\bpd\b|power delivery", text, re.IGNORECASE):
        specs["usb_pd"] = True
    return specs


def evaluate_offer(product: str, budget: float | None, price: float, stock: int) -> dict:
    """Run one shop offer through the author's 17C orchestration + 17D passport + 17E queue."""
    budget_value = budget if budget and budget > 0 else price * 1.5
    budget_units, price_units = engine_scale(budget_value, price)
    payload = FreshJourney17C(
        product_query=(product or "requested product")[:150].ljust(3),
        budget_inr=budget_units,
        reported_price_inr=price_units,
        simulated_report="reported_offer" if stock > 0 else "stockout",
        simulation_acknowledged=True,
    )
    result = evaluate_fresh_journey_17c(payload)
    queue = result.get("verification_queue_17e") or {}
    state = queue.get("workflow_state") or (result.get("workflow") or {}).get("workflow_state") or "UNKNOWN"
    actions = queue.get("queue") or queue.get("actions") or []
    next_label = None
    if isinstance(actions, list) and actions:
        first = actions[0]
        next_label = first.get("label") or first.get("title") or first.get("action_id") if isinstance(first, dict) else None
    return {
        "engine": "17C orchestration + 17D passport + 17E next-best-proof",
        "workflow_state": state,
        "state_text": STATE_TEXT.get(state, state.replace("_", " ").title()),
        "next_best_proof": queue.get("recommended_action_id") or next_label,
        "snapshot_sha256": queue.get("snapshot_sha256"),
        "purchase_allowed": bool(result.get("purchase_allowed")),
        "budget_assumed": not (budget and budget > 0),
    }
