"""Real Python 17C calculation trace; never connects to any external service."""
from __future__ import annotations

import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'backend'))
from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c


def main() -> int:
    template={
        "product_query":"65W USB-C PD charger",
        "budget_inr":1000,
        "location_note":"Thane",
        "reported_price_inr":720,
        "simulation_acknowledged":True,
    }
    outputs=[]
    states={
        "reported_offer":"PROVISIONAL_VERIFICATION_NEEDED",
        "stockout":"MORE_EVIDENCE_NEEDED",
        "no_merchants":"DISCOVERY_NEEDED",
    }
    for scenario, expected in states.items():
        v=evaluate_fresh_journey_17c(FreshJourney17C.model_validate({**template,"simulated_report":scenario}))
        assert v['workflow']['workflow_state']==expected
        assert not v['purchase_allowed']
        print(f"{scenario}: {expected}; trace stages={len(v['workflow']['workflow_trace'])}; model={v['gemini_called']}; purchase={v['purchase_allowed']}")
        outputs.append({"scenario":scenario,"state":expected,"trace":v['workflow']['workflow_trace'],"purchase_allowed":False})
    out=BASE/'qa_reports'/'17c'/'fresh_python_trace.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({
      "status":"REAL_LOCAL_PYTHON_USING_FICTIONAL_SCENARIOS",
      "browser_http_proven":False,"hosted_auth_proven":False,"live_gemini_called":False,
      "merchant_verification_proven":False,"results":outputs,
    },indent=2),encoding='utf-8')
    print(f"TRACE PASSED; JSON: {out}")
    return 0

if __name__=='__main__':raise SystemExit(main())
