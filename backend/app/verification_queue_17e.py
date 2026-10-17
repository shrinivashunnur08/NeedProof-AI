"""17E next-best-proof queue. Executes the existing 14A.1 model only as an
explicitly *hypothetical*, uncalibrated sidecar. No external contact or writes.

A queue is a recommendation for what a *human* might verify. It is NOT an
order to call a merchant, source validation, or an authorization to purchase.
"""
from __future__ import annotations

from typing import Any

from app.evidence_planner_14a1 import EvidencePlanInput14A1, evaluate_evidence_plan


LABELS = {
    "RECONCILE_CONFLICT": ("Reconcile conflicting specifications", "Opposing USB-PD claims block compatibility.", "Compare an authentic manufacturer specification or obtain expert review."),
    "DISCOVER_MERCHANTS": ("Find candidate merchants", "There is no supplied merchant to assess.", "Look for genuine sellers; this application performs no discovery here."),
    "REFRESH_ALTERNATIVES": ("Find an alternative offer", "The supplied stock-out excludes the fictional offer.", "Request new offers without assuming availability."),
    "CHECK_COMPATIBILITY": ("Verify device and charger compatibility", "Unverified or conflicting product information could make the item unusable.", "Check the precise device model against authentic USB-PD and voltage documentation."),
    "AUTHENTICATE_MERCHANT": ("Verify merchant identity", "The fictional merchant label is not a real authenticated seller.", "Confirm seller identity using an independent trusted source."),
    "VERIFY_STOCK": ("Verify actual stock", "A fictional stock report is not independently observed inventory.", "Ask an authenticated merchant to confirm the exact SKU and availability."),
    "CONFIRM_FULFILLMENT": ("Confirm pickup or delivery", "No fulfillment commitment has been established.", "Confirm pickup window or delivery coverage with the merchant."),
}


def _sidecar_evsi(snapshot: dict, passport: dict, workflow: dict) -> dict:
    """Use existing 14A.1 with *disclosed fixed demonstration assumptions*."""
    if workflow["workflow_state"] == "RESEARCH_CONFLICT":
        return {"status": "BLOCKED_DOCUMENT_CONFLICT", "recommended_action_id": None,
                "actions": [], "assumptions_calibrated": False}
    if not snapshot["merchants"]:
        return {"status": "NOT_APPLICABLE_NO_MERCHANT", "recommended_action_id": None,
                "actions": [], "assumptions_calibrated": False}
    args = {
        "snapshot": snapshot,
        "proposals": [{
            "place_id": "fixture_17c_a",
            "assumed_prior_feasible": "0.65", "assumed_response_probability": "0.80",
            "verification_cost_minor": 500, "verification_delay_minutes": 2,
            "compatibility_status": "UNKNOWN",
            "source_reference_ids": [s["source_id"] for s in passport["sources"]][:12],
        }],
        "assumption_acknowledged": True,
    }
    plan = evaluate_evidence_plan(EvidencePlanInput14A1.model_validate(args))
    return {
        "status": "EXECUTED_HYPOTHETICAL_UNCALIBRATED",
        "recommended_action_id": plan["recommended_action_id"],
        "actions": [{"action_id": a["action_id"], "net_evsi_inr": a["net_evsi_inr"],
                     "skip_reason": a.get("skip_reason")} for a in plan["actions"]],
        "assumptions_calibrated": False,
        "assumptions": {
            "prior_feasible": "0.65 (invented scenario assumption)",
            "response_probability": "0.80 (invented scenario assumption)",
            "verification_cost_inr": "5.00 (invented scenario assumption)",
            "verification_delay_minutes": "2 (invented scenario assumption)",
        },
        "no_merchant_contact_performed": True,
        "purchase_allowed": False,
    }


def build_verification_queue_17e(*, snapshot: dict, passport: dict, workflow: dict,
                                  fictional_update: dict | None = None) -> dict:
    if passport["snapshot_sha256"] != workflow["snapshot_sha256"]:
        raise RuntimeError("17E queue and passport refer to different evidence snapshots")
    if passport["real_world_evidence_present"] or workflow["purchase_allowed"]:
        raise RuntimeError("17E refuses verified or purchased workflow claims")
    state = workflow["workflow_state"]
    kinds = [a["kind"] for a in passport["unresolved_verification"]]
    if state == "RESEARCH_CONFLICT":
        order = ["RECONCILE_CONFLICT", "CHECK_COMPATIBILITY", "AUTHENTICATE_MERCHANT", "VERIFY_STOCK", "CONFIRM_FULFILLMENT"]
    elif state == "DISCOVERY_NEEDED":
        order = ["DISCOVER_MERCHANTS", "CHECK_COMPATIBILITY"]
    elif state == "MORE_EVIDENCE_NEEDED":
        order = ["REFRESH_ALTERNATIVES", "CHECK_COMPATIBILITY", "AUTHENTICATE_MERCHANT", "VERIFY_STOCK", "CONFIRM_FULFILLMENT"]
    else:
        order = ["CHECK_COMPATIBILITY", "AUTHENTICATE_MERCHANT", "VERIFY_STOCK", "CONFIRM_FULFILLMENT"]
    queue = []
    for kind in order:
        if kind not in kinds:
            continue
        label, reason, method = LABELS[kind]
        queue.append({
            "rank": len(queue) + 1, "action_id": kind, "label": label,
            "reason": reason, "suggested_human_check": method,
            "status": "NOT_EXECUTED", "requires_independent_evidence": True,
            "supporting_source_ids": [], "score_origin": "DETERMINISTIC_SAFETY_POLICY_NOT_CALIBRATED_EVSI",
        })
    hypothetical = _sidecar_evsi(snapshot, passport, workflow)
    if not queue:
        raise RuntimeError("17E expected at least one unresolved verification action")
    return {
        "mode": "NEXT_BEST_PROOF_17E",
        "data_origin": "FICTIONAL_SCENARIO_AND_UNCALIBRATED_ASSUMPTIONS",
        "snapshot_sha256": workflow["snapshot_sha256"],
        "workflow_state": state,
        "recommended_action_id": queue[0]["action_id"],
        "selection_rule": "SAFETY_FIRST_POLICY_CONFLICT_DISCOVERY_STOCKOUT_THEN_REQUIREMENT_CHECKS",
        "actions": queue,
        "hypothetical_evsi": hypothetical,
        "hypothetical_merchant_update": fictional_update,
        "real_merchant_evidence_submitted": False,
        "merchant_verified": False, "stock_verified": False,
        "external_requests_performed": False, "database_written": False,
        "purchase_allowed": False,
        "business_kpis": {"actual_contact_count": 0,
                          "real_customer_time_saved_measured": False,
                          "real_merchant_response_rate_measured": False,
                          "real_conversion_improvement_measured": False},
        "interpretation": (
            "Rank is a deterministic safety-oriented next-proof policy, not a measured likelihood. "
            "The separate 14A.1 EVSI calculation uses fixed illustrative assumptions; "
            "it does not validate a merchant or supersede contradiction/stock-out policy. "
            "Neither recommended actions nor fictional updates contact any real store."
        ),
    }
