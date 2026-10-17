"""Chunk 16B local-only, read-only release gate.

Does not import gcloud/firebase, use external tools, read ADC credentials, connect
network sockets, or mutate application source/feature flags.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BASELINE = "f490ddd"
# Hashes are compared after normalized LF line endings, which tolerates Windows CRLF.
AUDITED = {
    "backend/app/cloud_decision_api.py": "12fe891e544dfbf471a5baf85bacdea2765e32404b73b42bc481dce60d97cc93",
    "backend/app/guided_journey_16a.py": "931a658d43ed984392c85edd51de2c08eb48df17b52a26922a91526d14f5cc84",
    "backend/app/evidence_firestore_13b2.py": "b1d755c6513868fed38d72990b4d0380aa2cca91d61daea8ee72397a902cf356",
    "backend/app/merchant_evidence_13b.py": "0d6c83df49f8c5c92f8d06bec7df8c0b79ebd99164a5ea36996568f702d8bdb3",
    "frontend/src/lib/guidedJourney16a.ts": "b28b9401cfe5a03afd5ae0c3d55492cea9296749a3bc96a4107372fb2b52f954",
    "firestore.rules": "a9d5ddd67024ec6b9522034f6a937c5dbf1630ed23d66eb0ddfeed8fcec79c58",
}


def _sha(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", required=True)
    args = p.parse_args()
    print("NeedProof Chunk 16B OFFLINE security/release preflight")
    print("No network, service configuration changes, credentials, paid calls or deployments")
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=BASE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"STOP: Could not read git HEAD: {exc}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASELINE, "HEAD"], cwd=BASE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if ancestor.returncode != 0:
        raise SystemExit(f"STOP: Expected commit {BASELINE} as baseline/ancestor; got {head}. Do not force.")
    print(f"PASS: Git HEAD {head} descends from {BASELINE}")
    for path, expected in AUDITED.items():
        full = BASE / path
        if not full.is_file() or _sha(full) != expected:
            raise SystemExit(f"STOP: Audited source mismatch for {path}. Send output for review; do not overwrite it.")
        print(f"PASS: Audited {path}")
    rules = (BASE / "firestore.rules").read_text(encoding="utf-8")
    if "allow read, write: if false;" not in rules or "allow list: if false;" not in rules:
        raise SystemExit("STOP: Default-deny Firestore or list-deny rule is absent")
    print("PASS: Firestore browser rules retain explicit deny-all fallback")
    for item in (
        "backend/tests/test_cloud_16a.py",
        "scripts/run_13b_emulator_e2e.cmd",
        "scripts/check_13b_emulator.py",
        "backend/tests/test_13b_emulator_e2e.py",
    ):
        if not (BASE / item).is_file():
            raise SystemExit(f"STOP: Missing local integration prerequisite {item}")
    print("PASS: Guided-journey and Firestore emulator test prerequisites present")
    flags = (BASE / "backend/app/cloud_decision_api.py").read_text(encoding="utf-8")
    if 'GUIDED_JOURNEY_16A_ENABLED", "false"' not in flags:
        raise SystemExit("STOP: Guided journey default-off contract changed")
    ui = (BASE / "frontend/src/lib/guidedJourney16a.ts").read_text(encoding="utf-8")
    if 'VITE_GUIDED_JOURNEY_16A_ENABLED === "true"' not in ui:
        raise SystemExit("STOP: Browser demo default-off contract changed")
    print("PASS: 16A API and UI remain opt-in")
    print("PASS: Local 16B static security preflight. Live Auth/App Check still UNVERIFIED.")
    print("NEXT: scripts\\verify_chunk16b.cmd and scripts\\run_13b_emulator_e2e.cmd")


if __name__ == "__main__":
    main()
