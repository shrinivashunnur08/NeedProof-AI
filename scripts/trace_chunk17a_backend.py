#!/usr/bin/env python3
"""NeedProof AI: local-only, real-engine and in-process FastAPI trace.

This script deliberately does not invoke Firebase, Gemini, Places, Cloud Run,
Firestore, merchant messaging, billing or deployed URLs. It runs real Python
engines and a local in-process FastAPI TestClient (with TEST-ONLY auth override).

Execute from project root:
  backend\\.venv\\Scripts\\python.exe scripts\\trace_needproof_backend.py --all
  backend\\.venv\\Scripts\\python.exe scripts\\trace_needproof_backend.py --scenario stockout
  backend\\.venv\\Scripts\\python.exe scripts\\trace_needproof_backend.py --all --save qa_reports\\developer_trace.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


# An in-process TestClient does not access a hosted service. On Windows,
# asyncio/AnyIO builds its internal socketpair over 127.0.0.1. Reject external
# TCP destinations while allowing local loopback for the event-loop wake-up.
# This guard is a defensive smoke-test measure, not an OS-level egress sandbox.
import ipaddress
import socket

_original_connect_17a = socket.socket.connect
_original_connect_ex_17a = socket.socket.connect_ex
_original_create_connection_17a = socket.create_connection


def _is_loopback_address_17a(address: object) -> bool:
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    if not isinstance(host, str):
        return False
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False  # Deny domain names: don't initiate a DNS lookup.


def _local_only_connect(self: socket.socket, address: object) -> None:
    if not _is_loopback_address_17a(address):
        raise RuntimeError("Chunk 17A blocks non-loopback TCP connections")
    return _original_connect_17a(self, address)


def _local_only_connect_ex(self: socket.socket, address: object) -> int:
    if not _is_loopback_address_17a(address):
        raise RuntimeError("Chunk 17A blocks non-loopback TCP connections")
    return _original_connect_ex_17a(self, address)


def _local_only_create_connection(address: object, *args, **kwargs):
    if not _is_loopback_address_17a(address):
        raise RuntimeError("Chunk 17A blocks non-loopback TCP connections")
    return _original_create_connection_17a(address, *args, **kwargs)


socket.socket.connect = _local_only_connect
socket.socket.connect_ex = _local_only_connect_ex
socket.create_connection = _local_only_create_connection

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if not (BACKEND / "app" / "guided_journey_16a.py").is_file():
    raise SystemExit("ERROR: Project backend missing. Extract the ZIP into D:\\AiBuilderCup\\needproof-ai (not a nested folder).")
sys.path.insert(0, str(BACKEND))

from app.guided_journey_16a import GuidedJourneyInput16A, evaluate_guided_journey_16a

SCENARIOS = (
    "reported_offer",
    "stockout",
    "document_conflict",
    "no_merchants",
)
EXPECTED = {
    "reported_offer": "PROVISIONAL_VERIFICATION_NEEDED",
    "stockout": "MORE_EVIDENCE_NEEDED",
    "document_conflict": "RESEARCH_CONFLICT",
    "no_merchants": "DISCOVERY_NEEDED",
}


def header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def show_workflow(case: str) -> dict:
    payload = GuidedJourneyInput16A.model_validate({
        "scenario": case,
        "simulation_acknowledged": True,
        "include_illustrative_business_context": True,
    })
    result = evaluate_guided_journey_16a(payload)
    flow = result["workflow"]
    assert flow["workflow_state"] == EXPECTED[case], (case, flow["workflow_state"])
    assert result["purchase_allowed"] is False and flow["purchase_allowed"] is False
    assert result["fixture_origin"] == "SERVER_OWNED_SYNTHETIC_NOT_REAL_MERCHANTS"
    assert len(flow["workflow_trace"]) == 5
    header("Case: " + case + " | REAL LOCAL PYTHON ENGINE")
    print("Input: ", json.dumps(payload.model_dump(mode="json"), ensure_ascii=False))
    print("Developer meaning:", result["title"])
    print("Workflow state:", flow["workflow_state"])
    print("Next backend action:", flow["recommended_next_action"])
    print("Reason:", flow["reason"])
    print("\n5 internal algorithm stages:")
    for index, stage in enumerate(flow["workflow_trace"], 1):
        print(f"  {index}. {stage['stage']} -> {stage['state']} | {stage['status']}")
    merchant = flow["merchant_replanning"]
    selected = merchant.get("selected")
    print("\nMerchant replanning:", merchant["decision_status"])
    print("Selected candidate:", (selected or {}).get("name") or "NONE")
    print("Source review:", flow["product_research"]["review"]["status"])
    plan = flow["hypothetical_verification_plan"]
    print("Hypothetical next check:", plan.get("recommended_action_id") if plan else "None: discovery first")
    print("Hypothetical basket:", flow["synthetic_basket_scenario"]["scenario_status"])
    print("Purchase allowed:", result["purchase_allowed"])
    print("External model called:", result["cloud_model_used"])
    print("Database written:", result["source_records_persisted"])
    print("Real merchants contacted:", result["real_merchant_contact"])
    return result


def test_local_route() -> None:
    """Demonstrate actual FastAPI dispatch with explicit TEST-ONLY identity override.

    This DOES NOT verify a real Firebase ID token or App Check token.
    """
    from fastapi.testclient import TestClient
    from app.cloud_decision_api import app, require_firebase_client

    header("IN-PROCESS HTTP trace: client -> FastAPI endpoint -> engine")
    path = "/api/v1/demo/guided-journey"
    payload = {"scenario": "reported_offer", "simulation_acknowledged": True}
    client = TestClient(app)
    unauth = client.post(path, json=payload)
    print(f"POST {path} without tokens => HTTP {unauth.status_code} (expected 401)")
    assert unauth.status_code == 401, unauth.text

    original = os.environ.get("GUIDED_JOURNEY_16A_ENABLED")
    app.dependency_overrides[require_firebase_client] = lambda: "LOCAL_TEST_IDENTITY_NOT_REAL_AUTH"
    os.environ["GUIDED_JOURNEY_16A_ENABLED"] = "true"
    try:
        accepted = client.post(path, json=payload)
        print(f"POST {path} with local test-identity override => HTTP {accepted.status_code} (expected 200)")
        assert accepted.status_code == 200, accepted.text
        result = accepted.json()
        print("FastAPI response state:", result["workflow"]["workflow_state"])
        print("Purchase authorized:", result["purchase_allowed"])
        assert result["workflow"]["workflow_state"] == EXPECTED["reported_offer"]
        assert result["purchase_allowed"] is False
    finally:
        app.dependency_overrides.pop(require_firebase_client, None)
        if original is None:
            os.environ.pop("GUIDED_JOURNEY_16A_ENABLED", None)
        else:
            os.environ["GUIDED_JOURNEY_16A_ENABLED"] = original
    print("NOTE: TestClient lives inside this Python process; it did NOT contact Cloud Run.")
    print("NOTE: The override is TEST ONLY; production Auth + App Check were not proven.")


def test_business_engines() -> dict:
    """Exercise actual standalone 13C and 14B engines with fictional inputs."""
    from app.product_retrieval_13c2 import RetrievalInput, retrieve_and_review
    from app.retail_forecast_14b1 import ForecastInput14B1, evaluate_retail_forecast_14b1
    from app.retail_segments_14b2 import CommerceInsightsInput14B2, evaluate_commerce_insights_14b2
    from app.inventory_intelligence_14b3 import InventoryInput14B3, evaluate_inventory_14b3
    from app.bi_command_center_14b4 import BIInput14B4, evaluate_bi_command_center_14b4

    header("SUPPLEMENTAL REAL BACKEND MODULES | Synthetic inputs only")
    source_text = "USB PD supported. Output 20V/3250mA. Cable 5A rated."
    retrieval = retrieve_and_review(RetrievalInput.model_validate({
        "query": "USB PD charger 20V 65W",
        "review": {
            "product_label": "Example charger", "device_model": "Sample laptop",
            "device_supports_usb_pd": True, "required_power_w": 65,
            "required_voltage_v": 20,
            "sources": [{"source_id": "doc_demo", "title": "Fictional specification", "captured_at": datetime.now(timezone.utc).isoformat(), "excerpt": source_text, "facts": []}],
        },
    }))
    print("13C.2 retrieval & source review:", retrieval["review"]["status"], "| purchase=", retrieval["purchase_allowed"])
    assert retrieval["review"]["status"] == "CONDITIONAL_SPEC_MATCH" and retrieval["purchase_allowed"] is False

    start = date.today() - timedelta(days=42)
    sales = [{"day": (start + timedelta(days=i)).isoformat(), "units_sold": 6 + i % 7, "reported_stockout": i % 23 == 0} for i in range(42)]
    forecast = evaluate_retail_forecast_14b1(ForecastInput14B1.model_validate({
        "product_label": "Fictional charger", "history": sales, "horizon_days": 7,
        "on_hand_units": 80, "replenishment_lead_days": 5, "synthetic_demo": True,
    }))
    print("14B.1 forecast:", forecast.get("mode"), "| response keys:", ", ".join(sorted(forecast)[:8]))

    profiles = [{"recency_days": (i * 7) % 110, "orders_90d": 1 + i % 11, "spend_minor_90d": 30000 + i * 9000} for i in range(48)]
    baskets = [["CHARGER", "CABLE"] if i % 3 else ["MOUSE", "CASE"] for i in range(48)]
    segments = evaluate_commerce_insights_14b2(CommerceInsightsInput14B2.model_validate({
        "profiles": profiles, "baskets": baskets, "minimum_pair_orders": 3, "synthetic_demo": True,
    }))
    print("14B.2 cohorts/baskets:", segments.get("mode"), "| purchase=", segments.get("purchase_allowed"))

    stock = 350
    history = []
    for i in range(42):
        sold = 4 + i % 5
        close = stock - sold
        history.append({"day": (start + timedelta(days=i)).isoformat(), "opening_units": stock,
                        "received_units": 0, "sold_units": sold, "closing_units": close,
                        "reported_stockout": False})
        stock = close
        if stock < 0:
            raise RuntimeError("Synthetic fixture went negative")
    inv = evaluate_inventory_14b3(InventoryInput14B3.model_validate({
        "sku_code": "DEMO-SKU-TRACE", "history": history, "lead_time_days": 7, "synthetic_demo": True,
    }))
    print("14B.3 inventory:", inv.get("mode"), "| response keys:", ", ".join(sorted(inv)[:8]))

    bi = evaluate_bi_command_center_14b4(BIInput14B4.model_validate({
        "as_of": date.today().isoformat(), "synthetic_demo": True,
        "forecast": {"sku_code": "DEMO-SKU", "projected_sales_units": 53.4,
                     "horizon_days": 7, "backtest_wape_pct": 17.5, "reported_stockout_days": 0},
        "inventory": {"sku_code": "DEMO-SKU", "reported_on_hand_units": 25,
                      "balance_mismatches": 1, "cross_day_gaps": 0,
                      "unusual_sales_days": 2, "modeled_lead_time_shortfall_units": 14.6},
        "cohorts": {"anonymous_profile_count": 48, "aggregate_cohort_count": 2,
                    "minimum_cohort_size": 9, "association_rule_count": 3},
        "verification": {"candidates_considered": 4, "unresolved_evidence_items": 2,
                         "provisional_candidates": 3},
    }))
    print("14B.4 BI command center:", bi.get("mode"), "| coverage:", bi["coverage"]["available_modules"], "modules")
    print("All supplemental outputs are illustrative and do NOT prove actual retail outcomes.")
    return {"retrieval": retrieval, "forecast": forecast, "segments": segments, "inventory": inv, "bi": bi}


def main() -> int:
    parser = argparse.ArgumentParser(description="Trace NeedProof real local Python engines from customer evidence to decision. Offline only.")
    parser.add_argument("--scenario", choices=SCENARIOS, help="Run one coherent 16A scenario")
    parser.add_argument("--all", action="store_true", help="Run four 16A cases, in-process FastAPI auth smoke, and 13C/14B modules")
    parser.add_argument("--save", type=Path, help="Optional write JSON of fictional backend outputs to specified local file")
    args = parser.parse_args()
    if not args.all and args.scenario is None:
        parser.error("Choose --all or --scenario CASE")
    print("NeedProof AI CHUNK 17A EXECUTION PROOF | OFFLINE ONLY | No keys, network, cloud or merchant contact")
    records = {"trace_mode": "LOCAL_REAL_ENGINE_SYNTHETIC", "firebase_token_verified": False,
               "app_check_verified": False, "hosted_backend_called": False, "scenarios": {}}
    for scenario in (SCENARIOS if args.all else (args.scenario,)):
        records["scenarios"][scenario] = show_workflow(scenario)
    if args.all:
        test_local_route()
        records["business_modules"] = test_business_engines()
    if args.save:
        destination = args.save if args.save.is_absolute() else ROOT / args.save
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(records, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
        print("\nSaved fictional trace to:", destination)
    header("TRACE PASSED — Read the printed five-stage states above")
    print("This confirms local execution of Python algorithms, NOT a live browser -> Cloud Run transaction.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
