"""17D: provenance is factual ABOUT fictional inputs, not proof of retail claims."""
import json
from hashlib import sha256

import pytest
from pydantic import ValidationError
from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c


def request(**changes):
    return FreshJourney17C.model_validate({
        "product_query": "65W USB-C PD charger", "budget_inr": 1000,
        "reported_price_inr": 720, "location_note": "Thane",
        "simulated_report": "reported_offer", "simulation_acknowledged": True,
        **changes,
    })


def run(**changes):
    return evaluate_fresh_journey_17c(request(**changes))


def test_passport_attached_to_actual_workflow():
    r = run()
    p = r["evidence_passport"]
    assert p["mode"] == "EVIDENCE_PASSPORT_17D"
    assert p["snapshot_sha256"] == r["workflow"]["snapshot_sha256"]
    assert p["data_origin"] == "SERVER_CREATED_FICTIONAL_WHAT_IF_ONLY"
    assert p["overall_trust_state"] == "INSUFFICIENT_INDEPENDENT_PROOF"
    assert r["workflow"]["workflow_trace"][1]["status"] == "NOT_PROVIDED"


def test_all_safety_invariants():
    for merchant in ("reported_offer", "stockout", "no_merchants"):
        for docs in ("not_submitted", "matching_fixture", "conflicting_fixtures"):
            r = run(simulated_report=merchant, synthetic_documents=docs)
            p = r["evidence_passport"]
            for k in ("purchase_allowed", "real_world_evidence_present", "merchant_verified",
                      "stock_verified", "compatibility_verified", "freshness_is_real_world_verified"):
                assert p[k] is False, (merchant, docs, k)
            assert all(c["purchase_eligible"] is False for c in p["claims"])
            assert all(s["origin_authenticated"] is False and s["independently_verified"] is False
                       and s["external_url"] is None for s in p["sources"])
            assert r["purchase_allowed"] is False and r["gemini_called"] is False
            assert r["database_written"] is False and r["merchant_contacted"] is False


def test_no_documents_gaps_explicit():
    p = run()["evidence_passport"]
    assert not p["conflicts"]
    assert any(c["kind"] == "USB_PD_COMPATIBILITY" and c["verification_status"] == "MISSING"
               for c in p["claims"])
    assert any(g["kind"] == "CHECK_COMPATIBILITY" for g in p["unresolved_verification"])


def test_matching_fixture_executes_real_document_engine():
    r = run(synthetic_documents="matching_fixture")
    assert r["workflow"]["workflow_trace"][1]["status"] == "EVALUATED"
    assert r["workflow"]["product_research"]["retrieval_method"] == "LOCAL_BM25_CHAR_TRIGRAM_NO_EMBEDDINGS"
    assert r["workflow"]["product_research"]["review"]["status"] == "CONDITIONAL_SPEC_MATCH"
    assert r["workflow"]["workflow_state"] == "PROVISIONAL_VERIFICATION_NEEDED"
    assert r["evidence_passport"]["compatibility_verified"] is False


def test_conflicting_fixture_preempts_recommendation():
    r = run(synthetic_documents="conflicting_fixtures")
    assert r["workflow"]["workflow_state"] == "RESEARCH_CONFLICT"
    assert r["workflow"]["recommended_next_action"] == "RECONCILE_CONFLICTING_DOCUMENT_EXCERPTS"
    p = r["evidence_passport"]
    assert p["overall_trust_state"] == "CONFLICT_UNRESOLVED"
    assert len(p["conflicts"]) == 1
    assert set(p["conflicts"][0]["source_ids"]) == {"fictional_spec_a", "fictional_spec_b"}
    assert len(p["conflicts"][0]["citations"]) == 2
    assert any(c["verification_status"] == "CONFLICTED" for c in p["claims"])
    assert p["unresolved_verification"][0]["kind"] == "RECONCILE_CONFLICT"


def test_conflict_never_becomes_confident_even_with_stock_and_budget():
    r = run(budget_inr=5000, reported_price_inr=100,
            synthetic_documents="conflicting_fixtures")
    assert r["workflow"]["merchant_replanning"]["selected"] is not None
    assert r["workflow"]["workflow_state"] == "RESEARCH_CONFLICT"
    assert r["evidence_passport"]["purchase_allowed"] is False


def test_stock_out_is_simulated_revision_not_history():
    r = run(simulated_report="stockout")
    p = r["evidence_passport"]
    assert r["workflow"]["workflow_state"] == "MORE_EVIDENCE_NEEDED"
    assert p["unresolved_verification"][0]["kind"] == "REFRESH_ALTERNATIVES"
    assert any(c["kind"] == "STOCK_QUANTITY" and "0 units" in c["display_value"] for c in p["claims"])
    assert all("HISTORICALLY_VERIFIED" not in json.dumps(s) for s in p["sources"])


def test_no_merchants_yields_missing_not_fictional_store():
    p = run(simulated_report="no_merchants")["evidence_passport"]
    assert p["sources"] == []
    assert p["unresolved_verification"][0]["kind"] == "DISCOVER_MERCHANTS"
    assert not any(c["source_id"] is not None for c in p["claims"])


def test_budget_and_fictional_price_have_distinct_sources():
    r = run(budget_inr=300, reported_price_inr=720)
    assert r["workflow"]["workflow_state"] == "MORE_EVIDENCE_NEEDED"
    p = r["evidence_passport"]
    source_ids = {s["source_id"] for s in p["sources"]}
    assert source_ids == {"fictional_merchant_17c_a"}
    assert any(c["kind"] == "REPORTED_PRICE" and c["source_id"] in source_ids for c in p["claims"])


def test_excerpts_have_source_fingerprints_and_actual_citations():
    r = run(synthetic_documents="conflicting_fixtures")
    p = r["evidence_passport"]
    byid = {s["source_id"]: s for s in p["sources"]}
    assert byid["fictional_spec_a"]["content_sha256"] == sha256(
        b"USB PD supported. Output 20V/3250mA. Cable 5A rated.").hexdigest()
    for c in p["claims"]:
        if c["citation_id"]:
            assert c["source_id"] in byid
            assert c["citation_id"].startswith(c["source_id"] + ":")
    assert all("generated" in s["freshness_label"].lower() for s in p["sources"])


def test_hash_changes_with_synthetic_content():
    a = run(reported_price_inr=720)["evidence_passport"]
    b = run(reported_price_inr=725)["evidence_passport"]
    assert a["sources"][0]["content_sha256"] != b["sources"][0]["content_sha256"]


@pytest.mark.parametrize("changes", [
    {"synthetic_documents": "live_search"},
    {"synthetic_documents": "conflicting_fixtures", "product_query": "Electric kettle"},
    {"synthetic_documents": "matching_fixture", "product_query": "a" * 150 + "charger"},
    {"synthetic_documents": True},
    {"simulation_acknowledged": False},
    {"merchant_verified": True},
])
def test_invalid_sources_never_accepted(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_source_claims_bounded_and_no_external_urls():
    for doc in ("not_submitted", "matching_fixture", "conflicting_fixtures"):
        p = run(synthetic_documents=doc)["evidence_passport"]
        assert len(p["sources"]) <= 3
        assert len(p["claims"]) <= 15
        assert len(p["unresolved_verification"]) <= 8
        assert all(s["external_url"] is None for s in p["sources"])
