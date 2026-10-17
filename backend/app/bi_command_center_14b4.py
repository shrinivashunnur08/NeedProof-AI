"""NeedProof 14B.4 — offline BI synthesis of caller-supplied AGGREGATE scenarios.

These are unverified supplied summaries, not trusted copies of upstream computations,
warehouse reads, live stock, customer profiles, or independently validated outcomes.
No persistence, external calls, Google Cloud resources or purchase authority.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ORIGIN = Literal["USER_SUPPLIED_UNVERIFIED_AGGREGATE", "CLIENT_LABELED_SYNTHETIC_DEMO"]


class _SafeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ForecastAggregate14B4(_SafeModel):
    sku_code: str = Field(min_length=2, max_length=32)
    projected_sales_units: float = Field(ge=0, le=10_000_000, allow_inf_nan=False)
    horizon_days: int = Field(ge=1, le=14, strict=True)
    backtest_wape_pct: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    reported_stockout_days: int = Field(ge=0, le=180, strict=True)


class InventoryAggregate14B4(_SafeModel):
    sku_code: str = Field(min_length=2, max_length=32)
    reported_on_hand_units: int = Field(ge=0, le=1_000_000, strict=True)
    balance_mismatches: int = Field(ge=0, le=90, strict=True)
    cross_day_gaps: int = Field(ge=0, le=90, strict=True)
    unusual_sales_days: int = Field(ge=0, le=90, strict=True)
    modeled_lead_time_shortfall_units: float | None = Field(default=None, ge=0, le=10_000_000, allow_inf_nan=False)


class CohortAggregate14B4(_SafeModel):
    anonymous_profile_count: int = Field(ge=24, le=120, strict=True)
    aggregate_cohort_count: int = Field(ge=1, le=4, strict=True)
    minimum_cohort_size: int = Field(ge=5, le=120, strict=True)
    association_rule_count: int = Field(ge=0, le=12, strict=True)

    @model_validator(mode="after")
    def plausible_cohorts(self):
        if self.minimum_cohort_size * self.aggregate_cohort_count > self.anonymous_profile_count:
            raise ValueError("Minimum cohort size exceeds aggregate profile count")
        return self


class VerificationAggregate14B4(_SafeModel):
    candidates_considered: int = Field(ge=0, le=100, strict=True)
    unresolved_evidence_items: int = Field(ge=0, le=100, strict=True)
    provisional_candidates: int = Field(ge=0, le=100, strict=True)

    @model_validator(mode="after")
    def plausible_candidates(self):
        if self.provisional_candidates > self.candidates_considered:
            raise ValueError("Provisional candidates exceed candidates considered")
        return self


class BIInput14B4(_SafeModel):
    as_of: date
    synthetic_demo: bool = Field(default=False, strict=True)
    forecast: ForecastAggregate14B4 | None = None
    inventory: InventoryAggregate14B4 | None = None
    cohorts: CohortAggregate14B4 | None = None
    verification: VerificationAggregate14B4 | None = None

    @model_validator(mode="after")
    def validate_bundle(self):
        if self.as_of > date.today():
            raise ValueError("Future-dated aggregate snapshots are not accepted")
        if not any((self.forecast, self.inventory, self.cohorts, self.verification)):
            raise ValueError("Supply at least one aggregate summary")
        for part in (self.forecast, self.inventory):
            if part is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,31}", part.sku_code):
                raise ValueError("SKU must be a non-personal short product code")
        if self.forecast and self.inventory and self.forecast.sku_code != self.inventory.sku_code:
            raise ValueError("Forecast and inventory summaries must describe the same SKU")
        return self


def evaluate_bi_command_center_14b4(data: BIInput14B4) -> dict:
    """Produce deterministic review priorities, not probabilities or executive proof."""
    origin: ORIGIN = ("CLIENT_LABELED_SYNTHETIC_DEMO" if data.synthetic_demo
                      else "USER_SUPPLIED_UNVERIFIED_AGGREGATE")
    supplied = {"forecast": data.forecast is not None,
                "inventory": data.inventory is not None,
                "cohorts": data.cohorts is not None,
                "verification": data.verification is not None}
    missing = [key for key, present in supplied.items() if not present]
    days_old = (date.today() - data.as_of).days
    metrics: list[dict] = []
    actions: list[dict] = []

    def metric(key: str, label: str, value: float | int, unit: str, module: str, meaning: str):
        metrics.append({"key": key, "label": label, "value": value, "unit": unit,
                        "source_module": module, "data_origin": origin,
                        "interpretation": meaning})

    def action(key: str, priority: int, source: str, title: str, reason: str):
        actions.append({"key": key, "priority": priority, "source_module": source,
                        "title": title, "reason": reason,
                        "requires_human_verification": True})

    if data.forecast:
        f = data.forecast
        metric("forecast_sales", "Projected observed sales", round(f.projected_sales_units, 2),
               "units", "14B.1", "Caller-supplied forecast summary; not independently recomputed or true demand")
        if f.backtest_wape_pct is not None:
            metric("forecast_wape", "Reported backtest WAPE", round(f.backtest_wape_pct, 2),
                   "%", "14B.1", "Caller-reported backtest error; not audited by this endpoint")
            if f.backtest_wape_pct > 30:
                action("forecast_accuracy", 2, "14B.1", "Review forecast fit",
                       "Reported WAPE exceeds 30%; compare seasonal patterns and stockout censorship")
        if f.reported_stockout_days:
            action("sales_censoring", 2, "14B.1", "Review stockout-censored sales",
                   "Reported stockout days may hide unmet demand")
    if data.inventory:
        inv = data.inventory
        metric("on_hand", "Reported on-hand inventory", inv.reported_on_hand_units,
               "units", "14B.3", "Caller-reported stock figure; not physically verified")
        signals = inv.balance_mismatches + inv.cross_day_gaps + inv.unusual_sales_days
        metric("inventory_signals", "Reported inventory review signals", signals,
               "signals", "14B.3", "Sum of caller-supplied flagged categories; not fraud findings")
        if inv.balance_mismatches or inv.cross_day_gaps:
            action("stock_reconciliation", 1, "14B.3", "Reconcile reported stock movements",
                   "Reported balance or continuity differences require reconciliation with source records")
        if inv.unusual_sales_days:
            action("sales_anomalies", 2, "14B.3", "Investigate unusual sales",
                   "Review promotions, batch orders and data-entry errors before attributing cause")
        if inv.modeled_lead_time_shortfall_units is not None:
            metric("lead_gap", "Modeled lead-time shortfall", round(inv.modeled_lead_time_shortfall_units, 2),
                   "units", "14B.3", "User-supplied lead-time scenario, not a replenishment order")
            if inv.modeled_lead_time_shortfall_units > 0:
                action("lead_time_gap", 1, "14B.3", "Verify potential replenishment gap",
                       "The supplied scenario estimates a positive unit shortfall; check live inventory and lead times")
    if data.cohorts:
        c = data.cohorts
        metric("cohort_profiles", "Anonymous aggregate profiles", c.anonymous_profile_count,
               "profiles", "14B.2", "Count only; no individual identities or assignments")
        metric("basket_rules", "Exploratory basket association rules", c.association_rule_count,
               "rules", "14B.2", "Co-occurrences, not causal cross-sell uplift")
        if c.association_rule_count == 0:
            action("basket_evidence", 3, "14B.2", "Reassess product associations",
                   "No supplied rule passed the upstream exploration filters")
    if data.verification:
        v = data.verification
        metric("pending_evidence", "Unresolved evidence items", v.unresolved_evidence_items,
               "items", "14A/13B", "Caller-supplied verification backlog; not proof of live merchant contact")
        if v.unresolved_evidence_items or v.provisional_candidates:
            action("verification_backlog", 1, "14A/13B", "Prioritize independent verification",
                   "Pending evidence or provisional candidates must not be treated as purchasable stock")
    if days_old > 14:
        action("stale_snapshot", 1, "14B.4", "Refresh stale scenario summaries",
               f"Snapshot reference date is {days_old} days old; current operations may differ")
    if missing:
        action("missing_modules", 3, "14B.4", "Complete command-center coverage",
               "Missing summaries: " + ", ".join(missing))

    actions.sort(key=lambda item: (item["priority"], item["key"]))
    return {
        "mode": "AGGREGATE_BI_COMMAND_CENTER_14B4",
        "data_origin": origin,
        "as_of": data.as_of.isoformat(), "snapshot_age_days": days_old,
        "coverage": {"available_modules": sum(supplied.values()),
                     "total_modules": 4, "supplied": supplied, "missing_modules": missing},
        "metrics": metrics, "review_queue": actions,
        "executive_summary": (f"{sum(supplied.values())}/4 analysis families represented; "
                              f"{len(actions)} follow-up review actions. All values are supplied summaries, "
                              "not verified operational outcomes."),
        "limitations": [
            "All aggregates are caller-supplied summaries, even when their source chunk is named; the API does not recompute or authenticate the upstream calculations.",
            "Synthetic demo inputs are labels supplied by the client and not evidence of production retail activity.",
            "Forecasts are observed-sales proxies; inventory is unverified; associations are descriptive and do not imply sales uplift.",
            "Priority levels are deterministic review heuristics, not calibrated risk, fraud prediction, EVSI, or financial value.",
            "Missing analysis modules mean the command center is incomplete; no module silently becomes verified by aggregation.",
            "No persistence, live BigQuery, Looker, POS or ERP feeds, merchant contact, stock confirmation, purchasing or restocking is performed.",
        ],
        "source_records_persisted": False, "independently_verified": False,
        "cloud_model_used": False, "bigquery_used": False, "purchase_allowed": False,
        "fraud_determined": False, "individual_customer_data_returned": False,
    }
