#!/usr/bin/env python3
"""NeedProof 16B.2A offline security/config integrity gate. No cloud/network actions."""
from __future__ import annotations
import argparse
import hashlib
import subprocess
from pathlib import Path

# Audited 16A + 16B.1 additive baseline; normalize CRLF for Windows checkout.
EXPECTED = {'backend/app/cloud_decision_api.py': '12fe891e544dfbf471a5baf85bacdea2765e32404b73b42bc481dce60d97cc93', 'backend/app/guided_journey_16a.py': '931a658d43ed984392c85edd51de2c08eb48df17b52a26922a91526d14f5cc84', 'backend/app/evidence_firestore_13b2.py': 'b1d755c6513868fed38d72990b4d0380aa2cca91d61daea8ee72397a902cf356', 'backend/app/merchant_evidence_13b.py': '0d6c83df49f8c5c92f8d06bec7df8c0b79ebd99164a5ea36996568f702d8bdb3', 'backend/app/api_guard_15a.py': 'ea9a807b2cc3deb09a6f3305d37f3018cf94e1b4e935b1a85963290258ac5e34', 'frontend/src/lib/cloudDecisions.ts': 'fdbc5beb8a23f5ad9b3bd6f545371bbe854db70dc4c7f6025751661aee9185ec', 'frontend/src/lib/guidedJourney16a.ts': 'b28b9401cfe5a03afd5ae0c3d55492cea9296749a3bc96a4107372fb2b52f954', 'firestore.rules': 'a9d5ddd67024ec6b9522034f6a937c5dbf1630ed23d66eb0ddfeed8fcec79c58'}
BASELINE = "e71f91e"


def sha256_normalized(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def audit(root: Path, *, verify_git: bool = True) -> list[str]:
    issues: list[str] = []
    for rel, digest in EXPECTED.items():
        path = root / rel
        if not path.is_file():
            issues.append("Required audited source missing: " + rel)
        elif sha256_normalized(path) != digest:
            issues.append("Audited source differs: " + rel)

    if verify_git:
        if not (root / ".git").exists():
            issues.append("Git checkout not found; run from NeedProof repository root")
        else:
            result = subprocess.run(
                ["git", "merge-base", "--is-ancestor", BASELINE, "HEAD"],
                cwd=root, capture_output=True, text=True, check=False,
            )
            if result.returncode != 0:
                issues.append("Git HEAD is not the expected 16B.1 commit or descendant: " + BASELINE)

    def source(name: str) -> str:
        path = root / name
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    api = source("backend/app/cloud_decision_api.py")
    client = source("frontend/src/lib/cloudDecisions.ts")
    guided = source("frontend/src/lib/guidedJourney16a.ts")
    firestore = source("backend/app/evidence_firestore_13b2.py")
    rules = source("firestore.rules")
    assertions = {
        "Backend requires both Auth and App Check":
            'authorization.startswith("Bearer ")' in api and 'not x_firebase_appcheck' in api,
        "Backend checks ID and App Check with SDK":
            'auth.verify_id_token(' in api and 'app_check.verify_token(' in api,
        "Backend checks App Check app id":
            'decoded_app.get("app_id") != FIREBASE_WEB_APP_ID' in api,
        "Origin allowlist sourced from explicit setting":
            'os.environ.get("ALLOWED_ORIGINS", "")' in api and 'allow_origins=ALLOWED_ORIGINS' in api,
        "Cloud client obtains both credentials":
            'user.getIdToken()' in client and 'getToken(appCheck)' in client,
        "Cloud client passes both credentials":
            'Authorization: `Bearer ${userToken}`' in client and '"X-Firebase-AppCheck": appToken.token' in client,
        "Guided journey obtains Auth/App Check":
            'getToken(appCheck)' in guided and 'getIdToken()' in guided,
        "Guided journey UI feature gated":
            'VITE_GUIDED_JOURNEY_16A_ENABLED === "true"' in guided,
        "Guided journey server feature gated":
            'GUIDED_JOURNEY_16A_ENABLED' in api and '"false"' in api,
        "Firestore evidence defaults disabled":
            'MERCHANT_EVIDENCE_ENABLED", "false"' in firestore,
        "Firestore project exactly scoped":
            'PROJECT = "needproof-ai-showcase"' in firestore,
        "Firestore browser deny-all fallback":
            'match /{document=**}' in rules and 'allow read, write: if false;' in rules,
        "Firestore browser owner isolation":
            'request.auth.uid == uid' in rules,
        "UI and backend keep purchase safety":
            'purchase_allowed' in source("backend/app/guided_journey_16a.py")
    }
    for label, ok in assertions.items():
        if not ok:
            issues.append("Security invariant not confirmed: " + label)

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="NeedProof 16B.2A local read-only release gate")
    parser.add_argument("--check", action="store_true", help="Run OFFLINE checks only")
    parser.add_argument("--print-live-plan", action="store_true", help="Print manual opt-in gate; execute nothing")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.print_live_plan:
        print("LIVE TESTING IS NOT AUTHORIZED BY THIS SCRIPT.")
        print("1. Explicitly accept possible Cloud Run/Auth/App Check/Firestore charges before live requests.")
        print("2. Confirm provider quota and rollback safeguards in docs/CHUNK16B2_LIVE_VALIDATION_PLAN.md.")
        print("3. Use an approved account in the existing hosted app; never export or paste tokens.")
        print("4. Validate token rejection, CORS, owner isolation and the still-disabled new feature flags.")
        print("5. Do not deploy, shift Cloud Run traffic, change IAM or activate merchant evidence by default.")
        return 0
    print("NeedProof 16B.2A — OFFLINE READINESS GATE")
    print("No network, credentials, Firebase tokens, IAM changes, deployments or new costs.")
    issues = audit(root)
    if issues:
        for item in issues:
            print("STOP: " + item)
        print("Do not deploy or enable any live flags. Share only the STOP lines.")
        return 1
    print(f"PASS: Git baseline {BASELINE} or descendant")
    print(f"PASS: {len(EXPECTED)} source fingerprints and 14 security invariants")
    print("PASS: Browser Auth + App Check, backend verification, Firestore browser-deny defaults")
    print("PASS: 16A and merchant-evidence backends stay feature-gated by default")
    print("OUTSTANDING: Real tokens, hosted CORS, deployed Firestore IAM, merchant role checks")
    print("OUTSTANDING: Cloud cost ceilings, quota policies and judge-facing live rollout")
    print("NO live resources tested or changed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
