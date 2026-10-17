"""Chunk 16A: one coherent, *strictly synthetic* evidence-to-decision demonstration.

Composes existing 13C/14A and aggregate 14B logic without network, persistence,
real merchant IDs, real inventory, billing, reservations, or any purchasing actions.
This is a reproducible story in terms of outcomes, not independent validation.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.bi_command_center_14b4 import BIInput14B4, evaluate_bi_command_center_14b4
from app.decision_orchestrator_14a3 import OrchestrationInput14A3, orchestrate_decision_14a3


Scenario16A = Literal["reported_offer", "stockout", "document_conflict", "no_merchants"]
PRODUCT = "65W USB-C PD charger"


class GuidedJourneyInput16A(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Scenario16A
    include_illustrative_business_context: bool = Field(default=True, strict=True)
    simulation_acknowledged: Literal[True]


def _snapshot(*, stock: int, at: str, merchants: bool = True) -> dict:
    return {
        "customer": {
            "product_query": PRODUCT, "budget_minor": 100_000,
            "required_quantity": 1, "delivery_required": False,
        },
        "merchants": [
            {
                "place_id": "fixture_store_a", "name": "FICTIONAL Store A",
                "evidence": {
                    "product_query": PRODUCT, "status": "REPORTED_UNVERIFIED",
                    "submission": {
                        "product_name": PRODUCT, "stock_quantity": stock,
                        "price_minor": 72_000, "currency": "INR",
                        "delivery_available": True, "submitted_at": at,
                    },
                    "assessment": {
                        "status": "REPORTED_UNVERIFIED",
                        "freshness": "RECENT_REPORT",
                        "eligible_for_commitment": False,
                    },
                },
            },
            {"place_id": "fixture_store_b", "name": "FICTIONAL Store B"},
        ] if merchants else [],
    }


def _research(*, at: str, conflict: bool) -> dict:
    excerpts = [{
        "source_id": "fictional_excerpt_a", "title": "Illustrative document excerpt A",
        "captured_at": at,
        "excerpt": "USB PD supported. Output 20V/3250mA. Cable 5A rated.", "facts": [],
    }]
    if conflict:
        excerpts.append({
            "source_id": "fictional_excerpt_b", "title": "Illustrative document excerpt B",
            "captured_at": at,
            "excerpt": "USB PD not supported. Output 20V/3250mA. Cable 5A rated.", "facts": [],
        })
    return {
        "query": "65W charger USB PD compatibility evidence",
        "review": {
            "product_label": PRODUCT, "device_model": "FICTIONAL laptop",
            "device_supports_usb_pd": True, "required_power_w": 65,
            "required_voltage_v": 20, "sources": excerpts,
        },
    }


def _evsi(snapshot: dict) -> dict:
    return {
        "snapshot": snapshot, "proposals": [
            {
                "place_id": place_id,
                "assumed_prior_feasible": "0.65",
                "assumed_response_probability": "0.8",
                "verification_cost_minor": 500,
                "verification_delay_minutes": 2,
                "indicative_price_minor": price,
            }
            for place_id, price in (("fixture_store_a", 72_000), ("fixture_store_b", 82_000))
        ],
        "assumption_acknowledged": True,
    }


def _basket() -> dict:
    return {
        "items": [{"item_id": "charger", "name": "Synthetic charger", "quantity": 1}],
        "merchants": [{
            "merchant_id": "simulation_merchant", "name": "SIMULATED fixture merchant",
            "fulfillment_fee_minor": 1000,
        }],
        "offers": [{
            "sku": "simulation_verified_fixture", "item_id": "charger",
            "merchant_id": "simulation_merchant", "product_name": "SIMULATED charger",
            "unit_price_minor": 60_000, "stock_on_hand": 2,
            "delivery_eta_minutes": 10, "merchant_verified": True,
            "stock_verified": True, "compatibility_verified": True,
            "delivery_verified": True, "evidence_source": "SIMULATION_VERIFIED",
        }],
        "budget_minor": 100_000, "deadline_minutes": 60,
        "max_merchants": 1, "hypothetical_scenario_acknowledged": True,
    }


def _business_context() -> dict:
    # 14B inputs are entirely separate synthetic illustrative aggregate figures,
    # not calculations from the demonstrated customer journey.
    data = {
        "as_of": date.today().isoformat(), "synthetic_demo": True,
        "forecast": {
            "sku_code": "DEMO-CHARGER", "projected_sales_units": 53.4,
            "horizon_days": 7, "backtest_wape_pct": 17.5,
            "reported_stockout_days": 1,
        },
        "inventory": {
            "sku_code": "DEMO-CHARGER", "reported_on_hand_units": 25,
            "balance_mismatches": 1, "cross_day_gaps": 0,
            "unusual_sales_days": 2, "modeled_lead_time_shortfall_units": 14.6,
        },
        "cohorts": {
            "anonymous_profile_count": 48, "aggregate_cohort_count": 2,
            "minimum_cohort_size": 9, "association_rule_count": 3,
        },
        "verification": {
            "candidates_considered": 2, "unresolved_evidence_items": 2,
            "provisional_candidates": 1,
        },
    }
    return evaluate_bi_command_center_14b4(BIInput14B4.model_validate(data))


STORIES = {
    "reported_offer": "A fictional store claims one charger is available. The model may shortlist it provisionally, but cannot approve a purchase.",
    "stockout": "A fictional merchant report changes from one unit to zero. The previously provisional candidate is excluded.",
    "document_conflict": "Two fictional product excerpts disagree on USB PD support. Research must be reconciled before the offer can progress.",
    "no_merchants": "No merchant reports are supplied. The next step is discovery, not invented stock availability.",
}


def evaluate_guided_journey_16a(payload: GuidedJourneyInput16A) -> dict:
    """Generate an integrated bounded storyboard from server-owned synthetic fixtures."""
    now = datetime.now(timezone.utc).isoformat()
    stock = 0 if payload.scenario == "stockout" else 1
    snapshot = _snapshot(stock=stock, at=now, merchants=payload.scenario != "no_merchants")
    previous = _snapshot(stock=1, at=now) if payload.scenario == "stockout" else None
    research = _research(at=now, conflict=payload.scenario == "document_conflict")
    workflow = orchestrate_decision_14a3(OrchestrationInput14A3.model_validate({
        "snapshot": snapshot,
        "previous_snapshot": previous,
        "product_research": research,
        "verification_plan": _evsi(snapshot) if snapshot["merchants"] else None,
        "basket_scenario": _basket(),
        "client_revision": 1 if previous is not None else 0,
        "simulation_acknowledged": True,
    }))
    business = _business_context() if payload.include_illustrative_business_context else None

    if workflow["purchase_allowed"] is not False or workflow["stock_independently_verified"] is not False:
        raise RuntimeError("Unsafe orchestration contract: synthetic data cannot authorize purchase")
    if workflow["synthetic_basket_scenario"] is None or workflow["synthetic_basket_scenario"]["purchase_allowed"] is not False:
        raise RuntimeError("Unsafe basket contract")
    if business and business["purchase_allowed"] is not False:
        raise RuntimeError("Unsafe BI contract")

    return {
        "mode": "GUIDED_EVIDENCE_JOURNEY_16A",
        "scenario": payload.scenario,
        "title": STORIES[payload.scenario],
        "fixture_origin": "SERVER_OWNED_SYNTHETIC_NOT_REAL_MERCHANTS",
        "product": PRODUCT,
        "workflow": workflow,
        "separate_illustrative_business_context": business,
        "business_context_is_derived_from_customer_journey": False,
        "journey_is_historical_verified_record": False,
        "real_merchant_contact": False,
        "stock_independently_verified": False,
        "purchase_allowed": False,
        "cloud_model_used": False,
        "database_used": False,
        "source_records_persisted": False,
        "limitations": [
            "All store names, stock, prices and document excerpts are deliberately fictional fixtures.",
            "The orchestration calculations are real code on fictitious, unverified inputs.",
            "Optional retail BI figures are illustrative aggregates unrelated to this customer journey.",
            "EVSI results are hypothetical and uncalibrated; no observed purchase or savings.",
            "This endpoint does not contact merchants, Gemini, Places, Firestore, BigQuery or payment systems.",
            "No inventory is independently verified, no stock is reserved and no purchase can be authorized.",
        ],
    }
