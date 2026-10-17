"""Offline developer proof: documented fictional sources only."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c


def main():
    results = {}
    for scenario,report,docs in (
        ("fictional_offer", "reported_offer", "not_submitted"),
        ("matching_documents", "reported_offer", "matching_fixture"),
        ("contradictory_documents", "reported_offer", "conflicting_fixtures"),
        ("fictional_stockout", "stockout", "not_submitted"),
        ("no_merchants", "no_merchants", "not_submitted"),
    ):
        inp = FreshJourney17C(product_query="65W USB-C PD charger", budget_inr=1000,
            location_note="Thane", reported_price_inr=720,
            simulated_report=report, synthetic_documents=docs,
            simulation_acknowledged=True)
        result = evaluate_fresh_journey_17c(inp)
        passp = result["evidence_passport"]
        expected = "RESEARCH_CONFLICT" if docs == "conflicting_fixtures" else (
            "MORE_EVIDENCE_NEEDED" if report == "stockout" else
            "DISCOVERY_NEEDED" if report == "no_merchants" else "PROVISIONAL_VERIFICATION_NEEDED")
        assert result["workflow"]["workflow_state"] == expected
        assert passp["snapshot_sha256"] == result["workflow"]["snapshot_sha256"]
        assert result["purchase_allowed"] is passp["purchase_allowed"] is False
        assert passp["real_world_evidence_present"] is False
        assert all(not c["purchase_eligible"] for c in passp["claims"])
        results[scenario] = {
            "decision": result["workflow"]["workflow_state"],
            "document_stage": result["workflow"]["workflow_trace"][1]["status"],
            "synthetic_sources": len(passp["sources"]),
            "claims": len(passp["claims"]),
            "contradictions": len(passp["conflicts"]),
            "evidence_passport": passp,
        }
        print(f"{scenario}: {expected}; sources={len(passp['sources'])}; "
              f"conflicts={len(passp['conflicts'])}; purchase=False")
    out = ROOT / "qa_reports" / "17d" / "fictional_passport_trace.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"execution_mode": "LOCAL_PYTHON_FICTIONAL_NO_NETWORK",
         "gemini_live": False,"firebase_live": False,"real_merchant_contact": False,
         "source_authentication": False,"scenarios": results}, indent=2), encoding="utf-8")
    print(f"PASS: 17D no-network evidence passport trace -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
