"""Local 17E proof: real 14A.1 sidecar + 14A.3 replanning, synthetic-only."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c

BASE = dict(product_query="65W USB-C PD laptop charger", budget_inr=1000,
            location_note="Thane", reported_price_inr=720,
            simulation_acknowledged=True, simulated_report="reported_offer")
CASES = {
    "reported_offer": {},
    "spec_conflict": {"synthetic_documents": "conflicting_fixtures"},
    "fictional_stockout_transition": {"fictional_merchant_update_17e": "stockout_after_report"},
    "fictional_restock_transition": {"simulated_report": "stockout", "fictional_merchant_update_17e": "restock_after_stockout"},
    "no_merchants": {"simulated_report": "no_merchants"},
}
result = {}
for name, args in CASES.items():
    response = evaluate_fresh_journey_17c(FreshJourney17C.model_validate({**BASE, **args}))
    q = response["verification_queue_17e"]
    assert not response["purchase_allowed"] and not q["purchase_allowed"]
    assert not q["external_requests_performed"] and not q["merchant_verified"]
    assert q["snapshot_sha256"] == response["evidence_passport"]["snapshot_sha256"]
    result[name] = {"workflow_state": response["workflow"]["workflow_state"],
                    "first_proof_action": q["recommended_action_id"],
                    "evsi_status": q["hypothetical_evsi"]["status"],
                    "evsi_hypothetical_actions": q["hypothetical_evsi"]["actions"],
                    "simulation_event": q["hypothetical_merchant_update"],
                    "purchase_allowed": False, "merchant_contacted": False}
    print(f"{name}: {result[name]['workflow_state']} -> {result[name]['first_proof_action']}; "
          f"EVSI={result[name]['evsi_status']}; purchase=False")
path = ROOT / "qa_reports" / "17e" / "verification_trace.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({"execution": "REAL_LOCAL_PYTHON_SYNTHETIC_DATA_NO_NETWORK",
                            "google_model_called": False,
                            "real_merchant_contacted": False,
                            "real_business_kpis_measured": False,
                            "scenarios": result}, indent=2) + "\n", encoding="utf-8")
print("PASS: 17E execution trace ->", path)
