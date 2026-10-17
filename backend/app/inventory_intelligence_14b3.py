"""14B.3: offline, evidence-labeled inventory reconciliation and risk scenarios.

No live stock lookup, persistence, external calls, trained fraud model, or purchase
approval. Values are USER-REPORTED observations or labeled synthetic fixtures.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from math import ceil
from statistics import median, mean

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.retail_forecast_14b1 import (
    DailySales14B1, ForecastInput14B1, evaluate_retail_forecast_14b1,
)


class InventoryDay14B3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    opening_units: int = Field(ge=0, le=1_000_000, strict=True)
    received_units: int = Field(ge=0, le=1_000_000, strict=True)
    sold_units: int = Field(ge=0, le=1_000_000, strict=True)
    closing_units: int = Field(ge=0, le=1_000_000, strict=True)
    reported_stockout: bool = Field(default=False, strict=True)


class InventoryInput14B3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku_code: str = Field(min_length=2, max_length=32)
    history: list[InventoryDay14B3] = Field(min_length=42, max_length=90)
    lead_time_days: int = Field(default=7, ge=1, le=14, strict=True)
    synthetic_demo: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def validate_inventory(self):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,31}", self.sku_code):
            raise ValueError("SKU must be a short non-personal identifier (letters, digits, ._-)")
        days = [row.day for row in self.history]
        if days[-1] > date.today():
            raise ValueError("Future-dated inventory observations are not accepted")
        if any(days[i] + timedelta(days=1) != days[i+1] for i in range(len(days)-1)):
            raise ValueError("History must be consecutive ascending daily dates without duplicates")
        return self


def _nearest_rank_quantile(values: list[int], quantile: float) -> int:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered)-1, ceil(quantile*len(ordered))-1))]


def _review_signals(rows: list[InventoryDay14B3]) -> dict:
    """Observed balance differences and robust, past-only sales spike checks."""
    anomalies = []
    totals = {"balance_mismatches": 0, "cross_day_gaps": 0, "sales_spikes": 0, "reported_stockout_days": 0}
    for i, row in enumerate(rows):
        if row.reported_stockout:
            totals["reported_stockout_days"] += 1
        expected = row.opening_units + row.received_units - row.sold_units
        difference = row.closing_units - expected
        if difference:
            totals["balance_mismatches"] += 1
            anomalies.append({"day": row.day.isoformat(), "signal": "BALANCE_DIFFERENCE", "difference_units": difference,
                              "detail": "Closing minus opening+receipts-sales; returns, transfers, losses or errors may explain this."})
        if i > 0:
            gap = row.opening_units - rows[i-1].closing_units
            if gap:
                totals["cross_day_gaps"] += 1
                anomalies.append({"day":row.day.isoformat(),"signal":"CROSS_DAY_DISCONTINUITY", "difference_units":gap,
                                  "detail":"Opening stock differs from previous closing stock; investigate timing or other movements."})
        # Past-only robust reference: never use a current/future observation to set its own threshold.
        if i >= 21 and not row.reported_stockout:
            training = [r.sold_units for r in rows[max(0, i-28):i] if not r.reported_stockout]
            if len(training) >= 14:
                mid = median(training)
                mad = median(abs(x-mid) for x in training)
                # When MAD is zero, use an explicit absolute/multiplicative floor instead of claiming zero variance.
                threshold = mid + max(3.0, 3.5 * 1.4826 * mad, 1.5 * mid)
                if row.sold_units > threshold:
                    totals["sales_spikes"] += 1
                    anomalies.append({"day":row.day.isoformat(),"signal":"UNUSUAL_SALES_SPIKE", "difference_units":None,
                                      "detail":"Sales exceed a past-only robust reference; may reflect a promotion, batch order or reporting issue."})
    signal_rank = {"BALANCE_DIFFERENCE":0, "CROSS_DAY_DISCONTINUITY":1, "UNUSUAL_SALES_SPIKE":2}
    anomalies.sort(key=lambda v:(v["day"],signal_rank[v["signal"]]))
    return {"totals":totals,"total_review_signals":len(anomalies),"signals":anomalies[:15],
            "signals_truncated":len(anomalies)>15,"review_not_fraud_prediction":True}


def _lead_window_exposure(rows: list[InventoryDay14B3], lead: int, on_hand: int, projected: float) -> dict:
    clean_windows = [sum(r.sold_units for r in rows[i:i+lead])
                     for i in range(len(rows)-lead+1)
                     if all(not r.reported_stockout for r in rows[i:i+lead])]
    minimum = max(5, lead)  # need enough windows, still overlapping and sample-dependent
    if len(clean_windows) < minimum:
        return {"status":"INSUFFICIENT_CLEAN_WINDOWS", "clean_windows":len(clean_windows),
                "minimum_clean_windows": minimum, "empirical_80p_units":None, "gap_to_empirical_80p_units":None,
                "reported_on_hand_units":on_hand,"forecast_sales_proxy_units":round(projected,2),
                "forecast_shortfall_scenario_units":round(max(0,projected-on_hand),2),
                "interpretation":"Insufficient uncensored historical windows for an empirical lead-time comparison."}
    quantile = _nearest_rank_quantile(clean_windows,0.8)
    gap = max(0, quantile-on_hand)
    return {"status":"REPLENISHMENT_REVIEW" if gap or projected>on_hand else "NO_MODELED_SHORTFALL",
            "clean_windows":len(clean_windows),"minimum_clean_windows":minimum,
            "empirical_80p_units":quantile,"gap_to_empirical_80p_units":gap,
            "reported_on_hand_units":on_hand,"forecast_sales_proxy_units":round(projected,2),
            "forecast_shortfall_scenario_units":round(max(0,projected-on_hand),2),
            "interpretation":"Descriptive 80th percentile of overlapping historical observed-sales windows; NOT an 80% service-level guarantee or verified future demand."}


def evaluate_inventory_14b3(payload: InventoryInput14B3) -> dict:
    rows = payload.history
    forecast_input = ForecastInput14B1(
        product_label=payload.sku_code,
        history=[DailySales14B1(day=r.day,units_sold=r.sold_units,reported_stockout=r.reported_stockout) for r in rows],
        horizon_days=payload.lead_time_days,
        on_hand_units=rows[-1].closing_units,
        replenishment_lead_days=payload.lead_time_days,
        synthetic_demo=payload.synthetic_demo,
    )
    forecast = evaluate_retail_forecast_14b1(forecast_input)
    projected = sum(p["expected_units"] for p in forecast["predictions"])
    clean = [r.sold_units for r in rows if not r.reported_stockout]
    avg_sales = mean(clean) if clean else 0
    coverage = round(rows[-1].closing_units/avg_sales,2) if avg_sales else None
    anomalies = _review_signals(rows)
    exposure = _lead_window_exposure(rows,payload.lead_time_days,rows[-1].closing_units,projected)
    review_actions = []
    if anomalies["totals"]["balance_mismatches"] or anomalies["totals"]["cross_day_gaps"]:
        review_actions.append("Reconcile reported stock movement with returns, transfers and physical counts before trusting on-hand figures.")
    if anomalies["totals"]["sales_spikes"]:
        review_actions.append("Investigate unusual observed-sales days against promotions, batch orders and input accuracy.")
    if anomalies["totals"]["reported_stockout_days"]:
        review_actions.append("Review stockout-censored sales; zero sales may reflect unavailable inventory rather than no demand.")
    if exposure["status"] == "REPLENISHMENT_REVIEW":
        review_actions.append("Check current stock and supplier lead times before considering replenishment; no order is authorized.")
    if exposure["status"] == "INSUFFICIENT_CLEAN_WINDOWS":
        review_actions.append("Collect additional stockout-free observations before relying on lead-time distribution scenarios.")
    if not review_actions:
        review_actions.append("Continue monitoring and verify any inventory figures before operational use.")
    return {
        "mode":"REPORTED_STOCK_RECONCILIATION_14B3",
        "sku_code":payload.sku_code,
        "data_origin":"CLIENT_LABELED_SYNTHETIC_DEMO" if payload.synthetic_demo else "USER_SUPPLIED_UNVERIFIED",
        "record_count":len(rows),"latest_day":rows[-1].day.isoformat(),
        "reported_closing_units":rows[-1].closing_units,
        "observed_stockout_days":anomalies["totals"]["reported_stockout_days"],
        "average_nonstockout_sales_units":round(avg_sales,2) if clean else None,
        "coverage_days_at_observed_sales_rate":coverage,
        "forecast_model_reused_14b1":forecast["selected_model"],
        "inventory_review":anomalies,
        "lead_time_scenario":exposure,
        "review_actions":review_actions,
        "limitations":[
            "All opening, received, sold and closing quantities are unverified user reports or labeled synthetic fixtures; no supplier, POS, warehouse or physical stock integrations were used.",
            "Inventory movement differences are not fraud findings; returns, transfers, shrinkage and recording cutoffs are not modeled.",
            "Sales spikes are heuristics based only on past non-stockout observations; they can reflect normal promotions or seasonality and are not anomaly-model accuracy claims.",
            "14B.1 forecasts observed SALES, not latent demand; stockout flags are user-reported, and lost sales were not imputed.",
            "Historical lead-time windows overlap and may be biased; empirical 80th percentile is not a calibrated service level or stockout probability.",
            "This tool never authorizes restocking, purchases, fraud accusations, or claims to verified live stock.",
        ],
        "source_records_persisted":False,"cloud_model_used":False,
        "inventory_independently_verified":False,"fraud_determined":False,"purchase_allowed":False,
    }
