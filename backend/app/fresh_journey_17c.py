"""17C: recomputable customer-supplied *what-if* evidence, never actual inventory.

No model call, network, database or merchant contact. All reported stock is a
server-created fictional scenario adjusted by explicit customer controls.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.decision_orchestrator_14a3 import OrchestrationInput14A3, orchestrate_decision_14a3
from app.evidence_passport_17d import build_passport_17d


class FreshJourney17C(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_query: str = Field(min_length=3, max_length=160)
    budget_inr: int = Field(ge=100, le=100_000, strict=True)
    location_note: str = Field(default="", max_length=80)
    reported_price_inr: int = Field(ge=1, le=100_000, strict=True)
    simulated_report: Literal["reported_offer", "stockout", "no_merchants"]
    simulation_acknowledged: Literal[True]
    synthetic_documents: Literal["not_submitted", "matching_fixture", "conflicting_fixtures"] = "not_submitted"

    @model_validator(mode="after")
    def document_fixture_is_applicable(self):
        if self.synthetic_documents != "not_submitted" and ("charger" not in self.product_query.casefold() or len(self.product_query) > 150):
            raise ValueError("Illustrative USB-PD documents apply only to charger requests <=150 characters")
        return self

    @field_validator("product_query")
    @classmethod
    def clean_product(cls, value: str) -> str:
        result = " ".join(value.split())
        if len(result) < 3 or len(result) > 160:
            raise ValueError("Product must contain 3-160 non-whitespace characters")
        return result

    @field_validator("location_note")
    @classmethod
    def clean_location(cls, value: str) -> str:
        return " ".join(value.split())


def _snapshot(p: FreshJourney17C, stock: int, at: str, empty: bool = False) -> dict:
    customer = {
        "product_query": p.product_query,
        "budget_minor": p.budget_inr * 100,
        "required_quantity": 1,
        "delivery_required": False,
    }
    if empty:
        return {"customer": customer, "merchants": []}
    return {
        "customer": customer,
        "merchants": [{
            "place_id": "fixture_17c_a", "name": "FICTIONAL Store A",
            "evidence": {
                "product_query": p.product_query,
                "status": "REPORTED_UNVERIFIED",
                "submission": {
                    "product_name": p.product_query, "stock_quantity": stock,
                    "price_minor": p.reported_price_inr * 100, "currency": "INR",
                    "delivery_available": None, "submitted_at": at,
                },
                "assessment": {
                    "status": "REPORTED_UNVERIFIED", "freshness": "RECENT_REPORT",
                    "eligible_for_commitment": False,
                },
            },
        }],
    }


def _fictional_documents_17d(payload: FreshJourney17C, at: str) -> dict | None:
    """Explicit opt-in synthetic USB-PD texts; never a retrieved authentic source."""
    if payload.synthetic_documents == "not_submitted":
        return None
    sources = [{
        "source_id": "fictional_spec_a", "title": "FICTIONAL specification A",
        "captured_at": at, "excerpt": "USB PD supported. Output 20V/3250mA. Cable 5A rated.", "facts": [],
    }]
    if payload.synthetic_documents == "conflicting_fixtures":
        sources.append({
            "source_id": "fictional_spec_b", "title": "FICTIONAL specification B",
            "captured_at": at, "excerpt": "USB PD not supported. Output 20V/3250mA. Cable 5A rated.", "facts": [],
        })
    return {
        "query": f"{payload.product_query[:120]} USB PD 65W compatibility scenario",
        "review": {"product_label": payload.product_query,
                   "device_model": "FICTIONAL example laptop",
                   "device_supports_usb_pd": True,
                   "required_power_w": 65, "required_voltage_v": 20,
                   "sources": sources},
    }


def evaluate_fresh_journey_17c(payload: FreshJourney17C) -> dict:
    """Run the actual 14A.3 engine on a new, explicit, bounded what-if input."""
    when = datetime.now(timezone.utc).isoformat()
    current = _snapshot(
        payload, 0 if payload.simulated_report == "stockout" else 1,
        when, empty=payload.simulated_report == "no_merchants",
    )
    # Previous snapshot is an *illustrative what-if*, NOT recorded merchant history.
    previous = _snapshot(payload, 1, when) if payload.simulated_report == "stockout" else None
    fictional_documents = _fictional_documents_17d(payload, when)
    workflow = orchestrate_decision_14a3(OrchestrationInput14A3.model_validate({
        "snapshot": current,
        "previous_snapshot": previous,
        "product_research": fictional_documents,
        "client_revision": 1 if previous is not None else 0,
        "simulation_acknowledged": True,
    }))
    if workflow["purchase_allowed"] is not False or workflow["stock_independently_verified"] is not False:
        raise RuntimeError("Unsafe decision engine contract")
    passport = build_passport_17d(payload=payload, workflow=workflow, issued_at=when,
                                  fixture_research=fictional_documents)
    if passport["snapshot_sha256"] != workflow["snapshot_sha256"] or passport["purchase_allowed"] is not False:
        raise RuntimeError("Evidence passport is not bound to safe workflow")
    return {
        "mode": "FRESH_STRUCTURED_WHAT_IF_17C",
        "execution": "LIVE_LOCAL_OR_CLOUD_PYTHON_NO_MODEL",
        "evidence_origin": "SERVER_GENERATED_FICTIONAL_FROM_CUSTOMER_CONTROLS",
        "input_product_query": payload.product_query,
        "input_budget_inr": payload.budget_inr,
        "location_note_unverified": payload.location_note,
        "location_used_for_discovery": False,
        "input_reported_price_inr": payload.reported_price_inr,
        "simulated_report": payload.simulated_report,
        "synthetic_documents": payload.synthetic_documents,
        "evidence_passport": passport,
        "workflow": workflow,
        "gemini_called": False,
        "merchant_contacted": False,
        "database_written": False,
        "stock_independently_verified": False,
        "purchase_allowed": False,
        "limitations": [
            "New customer-entered fields drive a real Python orchestration call.",
            "The store and stock values are fictional what-if inputs, not observed merchant evidence.",
            "The location note is not used for real Places discovery in this chunk.",
            "No Gemini, EVSI or basket calculation was executed. Document retrieval runs only when fictional fixture excerpts are explicitly selected.",
            "Stock-out comparison is simulated, not a historical merchant update.",
            "No stock verification, purchase, merchant contact, external API or storage.",
        ],
    }
