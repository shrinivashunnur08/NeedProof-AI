"""17D Evidence Passport for bounded, **fictional** 17C what-if decisions.

Read-only. Describes *supplied/fixture* provenance, never asserts verified stock,
merchant identity, purchase eligibility, calibrated confidence, or authenticated
history. No external requests, database writes, model calls, or crawler.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def build_passport_17d(*, payload: Any, workflow: dict, issued_at: str, fixture_research: dict | None) -> dict:
    """Bind traceable claims to actual local 13B/13C.2 workflow results.

    Claim identifiers and hashes identify fixture *content*, not authentic origin.
    The issued_at is when the scenario was computed, NOT when a real merchant
    or product author verified anything.
    """
    state = workflow["workflow_state"]
    fingerprint = workflow["snapshot_sha256"]
    sources: list[dict] = []
    claims: list[dict] = []
    conflicts: list[dict] = []

    def add_claim(kind: str, value: str, *, source_id: str | None, status: str, note: str,
                  citation_id: str | None = None) -> None:
        claims.append({
            "claim_id": "claim_" + _digest(f"{kind}\0{value}\0{source_id}")[:16],
            "kind": kind, "display_value": value,
            "source_id": source_id, "citation_id": citation_id,
            "verification_status": status, "explanation": note,
            "purchase_eligible": False,
        })

    store_present = payload.simulated_report != "no_merchants"
    if store_present:
        sid = "fictional_merchant_17c_a"
        price_label = f"INR {payload.reported_price_inr}"
        stock_label = "0 units (fictional what-if)" if payload.simulated_report == "stockout" else "1 unit (fictional what-if)"
        material = f"fictional_store_a|{payload.product_query}|{payload.reported_price_inr}|{stock_label}"
        sources.append({
            "source_id": sid, "source_type": "SERVER_GENERATED_FICTIONAL_MERCHANT_REPORT",
            "display_title": "FICTIONAL Store A — illustrative report",
            "content_sha256": _digest(material), "captured_at": issued_at,
            "freshness_label": "GENERATED_NOW_NOT_OBSERVED",
            "origin_authenticated": False, "independently_verified": False,
            "external_url": None,
        })
        add_claim("STOCK_QUANTITY", stock_label, source_id=sid, status="REPORTED_UNVERIFIED",
                  note="Current hypothetical stock, not a historical or real merchant observation.")
        add_claim("REPORTED_PRICE", price_label, source_id=sid, status="REPORTED_UNVERIFIED",
                  note="Scenario price entered by customer; no real merchant offer is confirmed.")
    else:
        add_claim("STOCK_QUANTITY", "Unknown — no store provided", source_id=None, status="MISSING",
                  note="No merchant evidence exists. Do not infer a store or available inventory.")
        add_claim("REPORTED_PRICE", "Unknown — no offer", source_id=None, status="MISSING",
                  note="A user-entered comparison price is not a merchant quote.")

    add_claim("MERCHANT_IDENTITY", "Not verified", source_id=None, status="MISSING",
              note="Fictional store details are never authenticated merchant identities.")
    add_claim("FULFILLMENT", "Not verified", source_id=None, status="MISSING",
              note="Neither delivery nor collection is checked in this scenario.")

    if fixture_research is None:
        add_claim("USB_PD_COMPATIBILITY", "Unknown — no excerpts supplied", source_id=None, status="MISSING",
                  note="Document retrieval was not run; no compatibility claim is supported.")
    else:
        research = workflow.get("product_research")
        if not research or research.get("sources_verified") is not False:
            raise RuntimeError("Unsafe document provenance: fixture research contract missing")
        for s in fixture_research["review"]["sources"]:
            sources.append({
                "source_id": s["source_id"], "source_type": "SERVER_GENERATED_FICTIONAL_SPEC_EXCERPT",
                "display_title": s["title"], "content_sha256": _digest(s["excerpt"]),
                "captured_at": issued_at, "freshness_label": "GENERATED_NOW_NOT_OBSERVED",
                "origin_authenticated": False, "independently_verified": False, "external_url": None,
            })
        # The 13C.2 engine provides actual text spans, source IDs and hashes.
        for item in research["passages"]:
            if item["source_id"] not in {s["source_id"] for s in fixture_research["review"]["sources"]}:
                raise RuntimeError("Unmatched citation source")
        refs = research["review"]["cited_facts"]
        contradictory = any(g.get("reason") == "CONTRADICTORY_SOURCE_FACTS" for g in research["review"]["evidence_gaps"])
        if contradictory:
            conflict_refs = [r for r in refs if r["kind"] == "USB_PD_SUPPORT"]
            conflicts.append({
                "conflict_id": "fictional_usb_pd_disagreement",
                "topic": "USB_PD_SUPPORT",
                "status": "UNRESOLVED_FICTIONAL_DOCUMENT_CONFLICT",
                "source_ids": sorted({r["source_id"] for r in conflict_refs}),
                "citations": [{"source_id": r["source_id"], "quote": r["quote"]} for r in conflict_refs],
                "action": "Reconcile opposing primary product specifications before any recommendation.",
            })
        for r in refs:
            # A quote is a *locator* within a fictional document, not proof of truth.
            source = next(s for s in fixture_research["review"]["sources"] if s["source_id"] == r["source_id"])
            passage = next((p for p in research["passages"] if p["source_id"] == r["source_id"]
                            and r["quote"].casefold() in p["quote"].casefold()), None)
            cite = passage["citation_id"] if passage else f"{r['source_id']}:excerpt"
            add_claim(r["kind"], r["quote"], source_id=r["source_id"], citation_id=cite,
                      status="CONFLICTED" if contradictory and r["kind"] == "USB_PD_SUPPORT" else "REPORTED_UNVERIFIED",
                      note=f"Exact quote from fictional fixture {source['source_id']}; not fetched/authenticated.")
        if not refs:
            add_claim("USB_PD_COMPATIBILITY", "Not established", source_id=None, status="MISSING",
                      note="The supplied fictional text does not establish a compatibility specification.")
        elif contradictory:
            add_claim("USB_PD_COMPATIBILITY", "Unresolved disagreement", source_id=None, status="CONFLICTED",
                      note="Document contradictions block compatibility assessment.")
        else:
            add_claim("USB_PD_COMPATIBILITY", "Conditional fixture-only assessment", source_id=None,
                      status="REPORTED_UNVERIFIED", note="Consistent fictional text is not a verified product specification.")

    gaps = [
        {"kind": "AUTHENTICATE_MERCHANT", "label": "Authenticate a real merchant and its offer"},
        {"kind": "VERIFY_STOCK", "label": "Independently confirm stock and its observation time"},
        {"kind": "CHECK_COMPATIBILITY", "label": "Validate specifications against an authentic manufacturer source"},
        {"kind": "CONFIRM_FULFILLMENT", "label": "Verify collection or delivery constraints"},
    ]
    if state == "DISCOVERY_NEEDED":
        gaps.insert(0, {"kind": "DISCOVER_MERCHANTS", "label": "Discover candidate real retailers"})
    if conflicts:
        gaps.insert(0, {"kind": "RECONCILE_CONFLICT", "label": "Resolve conflicting fictional document excerpts"})
    if state == "MORE_EVIDENCE_NEEDED":
        gaps.insert(0, {"kind": "REFRESH_ALTERNATIVES", "label": "Find an alternative to the fictional stock-out"})

    passport = {
        "mode": "EVIDENCE_PASSPORT_17D", "data_origin": "SERVER_CREATED_FICTIONAL_WHAT_IF_ONLY",
        "issued_at": issued_at, "snapshot_sha256": fingerprint,
        "sources": sources, "claims": claims, "conflicts": conflicts,
        "unresolved_verification": gaps,
        "overall_trust_state": "CONFLICT_UNRESOLVED" if conflicts else "INSUFFICIENT_INDEPENDENT_PROOF",
        "freshness_is_real_world_verified": False,
        "real_world_evidence_present": False,
        "merchant_verified": False, "stock_verified": False,
        "compatibility_verified": False, "purchase_allowed": False,
        "interpretation": "The Passport is a provenance trace for fictional what-if data. Hashes identify fixture content, not source authenticity. Model confidence scores and independent validation are not provided.",
    }
    if passport["purchase_allowed"] is not False or any(c["purchase_eligible"] for c in claims):
        raise RuntimeError("Evidence Passport must fail closed")
    return passport
