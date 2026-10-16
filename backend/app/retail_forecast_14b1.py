"""14B.1 — transparent sales forecasting on user-provided daily histories.

Offline deterministic statistics, not Gemini predictions or verified future demand.
No persistence, model downloads, external APIs or cloud provisioning.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import ceil
from statistics import mean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DailySales14B1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    units_sold: int = Field(ge=0, le=1_000_000)
    reported_stockout: bool = False


class ForecastInput14B1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_label: str = Field(min_length=2, max_length=100)
    history: list[DailySales14B1] = Field(min_length=42, max_length=180)
    horizon_days: int = Field(default=7, ge=1, le=14)
    on_hand_units: int | None = Field(default=None, ge=0, le=1_000_000)
    replenishment_lead_days: int | None = Field(default=None, ge=1, le=14)
    synthetic_demo: bool = False

    @model_validator(mode="after")
    def consecutive_days(self):
        days = [r.day for r in self.history]
        if any(days[i] + timedelta(days=1) != days[i + 1] for i in range(len(days)-1)):
            raise ValueError("History must contain unique consecutive ascending daily dates; use zero for observed no-sale days")
        if days[-1] > date.today():
            raise ValueError("Future-dated observed sales are not accepted")
        if (self.on_hand_units is None) != (self.replenishment_lead_days is None):
            raise ValueError("Provide on_hand_units and replenishment_lead_days together")
        if self.replenishment_lead_days is not None and self.replenishment_lead_days > self.horizon_days:
            raise ValueError("Replenishment lead days cannot exceed forecast horizon")
        return self


MODEL_IDS = ("seasonal_naive_7", "moving_average_7", "weekday_mean_4w", "damped_trend")


def _predict(method: str, values: list[int], horizon: int) -> list[float]:
    """Make all H forecasts using ONLY the supplied pre-origin history."""
    if len(values) < 21:
        raise ValueError("Forecast training requires at least 21 prior daily observations")
    trailing = [float(x) for x in values[-7:]]
    if method == "seasonal_naive_7":
        return [trailing[i % 7] for i in range(horizon)]
    if method == "moving_average_7":
        return [mean(trailing)] * horizon
    if method == "weekday_mean_4w":
        # Current final week corresponds to target weekdays 7 days ahead.
        return [mean(float(values[-7 + i % 7 - 7*j])
                     for j in range(min(4, (len(values) - 7 + (i % 7)) // 7 + 1)))
                for i in range(horizon)]
    if method == "damped_trend":
        recent = mean(trailing)
        previous = mean(values[-14:-7])
        # Difference between adjacent 7-day averages is a WEEKLY change;
        # damp it for horizon rather than extrapolating unchecked.
        weekly_change = recent - previous
        return [max(0.0, recent + 0.5 * weekly_change * min(i+1, 7) / 7) for i in range(horizon)]
    raise ValueError("Unknown forecasting baseline")


def _round2(value: float) -> float:
    return round(max(0.0, float(value)), 2)


def _absolute_quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(abs(v) for v in values)
    return ordered[max(0, min(len(ordered)-1, ceil(q*len(ordered))-1))]


def evaluate_retail_forecast_14b1(payload: ForecastInput14B1) -> dict:
    values = [r.units_sold for r in payload.history]
    horizon = payload.horizon_days
    # Exactly the most recent 14 origins. Each origin predicts ahead without
    # observing future holdout sales; cross-origin residuals are correlated.
    start = len(values) - 14
    reports: dict[str, dict] = {}
    for method in MODEL_IDS:
        errors: list[float] = []
        actuals: list[int] = []
        for origin in range(start, len(values)):
            future = min(horizon, len(values) - origin)
            predicted = _predict(method, values[:origin], future)
            for j in range(future):
                actual = values[origin+j]
                errors.append(predicted[j] - actual)
                actuals.append(actual)
        mae = sum(abs(e) for e in errors) / len(errors)
        denominator = sum(actuals)
        reports[method] = {
            "method": method,
            "mae_units": round(mae, 3),
            "wape_pct": round(100*sum(abs(e) for e in errors)/denominator, 2) if denominator else None,
            "mean_signed_error_units": round(mean(errors), 3),
            "evaluated_forecast_points": len(errors),
            "rolling_origins": 14,
            "_residuals": errors,
            "_selection_mae": mae,
        }
    winner = min(MODEL_IDS, key=lambda method: (reports[method]["_selection_mae"], MODEL_IDS.index(method)))
    best = _predict(winner, values, horizon)
    interval_halfwidth = _absolute_quantile(reports[winner]["_residuals"], 0.8)
    interval_available = any(value > 0 for value in values)
    predictions = []
    for idx, estimate in enumerate(best):
        predictions.append({
            "day": (payload.history[-1].day + timedelta(days=idx+1)).isoformat(),
            "expected_units": _round2(estimate),
            "lower_heuristic_80": _round2(estimate - interval_halfwidth) if interval_available else None,
            "upper_heuristic_80": _round2(estimate + interval_halfwidth) if interval_available else None,
        })
    warnings = [
        "This forecasts OBSERVED SALES, not latent demand; stockouts and lost sales can censor observations.",
        "Reported stockout flags are user-supplied, not independently verified or statistically corrected.",
        "The '80' bands are empirical residual heuristics from overlapping backtests, NOT calibrated 80% prediction intervals.",
        "Backtests share overlapping dates and cannot guarantee future accuracy; models are descriptive baselines, not learned seasonality guarantees.",
    ]
    flagged = sum(bool(r.reported_stockout) for r in payload.history)
    if flagged:
        warnings.append(f"{flagged} user-reported stockout day(s) may bias forecasts downward; no imputation attempted.")
    if not interval_available:
        warnings.append("All observed sales are zero; uncertainty band omitted rather than representing zero error as certainty.")
    elif interval_halfwidth == 0:
        warnings.append("Backtest residuals are all zero; a zero-width heuristic is NOT evidence of zero future uncertainty.")
    if len(values) < 56:
        warnings.append("Short series: weekly patterns and ranking are especially unstable.")
    for report in reports.values():
        report.pop("_residuals")
        report.pop("_selection_mae")
    exposure = None
    if payload.on_hand_units is not None and payload.replenishment_lead_days is not None:
        projected = sum(best[:payload.replenishment_lead_days])
        exposure = {
            "reported_on_hand_units": payload.on_hand_units,
            "lead_days": payload.replenishment_lead_days,
            "projected_sales_units_before_replenishment": _round2(projected),
            "projected_shortfall_units": _round2(max(0, projected - payload.on_hand_units)),
            "interpretation": "Illustrative sales-versus-on-hand comparison, not verified stock or a probabilistic stockout risk.",
        }
    return {
        "mode": "LOCAL_BASELINES_14B1",
        "product_label": payload.product_label,
        "data_origin": "CLIENT_LABELED_SYNTHETIC_DEMO" if payload.synthetic_demo else "USER_SUPPLIED_UNVERIFIED",
        "target": "OBSERVED_UNIT_SALES_AS_DEMAND_PROXY",
        "training_observations": len(values),
        "holdout_origin_count": 14,
        "holdout_method": "ROLLING_ORIGIN_DIRECT_MULTI_STEP_NO_FUTURE_LEAKAGE",
        "selected_model": winner,
        "model_comparison": [reports[method] for method in MODEL_IDS],
        "predictions": predictions,
        "heuristic_band_halfwidth_units": _round2(interval_halfwidth) if interval_available else None,
        "reported_stockout_days": flagged,
        "inventory_exposure_scenario": exposure,
        "limitations": warnings,
        "observations_persisted": False,
        "cloud_model_used": False,
        "forecast_independently_verified": False,
        "purchase_allowed": False,
    }
