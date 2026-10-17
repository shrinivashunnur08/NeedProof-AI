"""NeedProof 16C.3 local-only demo acceptance audit.

No network calls, credentials, deployment commands, or imports from app code.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "reported_offer": "PROVISIONAL_VERIFICATION_NEEDED",
    "stockout": "MORE_EVIDENCE_NEEDED",
    "document_conflict": "RESEARCH_CONFLICT",
    "no_merchants": "DISCOVERY_NEEDED",
}


def audit(root: Path) -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    def record(label: str, success: bool, detail: str) -> None:
        checks.append({"check": label, "result": "PASS" if success else "FAIL", "detail": detail})

    def read(rel: str) -> str:
        path = root / rel
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    showcase = read("frontend/src/FreeShowcase.tsx")
    replay_ui = read("frontend/src/components/JudgeReplay16C2.tsx")
    replay_raw = read("frontend/src/generated/needproof16cReplay.json")
    record("React showcase exists", bool(showcase), "Expected frontend/src/FreeShowcase.tsx")
    record("Integrated demo component", bool(replay_ui) and "JudgeReplay16C2" in showcase,
           "16C.2 replay must be wired into React")

    # The compact sidebar should be self-contained on desktop, without its own scrollbar.
    match = re.search(r'aria-label="NeedProof workspace sidebar"\s*className="([^"]+)"', showcase)
    classes = match.group(1) if match else ""
    record("Compact desktop sidebar", bool(classes) and "lg:h-dvh" in classes and "overflow-hidden" in classes
           and not any(name in classes for name in ("overflow-y-auto", "overflow-y-scroll")),
           "Fixed-height desktop sidebar without its own vertical scrollbar")
    record("Guided tour entry", "Start guided demo" in showcase,
           "Judge entry point is visible in primary navigation")
    record("Short viewport fallback", "max-height:" in showcase,
           "Responsive layout includes short-height adjustments")

    try:
        payload = json.loads(replay_raw)
    except (ValueError, TypeError):
        payload = None
    record("Replay is valid JSON", isinstance(payload, dict), "Checked-in offline replay must parse")
    if isinstance(payload, dict):
        scenarios = payload.get("scenarios", {})
        record("Exactly four replay cases", isinstance(scenarios, dict) and set(scenarios) == set(CASES),
               "Merchant claim, stock-out, document conflict, no candidates")
        record("Replay explicitly synthetic", payload.get("synthetic") is True and
               payload.get("mode") == "OFFLINE_ENGINE_REPLAY_16C",
               "No live inventory, customer or merchant claims")
        for case, expected in CASES.items():
            item = scenarios.get(case, {}) if isinstance(scenarios, dict) else {}
            workflow = item.get("workflow", {}) if isinstance(item, dict) else {}
            record(f"{case}: distinct decision state", workflow.get("workflow_state") == expected,
                   f"Expected {expected}")
            record(f"{case}: five-step trace", len(workflow.get("workflow_trace", [])) == 5,
                   "Full five-stage engine explanation retained")
            record(f"{case}: purchase safety", item.get("purchase_allowed") is False and
                   workflow.get("purchase_allowed") is False and
                   workflow.get("stock_independently_verified") is False and
                   workflow.get("merchant_contact_performed") is False,
                   "Unverified evidence cannot authorize purchase, stock, or contact")
        stockout = scenarios.get("stockout", {}) if isinstance(scenarios, dict) else {}
        record("Stock-out triggers change", stockout.get("workflow", {}).get("change_detection", {}).get("changed") is True,
               "Evidence update must trigger new decision state")
    else:
        record("Exactly four replay cases", False, "Missing/invalid replay data")

    record("Replay transparency", "fictional" in replay_ui.lower() or "offline" in replay_ui.lower(),
           "UI must label offline and fictional nature")

    # Asset metrics are informational; large bundles require performance QA, not false success.
    dist = root / "frontend/dist/assets"
    js_assets = list(dist.glob("*.js")) if dist.is_dir() else []
    main_bundles = [p for p in js_assets if p.name.startswith("index-")]
    main_size = max((p.stat().st_size for p in main_bundles), default=None)
    warnings = []
    if main_size is None:
        warnings.append("Vite dist not found. Run 'npm run build' in frontend before the final asset audit.")
    elif main_size > 500_000:
        warnings.append(f"Initial index bundle is {main_size / 1024:.1f} KiB; investigate startup performance on mobile.")
    warnings.extend([
        "Real Firebase ID tokens, App Check, hosted CORS, merchant ownership and deployed Firestore IAM are NOT verified by this audit.",
        "A static audit cannot prove visual layout, keyboard access, mobile touch behavior or network-free operation. Complete manual browser QA.",
        "No cloud cost guarantee: the existing billing-enabled project needs independent quota and spend controls."
    ])
    return {
        "schema": "needproof-16c3-release-audit-v1",
        "scope": "LOCAL_STATIC_FILES_NO_NETWORK_NO_CLOUD_CHANGES",
        "passed": sum(c["result"] == "PASS" for c in checks),
        "failed": sum(c["result"] == "FAIL" for c in checks),
        "checks": checks,
        "main_bundle_bytes": main_size,
        "warnings": warnings,
        "hosted_release_approved": False,
        "cloud_resources_modified": False,
    }


def render_md(data: dict[str, Any]) -> str:
    lines = [
        "# NeedProof 16C.3 — Local release QA report", "",
        f"**Checks:** {data['passed']} passed, {data['failed']} failed.",
        "**Deployment:** Not attempted. **Hosted approval:** Not granted.", "",
        "## Static checks", "",
        "| Check | Result | Evidence |", "|---|---|---|",
    ]
    for c in data["checks"]:
        clean = c["detail"].replace("|", "\\|")
        lines.append(f"| {c['check']} | {c['result']} | {clean} |")
    lines.extend(["", "## Warnings and manual follow-ups", ""])
    lines.extend(f"- {w}" for w in data["warnings"])
    lines.extend(["", "## Human acceptance matrix", "",
        "See docs/CHUNK16C3_FINAL_QA_MATRIX.md. Run the tests at 375×812, 768×1024, 1366×768 and 1920×1080, plus a short desktop viewport. Record screenshots and findings.",
        "", "**No claim of production authentication, live inventory, observed savings or real merchant verification.**", ""])
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="Audit only; no files written")
    p.add_argument("--report", action="store_true", help="Write local reports under qa_reports/16c3")
    args = p.parse_args()
    if not (args.check or args.report):
        p.error("Provide --check or --report")
    result = audit(ROOT)
    print("NeedProof 16C.3 local final UX/replay release audit — NO CLOUD CALLS")
    for item in result["checks"]:
        print(f"{item['result']}: {item['check']} — {item['detail']}")
    for warning in result["warnings"]:
        print("WARN:", warning)
    print(f"TOTAL: {result['passed']} passed, {result['failed']} failed")
    if args.report:
        folder = ROOT / "qa_reports/16c3"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "report.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (folder / "report.md").write_text(render_md(result), encoding="utf-8")
        print("LOCAL REPORT:", folder / "report.md")
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
