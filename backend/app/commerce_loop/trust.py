"""Trust report: how NeedProof decides, how well the AI parts did in live tests, and live outcome counts."""
from __future__ import annotations

import json
import time
from pathlib import Path

from app.commerce_loop import store

HERE = Path(__file__).resolve().parent / "trust"
_BENCH: dict = {}

SAFEGUARDS = [
    {"rule": "A photo is never marked as matching unless a model actually read it",
     "where": "vision.read_photo", "tested": "test_reply_without_photo_or_model_never_matches"},
    {"rule": "Gemini reads the photo; code compares wattage, connector, item type and price",
     "where": "vision.check_photo", "tested": "test_check_photo_rules; eval: 5/5 sample photos"},
    {"rule": "A different item (mixer, cable, adapter) is a conflict, even if the model says it fits",
     "where": "vision._same_item_type", "tested": "eval: mixer and cable photos"},
    {"rule": "Catalog photos from an inventory sheet are labelled weaker than a fresh shelf photo",
     "where": "vision.read_photo(catalog=True)", "tested": "test_inventory_sample_draft_and_approved_reply"},
    {"rule": "Reply drafts can only use real inventory rows; Gemini cannot invent a product or price",
     "where": "inventory.draft_reply", "tested": "eval: 4/4 drafts"},
    {"rule": "No draft is offered for an item that fails a required spec",
     "where": "inventory.draft_reply", "tested": "test_draft_never_offers_wrong_item_or_spec"},
    {"rule": "Nothing is sent to a shopper without the shopkeeper approving it",
     "where": "api.reply_with_photo", "tested": "HTTP 409 without approval"},
    {"rule": "Decision states come from the 17C/17D/17E engine, not from the language model",
     "where": "engine.evaluate_offer", "tested": "Evidence passport on every offer"},
    {"rule": "Text inside photos and shop data is treated as data, not instructions",
     "where": "system prompts", "tested": "eval: prompt-injection message"},
    {"rule": "Shoppers can delete what NeedProof remembers about them",
     "where": "DELETE /shoppers/{id}", "tested": "test_profile_remembers_and_forgets"},
    {"rule": "Every role sees only its screens; the server checks role and shop on every private action",
     "where": "access.require", "tested": "test_roles_are_enforced_when_enabled"},
    {"rule": "A WhatsApp reply link works only for one shop and one request (signed), with no account needed",
     "where": "replylink.valid", "tested": "test_one_tap_reply_link_lets_a_shop_answer_without_an_account"},
    {"rule": "A request reaches only shops that sell that kind of item (a shirt request never reaches phone shops)",
     "where": "agent._route_category + categories.shop_serves", "tested": "test_routing_summary_counts_requests_per_shop_and_category"},
    {"rule": "Public demo has a per-visitor rate limit and a daily AI-call cap",
     "where": "guard.ai_call_guard", "tested": "test_rate_limit_and_daily_cap"},
]

PIPELINE = [
    {"step": "Understand", "who": "Gemini", "what": "Text, voice or a photo of the old charger: extracts item, specs, budget, urgency, place and language; asks one question if a deciding spec is missing"},
    {"step": "Search", "who": "Code + Google Places", "what": "Shop listings and real nearby shops (Google Places, OpenStreetMap fallback); inventory via Vertex AI Search; multi-item baskets via OR-Tools"},
    {"step": "Decide", "who": "NeedProof engine (17C-17E)", "what": "Trust state, unresolved checks and next-best proof for each offer"},
    {"step": "Route", "who": "Gemini + Google Places types", "what": "Gemini picks the kind of shop that sells the item (shop_category); the request reaches only shops of that kind or general stores"},
    {"step": "Ask for proof", "who": "Shops", "what": "Request goes live to onboarded shops (AI drafts from their stock, approved by a person) and to real nearby shops on WhatsApp with a one-tap reply link"},
    {"step": "Check proof", "who": "Gemini Vision + code", "what": "Model reads the photo; rules compare it with the request and flag conflicts"},
    {"step": "Explain", "who": "Gemini", "what": "Writes the answer in the shopper's language from tool results only"},
]


def _eval(name: str) -> dict | None:
    path = HERE / name
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {"model": data["model"], "backend": data["backend"], "run_at": data["run_at"], "tasks": []}
    for key, label in (("intent", "Understanding requests (5 languages + injection)"),
                       ("photo", "Photo proof (Gemini Vision + rules)"),
                       ("draft", "Inventory reply drafts")):
        rows = data.get(key, [])
        ms = sorted(r["ms"] for r in rows)
        out["tasks"].append({"task": label, "passed": sum(r["ok"] for r in rows), "total": len(rows),
                             "median_ms": ms[len(ms) // 2] if ms else None})
    out["photos"] = [{"photo": r["photo"], "got": r["got"], "ok": r["ok"], "summary": r.get("summary")}
                     for r in data.get("photo", [])]
    return out


def _benchmarks() -> dict:
    if _BENCH and time.time() - _BENCH["at"] < 3600:
        return _BENCH["data"]
    from app.benchmarks.engine import run_benchmarks

    started = time.perf_counter()
    d = run_benchmarks(seed=42, basket_scenarios=30, evidence_trials=500)
    data = {"seconds": round(time.perf_counter() - started, 2), "mode": d["mode"],
            "evidence": d["evidence"]["summary"], "basket": d["basket"]["summary"],
            "notes": [d["assumptions"]["evsi_scope"], d["assumptions"]["data"]]}
    _BENCH.update(at=time.time(), data=data)
    return data


def live_stats() -> dict:
    r = store.rows("SELECT COUNT(*) AS n, SUM(status='ANSWERED') AS answered FROM requests")[0]
    statuses = store.rows("SELECT status, COUNT(*) AS n FROM responses GROUP BY status")
    drafts = store.rows("SELECT COUNT(*) AS n FROM responses WHERE inventory_id IS NOT NULL")[0]["n"]
    return {"requests": r["n"] or 0, "answered": r["answered"] or 0, "drafts_approved": drafts,
            "replies_by_status": {s["status"]: s["n"] for s in statuses}}


def report() -> dict:
    try:
        bench = _benchmarks()
    except Exception as exc:  # noqa: BLE001 - optional dependency (OR-Tools) may be missing
        bench = {"error": type(exc).__name__}
    return {"pipeline": PIPELINE, "safeguards": SAFEGUARDS,
            "evals": [e for e in (_eval("eval_ai_studio.json"), _eval("eval_vertex.json")) if e],
            "benchmarks": bench, "live": live_stats(),
            "limits": ["Live tests use 19 hand-written cases and 5 synthetic label photos, not real shop photos.",
                       "Sample shops (labelled), their listings and demand history are fictional; real shops come from Google Places (OpenStreetMap fallback) and only show what they reply.",
                       "Benchmarks are seeded simulations of the decision policy, not field results."]}
