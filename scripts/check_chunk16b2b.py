#!/usr/bin/env python3
"""Safe NeedProof 16B.2B offline readiness and evidence status gate.

Runs no network calls and does not read credentials, tokens or project env files.
Real-token integration remains pending and MUST NOT be inferred from PASS.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import re
import subprocess
from pathlib import Path

BASELINE = "5c8f5f2"
REQUIRED_FLAGS = (
    "GUIDED_JOURNEY_16A_ENABLED", "BI_COMMAND_CENTER_14B4_ENABLED",
    "INVENTORY_INTELLIGENCE_14B3_ENABLED", "RETAIL_INSIGHTS_14B2_ENABLED",
    "RETAIL_FORECAST_14B1_ENABLED", "DECISION_ORCHESTRATOR_14A3_ENABLED",
    "BASKET_OPTIMIZER_14A2_ENABLED", "EVIDENCE_PLANNER_14A1_ENABLED",
    "PRODUCT_RETRIEVAL_13C2_ENABLED", "PRODUCT_GROUNDING_13C1_ENABLED",
)
REQUIRED_DOCS = (
    "docs/CHUNK16B_LIVE_READINESS.md",
    "docs/CHUNK16B2_LIVE_VALIDATION_PLAN.md",
)

def audit(root: Path, *, verify_git: bool = True) -> list[str]:
    issues = []
    if verify_git:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", BASELINE, "HEAD"],
            cwd=root, capture_output=True, check=False,
        )
        if ancestor.returncode:
            issues.append("Git HEAD must include commit " + BASELINE)
    for name in REQUIRED_DOCS:
        if not (root / name).is_file():
            issues.append("Missing release documentation: " + name)
    gate_path = root / "scripts/preflight_chunk16b2.py"
    if not gate_path.is_file():
        issues.append("Missing committed 16B.2A source security gate")
    else:
        spec = importlib.util.spec_from_file_location("np16b2a_auditor", gate_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        issues.extend(module.audit(root, verify_git=verify_git))
    api_file = root / "backend/app/cloud_decision_api.py"
    api = api_file.read_text(encoding="utf-8") if api_file.is_file() else ""
    for flag in REQUIRED_FLAGS:
        pattern = re.compile(r'os\.environ\.get\(\s*["\']' + re.escape(flag) + r'["\']\s*,\s*["\']false["\']\s*\)')
        if not pattern.search(api):
            issues.append("Feature no longer defaults OFF: " + flag)
    if 'os.environ.get("MERCHANT_EVIDENCE_STORAGE", "")' not in api:
        issues.append("Evidence storage selection guard not confirmed")
    return issues

def report(issues: list[str]) -> dict:
    return {
        "schema_version": "needproof-16b2b-offline-v1",
        "baseline": BASELINE,
        "local_security_gate": "PASS" if not issues else "STOP",
        "issues": issues,
        "production_real_id_tokens": "UNVERIFIED",
        "production_app_check_tokens": "UNVERIFIED",
        "cross_project_firestore_io": "UNVERIFIED",
        "real_merchant_role_isolation": "UNVERIFIED",
        "hosted_16a_and_analytics": "NOT_TESTED_AND_DISABLED_BY_DEFAULT",
        "cloud_calls_performed": 0,
        "deployments_performed": 0,
        "cloud_billing_guarantee": "NONE_FOR_EXISTING_BILLING_ENABLED_SERVICES",
    }

def main() -> int:
    p = argparse.ArgumentParser(description="NeedProof 16B.2B strictly offline readiness check")
    p.add_argument("--check", action="store_true", help="Run local code checks only")
    p.add_argument("--plan", action="store_true", help="Print next manual validation steps; no calls")
    p.add_argument("--json", action="store_true", help="Print sanitized JSON report; no tokens")
    args = p.parse_args()
    if args.plan:
        print("STRICT ZERO-NEW-CLOUD-SPEND PATH:")
        print("1. Do not run gcloud deploy, enable new API flags, or contact paid endpoints.")
        print("2. Continue Chunk 16C local desktop/mobile demo QA and record a walkthrough.")
        print("3. 16A and analytics remain local-only until live deployment is separately approved.")
        print("CONTROLLED LIVE PATH (REQUIRES EXPLICIT APPROVAL FOR POSSIBLE COST):")
        print("1. Inspect Cloud Run traffic, billing state, quotas, origin allowlist and rollback.")
        print("2. Use a dedicated synthetic test account on the existing authorized hosted UI.")
        print("3. Verify real Auth + App Check, rejection states and browser CORS; never export tokens.")
        print("4. Test customer/merchant ownership against deployed Firestore only if enabled.")
        print("5. Deploy backend from backend/ only after approval; preserve traffic and rollback.")
        return 0
    root = Path(__file__).resolve().parents[1]
    issues = audit(root)
    result = report(issues)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("NeedProof 16B.2B — OFFLINE ONLY, NO CLOUD REQUESTS")
        print("PASS: original 16B.2A security audit and 10 default-OFF API flags" if not issues else "STOP: offline release gate failed")
        for issue in issues:
            print("STOP: " + issue)
        print("UNVERIFIED: real Auth, App Check, hosted CORS, Firestore IAM and merchant roles")
        print("NO live requests, deployments, billing changes, or service modifications made")
    return 1 if issues else 0

if __name__ == "__main__":
    raise SystemExit(main())
