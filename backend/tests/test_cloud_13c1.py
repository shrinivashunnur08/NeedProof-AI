"""Chunk 13C.1: no credentials, external calls or paid resources required."""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from app.product_grounding_13c1 import ReviewInput, review_product

STAMP = datetime(2026, 10, 16, tzinfo=timezone.utc)


def source(i, facts):
    return {"source_id": i, "title": f"Source {i}", "url": "https://example.org/product-info",
            "captured_at": STAMP.isoformat(),
            "excerpt": "USB PD supported. Output 20V/3250mA. Cable 5A rated. USB PD not supported.",
            "facts": facts}


def fact(kind, quote, value):
    return {"kind": kind, "quote": quote, "value": value}


def request(sources):
    return ReviewInput(product_label="Example charger", device_model="Sample laptop",
                       device_supports_usb_pd=True, required_power_w=65,
                       required_voltage_v=20, sources=sources)


def complete_source():
    return source("doc-1", [fact("USB_PD_SUPPORT", "USB PD supported", "true"),
                            fact("OUTPUT_PROFILE", "Output 20V/3250mA", "20V/3250mA"),
                            fact("CABLE_CURRENT_RATING", "Cable 5A rated", "5A")])


def test_missing_documents_do_not_create_facts():
    x = review_product(request([]))
    assert x["status"] == "INSUFFICIENT_SOURCE_EVIDENCE" and x["cited_facts"] == []
    assert x["purchase_allowed"] is False


def test_conditional_match_never_purchase_ready():
    x = review_product(request([complete_source()]))
    assert x["status"] == "CONDITIONAL_SPEC_MATCH"
    assert x["purchase_allowed"] is False
    assert x["provenance"] == "USER_SUPPLIED_EXCERPTS_NOT_INDEPENDENTLY_VERIFIED"
    assert len(x["cited_facts"]) == 3


def test_contradictory_pd_claims_block_match():
    second = source("doc-2", [fact("USB_PD_SUPPORT", "USB PD not supported", "false")])
    x = review_product(request([complete_source(), second]))
    assert x["status"] == "INSUFFICIENT_SOURCE_EVIDENCE"
    assert any(z["reason"] == "CONTRADICTORY_SOURCE_FACTS" for z in x["evidence_gaps"])


def test_missing_cable_fact_stops_grounded_review():
    incomplete = complete_source()
    incomplete["facts"] = incomplete["facts"][:2]
    x = review_product(request([incomplete]))
    assert x["status"] == "INSUFFICIENT_SOURCE_EVIDENCE"


def test_quote_must_be_present_in_excerpt():
    bad = complete_source()
    bad["facts"][0]["quote"] = "this text does not occur in the source"
    with pytest.raises(ValidationError):
        request([bad])


def test_invalid_fact_cannot_be_smuggled_in():
    bad = complete_source()
    bad["facts"][1]["value"] = "20V/9000mA"
    with pytest.raises(ValidationError):
        request([bad])


def test_duplicate_source_ids_rejected():
    with pytest.raises(ValidationError):
        request([complete_source(), complete_source()])


def test_underpowered_profile_is_a_mismatch():
    bad = complete_source()
    bad["excerpt"] = bad["excerpt"].replace("20V/3250mA", "20V/3000mA")
    bad["facts"][1] = fact("OUTPUT_PROFILE", "Output 20V/3000mA", "20V/3000mA")
    x = review_product(request([bad]))
    assert x["status"] == "REPORTED_SPEC_MISMATCH"
    assert x["purchase_allowed"] is False


def test_anonymous_urls_are_not_fetched(monkeypatch):
    # Pure function cannot use network by design; source URLs are returned unchanged as citations.
    x = review_product(request([complete_source()]))
    assert all(item["url"] == "https://example.org/product-info" for item in x["cited_facts"])


def test_disagreeing_current_at_same_voltage_blocks_match():
    other = source("doc-2", [fact("OUTPUT_PROFILE", "Output 20V/3250mA", "20V/3250mA")])
    prior = complete_source()
    prior["excerpt"] = prior["excerpt"].replace("20V/3250mA", "20V/3000mA")
    prior["facts"][1] = fact("OUTPUT_PROFILE", "Output 20V/3000mA", "20V/3000mA")
    result = review_product(request([prior, other]))
    assert result["status"] == "INSUFFICIENT_SOURCE_EVIDENCE"
    assert any(g["kind"] == "OUTPUT_PROFILE" for g in result["evidence_gaps"])

def test_standard_three_amp_case_does_not_need_cable_claim():
    s = complete_source()
    s["facts"] = s["facts"][:2]
    small = request([s])
    small.required_power_w = 60
    x = review_product(small)
    assert x["status"] == "CONDITIONAL_SPEC_MATCH"
