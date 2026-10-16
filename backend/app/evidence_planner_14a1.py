"""NeedProof 14A.1: transparent, *hypothetical* evidence-aware EVSI planning.

Accepts existing 13B ReplanInput evidence snapshots and 13C compatibility statuses.
Observed signals and likelihoods are caller-entered, uncalibrated assumptions, NOT
independent evidence. Uses the established Bayesian and EVSI implementations.
No I/O, persistence, external models, merchant contact, or purchasing.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.algorithms.adaptive_replanning import ReplanInput, evaluate_replan
from app.algorithms.evsi import Offer, VerificationAction, bayes_update, plan_verifications

CompatibilityStatus = Literal[
    "UNKNOWN", "CONDITIONAL_SPEC_MATCH", "INSUFFICIENT_SPEC_INPUT",
    "INSUFFICIENT_SOURCE_EVIDENCE", "REPORTED_SPEC_MISMATCH",
]
EvidenceKind = Literal["MERCHANT_REPORTED_UNVERIFIED", "USER_SUPPLIED_EXCERPT_UNVERIFIED", "OPERATOR_ASSUMPTION"]


class UncalibratedSignal(BaseModel):
    evidence_kind: EvidenceKind
    observed_positive: bool
    assumed_sensitivity: Decimal = Field(ge=0, le=1)
    assumed_specificity: Decimal = Field(ge=0, le=1)
    source_reference: str = Field(min_length=2, max_length=150)


class VerificationProposal(BaseModel):
    place_id: str = Field(min_length=3, max_length=300)
    indicative_price_minor: int | None = Field(default=None, ge=1, le=100_000_000)
    assumed_prior_feasible: Decimal = Field(ge=0, le=1)
    assumed_response_probability: Decimal = Field(ge=0, le=1)
    verification_cost_minor: int = Field(default=800, ge=0, le=100_000)
    verification_delay_minutes: int = Field(default=3, ge=0, le=120)
    compatibility_status: CompatibilityStatus = "UNKNOWN"
    source_reference_ids: list[str] = Field(default_factory=list, max_length=12)
    signals: list[UncalibratedSignal] = Field(default_factory=list, max_length=5)


class EvidencePlanInput14A1(BaseModel):
    snapshot: ReplanInput
    proposals: list[VerificationProposal] = Field(min_length=1, max_length=12)
    deadline_minutes: int = Field(default=15, ge=0, le=120)
    hypothetical_fulfillment_value_minor: int = Field(default=20_000, ge=0, le=1_000_000)
    hypothetical_delay_cost_minor_per_minute: int = Field(default=60, ge=0, le=100_000)
    assumption_acknowledged: Literal[True]

    @model_validator(mode="after")
    def validate_links(self):
        ids = [p.place_id for p in self.proposals]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate verification proposals")
        available = {m.place_id for m in self.snapshot.merchants}
        if not set(ids) <= available:
            raise ValueError("Every proposal must link to a snapshot merchant Place ID")
        if self.snapshot.customer.budget_minor is None or self.snapshot.customer.budget_minor <= 0:
            raise ValueError("A positive customer budget is required for EVSI ranking")
        return self


def _report_issues(snapshot: ReplanInput, place_id: str) -> tuple[str | None, int | None, str]:
    customer = snapshot.customer
    merchant = next(m for m in snapshot.merchants if m.place_id == place_id)
    report = merchant.evidence
    if report is None or report.submission is None:
        return None, None, "NO_MERCHANT_REPORT"
    submission = report.submission
    if report.status != "REPORTED_UNVERIFIED":
        return "UNSUPPORTED_REPORT_STATUS", None, "MERCHANT_REPORTED_UNVERIFIED"
    if " ".join(report.product_query.casefold().split()) != " ".join(customer.product_query.casefold().split()):
        return "PRODUCT_QUERY_MISMATCH", None, "MERCHANT_REPORTED_UNVERIFIED"
    if submission.stock_quantity < customer.required_quantity:
        return "REPORTED_STOCK_INSUFFICIENT", None, "MERCHANT_REPORTED_UNVERIFIED"
    if submission.currency.upper() != "INR":
        return "UNSUPPORTED_CURRENCY", None, "MERCHANT_REPORTED_UNVERIFIED"
    if customer.delivery_required and submission.delivery_available is False:
        return "REPORTED_DELIVERY_UNAVAILABLE", None, "MERCHANT_REPORTED_UNVERIFIED"
    price = submission.price_minor
    if price is not None:
        price *= customer.required_quantity
    return None, price, "MERCHANT_REPORTED_UNVERIFIED"


def evaluate_evidence_plan(payload: EvidencePlanInput14A1) -> dict:
    """Rank hypothetical next verification actions without promoting reports to verified facts."""
    customer = payload.snapshot.customer
    budget = customer.budget_minor
    assert budget is not None
    by_id = {m.place_id: m for m in payload.snapshot.merchants}
    offers: list[Offer] = []
    actions: list[VerificationAction] = []
    skipped: list[dict] = []
    evidence_traces: list[dict] = []
    for proposal in payload.proposals:
        merchant = by_id[proposal.place_id]
        reason, reported_price, price_provenance = _report_issues(payload.snapshot, proposal.place_id)
        if proposal.compatibility_status == "REPORTED_SPEC_MISMATCH":
            reason = reason or "REPORTED_SPEC_MISMATCH"
        # A merchant-reported price outranks an unrelated client estimate, but remains unverified.
        price = reported_price if reported_price is not None else (
            proposal.indicative_price_minor * customer.required_quantity
            if proposal.indicative_price_minor is not None else None
        )
        if reported_price is None and proposal.indicative_price_minor is not None:
            price_provenance = "CLIENT_ESTIMATE_UNVERIFIED"
        if price is None:
            reason = reason or "PRICE_INFORMATION_MISSING"

        posterior = proposal.assumed_prior_feasible
        signals = []
        for signal in proposal.signals:
            before = posterior
            try:
                posterior = bayes_update(
                    posterior, signal.assumed_sensitivity,
                    signal.assumed_specificity, signal.observed_positive,
                )
            except ValueError as exc:
                raise ValueError(f"Impossible likelihood in {signal.source_reference}") from exc
            signals.append({
                "source_reference": signal.source_reference,
                "evidence_kind": signal.evidence_kind,
                "observation_positive": signal.observed_positive,
                "assumed_prior": float(before),
                "assumed_posterior": float(posterior),
            })
        evidence_traces.append({
            "place_id": proposal.place_id,
            "merchant": merchant.name,
            "price_provenance": price_provenance,
            "quoted_total_minor": price,
            "compatibility_status": proposal.compatibility_status,
            "source_reference_ids": proposal.source_reference_ids,
            "assumed_prior": float(proposal.assumed_prior_feasible),
            "assumed_posterior": float(posterior),
            "signals": signals,
            "blocked_reason": reason,
        })
        if reason:
            skipped.append({
                "action_id": "VERIFY_" + proposal.place_id,
                "merchant": merchant.name,
                "sku": proposal.place_id,
                "prior_feasible": float(posterior),
                "response_probability": float(proposal.assumed_response_probability),
                "net_evsi_inr": "0.00",
                "gross_evsi_inr": "0.00",
                "skip_reason": reason,
            })
            continue
        assert price is not None
        offers.append(Offer(
            sku=proposal.place_id,
            merchant=merchant.name,
            price_minor=price,
            stock_on_hand=0,
            stock_verified=False,
            compatibility_verified=False,
            delivery_verified=False,
        ))
        actions.append(VerificationAction(
            action_id="VERIFY_" + proposal.place_id,
            sku=proposal.place_id,
            prior_feasible=posterior,
            response_probability=proposal.assumed_response_probability,
            cost_minor=proposal.verification_cost_minor,
            delay_minutes=proposal.verification_delay_minutes,
        ))

    ranked = plan_verifications(
        offers, actions,
        budget_minor=budget,
        deadline_minutes=payload.deadline_minutes,
        fulfillment_value_minor=payload.hypothetical_fulfillment_value_minor,
        delay_cost_minor_per_minute=payload.hypothetical_delay_cost_minor_per_minute,
    )
    current = evaluate_replan(payload.snapshot)
    selected = ranked["recommended_action_id"]
    return {
        "mode": "CLIENT_EVIDENCE_HYPOTHETICAL_EVSI_14A1",
        "recommended_action_id": selected,
        "stopping_reason": ranked["stopping_reason"],
        "actions": ranked["actions"] + skipped,
        "evidence_traces": evidence_traces,
        "snapshot_replanning": current,
        "current_verification_baseline": ranked["baseline"],
        "purchase_allowed": False,
        "no_merchant_contact_performed": True,
        "calibration_status": "UNCALIBRATED_USER_SUPPLIED_PRIORS_AND_LIKELIHOODS",
        "assumptions": [
            "Probabilities, detection characteristics and response rates are hypothetical, not measured or independently calibrated.",
            "Multiple signals are conditionally independent ONLY under the hypothetical model.",
            "Existing EVSI model assumes perfect complete verification on response and uses synthetic utility; reported claims do not satisfy that condition.",
            "Merchant evidence and supplied document excerpts are not independent confirmation of stock, product compatibility or fulfillment.",
            "No merchant was contacted or purchase authorized.",
        ],
    }
