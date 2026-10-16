"""NeedProof 14A.3: deterministic, evidence-separated decision workflow.

Pure, bounded composition of existing 13C.2, 13B, 14A.1, and 14A.2
engines. Client snapshots are NOT authenticated merchant records; a caller's
previous snapshot is NOT immutable history. No persistence, model calls,
merchant contact, payments, purchasing, or inventory reservations.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.algorithms.adaptive_replanning import ReplanInput, evaluate_replan, normalize
from app.basket_optimizer_14a2 import BasketPlan14A2, evaluate_basket_14a2
from app.evidence_planner_14a1 import EvidencePlanInput14A1, evaluate_evidence_plan
from app.product_retrieval_13c2 import RetrievalInput, retrieve_and_review


class OrchestrationInput14A3(BaseModel):
    snapshot: ReplanInput
    previous_snapshot: ReplanInput | None = None
    product_research: RetrievalInput | None = None
    verification_plan: EvidencePlanInput14A1 | None = None
    basket_scenario: BasketPlan14A2 | None = None
    client_revision: int = Field(default=0, ge=0, le=100_000)
    simulation_acknowledged: Literal[True]

    @model_validator(mode="after")
    def check_consistency(self):
        product = normalize(self.snapshot.customer.product_query)
        if self.product_research and normalize(self.product_research.review.product_label) != product:
            raise ValueError("Product research label must match the snapshot product")
        if self.verification_plan and self.verification_plan.snapshot != self.snapshot:
            raise ValueError("EVSI plan must use the exact same merchant/customer snapshot")
        if self.previous_snapshot and normalize(self.previous_snapshot.customer.product_query) != product:
            raise ValueError("Previous snapshot cannot belong to another product request")
        # Basket scenarios are separate, explicitly hypothetical fixtures. They
        # cannot be promoted to actual, authorized purchase candidates.
        return self


def _fingerprint(payload: ReplanInput) -> str:
    return sha256(payload.model_dump_json(exclude_none=False).encode("utf-8")).hexdigest()


def _changes(previous: ReplanInput | None, current: ReplanInput) -> dict:
    if previous is None:
        return {"comparison": "NO_CLIENT_PREVIOUS_SNAPSHOT", "changed": None, "changes": []}
    before = {m.place_id: m for m in previous.merchants}
    after = {m.place_id: m for m in current.merchants}
    notes = []
    for mid in sorted(set(before) | set(after)):
        if mid not in before:
            notes.append({"place_id": mid, "event": "MERCHANT_ADDED"})
        elif mid not in after:
            notes.append({"place_id": mid, "event": "MERCHANT_REMOVED"})
        elif before[mid].evidence != after[mid].evidence:
            notes.append({"place_id": mid, "event": "CLIENT_EVIDENCE_CHANGED"})
    if previous.customer != current.customer:
        notes.insert(0, {"place_id": None, "event": "CUSTOMER_REQUIREMENTS_CHANGED"})
    return {
        "comparison": "CLIENT_SUPPLIED_WHAT_IF_SNAPSHOTS",
        "changed": bool(notes),
        "changes": notes,
    }


def orchestrate_decision_14a3(payload: OrchestrationInput14A3) -> dict:
    """Compose real evidence *snapshots* and separate hypothetical scenarios."""
    # Engine calls are pure. Never trigger Firestore reads or external APIs.
    merchant = evaluate_replan(payload.snapshot)
    research = retrieve_and_review(payload.product_research) if payload.product_research else None
    verification = evaluate_evidence_plan(payload.verification_plan) if payload.verification_plan else None
    basket = evaluate_basket_14a2(payload.basket_scenario) if payload.basket_scenario else None
    comparison = _changes(payload.previous_snapshot, payload.snapshot)

    research_status = research["review"]["status"] if research else "NOT_SUBMITTED"
    issues = (research["review"]["evidence_gaps"] if research else [])
    conflict = any(gap["reason"] == "CONTRADICTORY_SOURCE_FACTS" for gap in issues)
    mismatch = research_status == "REPORTED_SPEC_MISMATCH"
    if conflict:
        state, action, rationale = (
            "RESEARCH_CONFLICT", "RECONCILE_CONFLICTING_DOCUMENT_EXCERPTS",
            "Source excerpts disagree; do not advance a candidate based on contradictory specifications.",
        )
    elif mismatch:
        state, action, rationale = (
            "SPECIFICATION_MISMATCH", "RESEARCH_COMPATIBLE_ALTERNATIVES",
            "Supplied specification excerpts indicate a mismatch; the source authenticity is still unverified.",
        )
    elif not payload.snapshot.merchants:
        state, action, rationale = (
            "DISCOVERY_NEEDED", "DISCOVER_MERCHANTS",
            "No candidate merchants were provided in the current snapshot.",
        )
    elif merchant["selected"] is not None:
        state, action, rationale = (
            "PROVISIONAL_VERIFICATION_NEEDED", "VERIFY_IDENTITY_COMPATIBILITY_AND_DELIVERY",
            "Merchant report is provisional; identity, compatibility and fulfillment remain unverified.",
        )
    else:
        state, action, rationale = (
            "MORE_EVIDENCE_NEEDED", merchant["recommended_next_action"],
            "No merchant can be treated as a confirmed fulfillment option from the supplied evidence.",
        )

    # EVSI selects only an assumed economic verification action. Even if it
    # ranks highly, a document mismatch/conflict always blocks promotion.
    proposed_action = verification["recommended_action_id"] if verification else None
    if proposed_action and not (conflict or mismatch) and payload.snapshot.merchants:
        action = "REVIEW_HYPOTHETICAL_" + proposed_action
        rationale += " EVSI provides a hypothetical ranking, not a real merchant confirmation."

    trace = [
        {"stage": "MERCHANT_REPLAN_13B", "status": "EVALUATED", "state": merchant["decision_status"],
         "source": "CLIENT_SUPPLIED_MERCHANT_SNAPSHOT"},
        {"stage": "DOCUMENT_RETRIEVAL_13C2", "status": "EVALUATED" if research else "NOT_PROVIDED",
         "state": research_status, "source": "USER_SUPPLIED_EXCERPTS_UNVERIFIED"},
        {"stage": "BAYES_EVSI_14A1", "status": "EVALUATED" if verification else "NOT_PROVIDED",
         "state": "HYPOTHETICAL_UNCALIBRATED" if verification else "NOT_RUN",
         "source": "CLIENT_SUPPLIED_MODEL_ASSUMPTIONS"},
        {"stage": "BASKET_OPTIMIZATION_14A2", "status": "EVALUATED" if basket else "NOT_PROVIDED",
         "state": basket["scenario_status"] if basket else "NOT_RUN",
         "source": "SYNTHETIC_SCENARIO_ONLY"},
        {"stage": "POLICY_BOUNDARY", "status": "ENFORCED", "state": "NO_PURCHASE_AUTHORIZATION",
         "source": "SERVER_POLICY"},
    ]
    return {
        "mode": "EVIDENCE_SEPARATED_ORCHESTRATION_14A3",
        "client_revision": payload.client_revision,
        "snapshot_sha256": _fingerprint(payload.snapshot),
        "change_detection": comparison,
        "workflow_state": state,
        "recommended_next_action": action,
        "reason": rationale,
        "workflow_trace": trace,
        "merchant_replanning": merchant,
        "product_research": research,
        "hypothetical_verification_plan": verification,
        "synthetic_basket_scenario": basket,
        "purchase_allowed": False,
        "merchant_contact_performed": False,
        "stock_independently_verified": False,
        "workflow_persisted": False,
        "gemini_used": False,
        "limitations": [
            "This is a deterministic workflow, not autonomous external tool-using agents.",
            "The snapshots and comparison history are client-supplied; no backend origin or tamper verification is performed.",
            "Merchant reports and document excerpts are not independent proof of inventory or compatibility.",
            "Bayesian likelihoods, response probabilities, and utility are hypothetical and not calibrated.",
            "Basket optima refer only to separate synthetic fixtures, not confirmed purchasable offers.",
            "No real merchant contacted, no stock reserved, no checkout or payment performed.",
        ],
    }
