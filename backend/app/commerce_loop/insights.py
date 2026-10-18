"""Demand intelligence: unanswered shopper needs become insights and a brief for shops."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from app.commerce_loop import store
from app.commerce_loop.gemini import Gemini, GeminiUnavailable
from app.commerce_loop.locale import CITIES, Money
from app.commerce_loop.providers import get_providers


def city_demand(city: str, days: int = 28) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    events = store.rows("SELECT * FROM demand_events WHERE city=? AND created_at>=? ORDER BY created_at",
                        (city, since.isoformat(timespec="seconds")))
    today = datetime.now(timezone.utc).date()
    groups: dict[str, dict] = {}
    for e in events:
        g = groups.setdefault(e["product_key"], {"product_key": e["product_key"], "product": e["product"], "asks": 0,
                                                 "answered": 0, "budgets": [], "daily": defaultdict(int),
                                                 "live_asks": 0})
        g["asks"] += 1
        g["answered"] += e["answered"]
        g["live_asks"] += 1 if e["source"] == "live_app" else 0
        if e["budget"]:
            g["budgets"].append(e["budget"])
        g["daily"][datetime.fromisoformat(e["created_at"]).date()] += 1
    currency = CITIES[city]["currency"]
    products = []
    for g in groups.values():
        series = [g["daily"].get(today - timedelta(days=d), 0) for d in range(days - 1, -1, -1)]
        last7, prev7 = sum(series[-7:]), sum(series[-14:-7])
        growth = (last7 - prev7) / prev7 if prev7 else (1.0 if last7 else 0.0)
        forecast = round(last7 * (1 + max(-0.5, min(growth, 1.0)) / 2))
        unmet = g["asks"] - g["answered"]
        avg_budget = sum(g["budgets"]) / len(g["budgets"]) if g["budgets"] else None
        products.append({
            "product_key": g["product_key"], "product": g["product"], "asks": g["asks"],
            "answered": g["answered"], "unmet": unmet, "unmet_rate": round(unmet / g["asks"], 2) if g["asks"] else 0,
            "avg_budget": Money(round(avg_budget), currency).format() if avg_budget else None,
            "last_7_days": last7, "previous_7_days": prev7, "growth_pct": round(growth * 100),
            "forecast_next_7_days": forecast, "daily_series": series, "live_asks": g["live_asks"],
        })
    products.sort(key=lambda p: -p["unmet"])
    return {"city": CITIES[city]["name"], "city_id": city, "currency": currency, "window_days": days,
            "products": products,
            "method": "Counts from demand events; 7-day forecast = last week adjusted by half the weekly growth. "
                      "Full profile runs BigQuery ML ARIMA_PLUS (infra/bigquery/).",
            "data_note": "Seeded synthetic history plus live requests made in this app."}


class DemandBrief(BaseModel):
    headline: str = Field(description="One sentence a shop owner understands")
    actions: list[str] = Field(description="Three concrete actions for this week")
    biggest_gap: str = Field(description="The product with the most unanswered demand and why it matters")
    caution: str = Field(description="One sentence on data limits")


BRIEF_SYSTEM = """You write a weekly demand brief for a small local electronics shop.
Use only the numbers provided. Be concrete: name products, counts and budgets. Plain language, no jargon.
Write in the requested language."""


def demand_brief(city: str, language: str = "en", shop_name: str | None = None,
                 gemini: Gemini | None = None, shop_id: str | None = None) -> dict:
    data = city_demand(city)
    from app.commerce_loop.analytics import shop_analytics

    a = shop_analytics(city, shop_id)
    shop_facts = {"forecast_next_7_days_units": a["forecast"]["next_7_days_units"],
                  "forecast_model": a["forecast"]["selected_model"], "on_hand": a["inventory"]["on_hand"],
                  "stock_status": a["inventory"]["status"], "shortfall_units": a["inventory"]["shortfall_units"],
                  "top_basket_rule": next((r for r in a["baskets"]["rules"] if r["if_bought"] == a["forecast"]["product"]),
                                            a["baskets"]["rules"][0] if a["baskets"]["rules"] else None),
                  "segments": [{k: s[k] for k in ("name", "share_pct")} for s in a["segments"]["items"]]}
    top = data["products"][:4]
    compact = [{k: p[k] for k in ("product", "asks", "answered", "unmet", "avg_budget", "last_7_days",
                                  "previous_7_days", "growth_pct", "forecast_next_7_days")} for p in top]
    gemini = gemini or Gemini()
    if not gemini.is_mock:
        try:
            prompt = (f"Shop: {shop_name or 'a local electronics shop'} in {data['city']}. Language: {language}.\n"
                      f"Demand over the last 28 days (asks = shopper requests, unmet = nobody confirmed stock):\n"
                      f"{json.dumps(compact, ensure_ascii=False)}\n"
                      f"This shop's own analytics (charger sales forecast, stock, baskets, segments; synthetic demo history):\n"
                      f"{json.dumps(shop_facts, ensure_ascii=False)}\n"
                      "Use the stock shortfall and the basket rule in the actions when they matter.")
            brief, meta = gemini.generate_json(prompt, DemandBrief, system=BRIEF_SYSTEM)
            return {"brief": brief.model_dump(), "mode": "gemini", "model": meta, "data": compact,
                    "shop_facts": shop_facts}
        except GeminiUnavailable as exc:
            meta = {"error": str(exc)}
    else:
        meta = {}
    p = top[0] if top else None
    brief = DemandBrief(
        headline=(f"{p['unmet']} shoppers in {data['city']} asked for {p['product']} and nobody confirmed stock."
                  if p else "No demand recorded yet."),
        actions=([f"Stock {p['product']} (typical budget {p['avg_budget']}).",
                  f"Reply to open requests with a photo; demand {'grew' if p['growth_pct'] >= 0 else 'changed'} "
                  f"{p['growth_pct']:+}% week on week.",
                  f"Plan for about {p['forecast_next_7_days']} requests next week."]
                 + ([f"Stock: {shop_facts['on_hand']} on hand vs {shop_facts['forecast_next_7_days_units']} forecast sales; "
                     f"bundle a {shop_facts['top_basket_rule']['also_bought']} "
                     f"({round(shop_facts['top_basket_rule']['confidence_pct'])}% of buyers add it)."]
                    if shop_facts["top_basket_rule"] else []) if p else []),
        biggest_gap=p["product"] if p else "",
        caution="Based on seeded demo history plus live app requests.")
    return {"brief": brief.model_dump(), "mode": "mock" if gemini.is_mock else "fallback_mock", "model": meta,
            "data": compact, "shop_facts": shop_facts}


def export_events_ndjson(path: str | Path) -> int:
    """Write demand events as newline-delimited JSON for `bq load` (works on the free BigQuery sandbox)."""
    events = store.rows("SELECT city, product_key, product, budget, currency, answered, source, created_at"
                        " FROM demand_events ORDER BY id")
    with open(path, "w", encoding="utf-8") as fh:
        for e in events:
            e["answered"] = bool(e["answered"])
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    return len(events)


def load_to_bigquery() -> dict:
    """Load events into BigQuery when ANALYTICS_BACKEND=bigquery and credentials exist."""
    p = get_providers()
    if p.analytics_backend != "bigquery" or not p.gcp_project:
        return {"loaded": False, "reason": "ANALYTICS_BACKEND is not bigquery or GOOGLE_CLOUD_PROJECT is unset"}
    try:
        from google.cloud import bigquery  # optional dependency
    except ImportError:
        return {"loaded": False, "reason": "pip install google-cloud-bigquery"}
    tmp = Path(store.db_path()).with_suffix(".ndjson")
    count = export_events_ndjson(tmp)
    client = bigquery.Client(project=p.gcp_project)
    table = f"{p.gcp_project}.{p.bigquery_dataset}.demand_events"
    client.create_dataset(p.bigquery_dataset, exists_ok=True)
    job = client.load_table_from_file(open(tmp, "rb"), table, job_config=bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON, autodetect=True,
        write_disposition="WRITE_TRUNCATE"))
    job.result()
    return {"loaded": True, "rows": count, "table": table}
