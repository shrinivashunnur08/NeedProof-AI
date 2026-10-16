"""Operator-only, *offline-reviewed* Firestore business claim approval/revocation.

No HTTP administration route. Dry-run is the default. Does not contact merchants,
verify product inventory, or independently certify a business.

Run from backend: python scripts/review_merchant_claim_13b3.py --uid UID --place-id ID --case CASE
Apply only after a real-world ownership review with --action approve --apply --confirm-reviewed.
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from uuid import uuid4

PROJECT = "needproof-ai-showcase"
GRANTS = "np_merchant_grants_13b"
AUDIT = "np_merchant_grant_audit_13b3"


def valid_uid(value: str) -> str:
    if not (1 <= len(value) <= 128) or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise ValueError("Invalid Firebase UID")
    return value


def valid_place(value: str) -> str:
    if not (3 <= len(value) <= 300) or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise ValueError("Invalid Google Place ID")
    return value


def valid_case(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,79}", value):
        raise ValueError("Use a non-personal 3–80 character review case reference")
    return value


def merchant_is_eligible(user) -> bool:
    # This is not proof of store ownership. It only checks Auth account status.
    return bool(user and not getattr(user, "disabled", True)
                and getattr(user, "email", None) and getattr(user, "email_verified", False))


def grant_record(uid: str, place_id: str, case: str, action: str, now: datetime) -> dict:
    return {
        "merchant_uid": uid,
        "place_id": place_id,
        "approval_status": "OPERATOR_APPROVED_CLAIM" if action == "approve" else "REVOKED",
        "review_case": case,
        "approved_at": now if action == "approve" else None,
        "revoked_at": now if action == "revoke" else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual approval after offline business ownership review")
    parser.add_argument("--uid", required=True)
    parser.add_argument("--place-id", required=True)
    parser.add_argument("--case", required=True, help="Non-personal audit case reference")
    parser.add_argument("--action", choices=["approve", "revoke"], default="approve")
    parser.add_argument("--apply", action="store_true", help="Perform a Firestore write (default: dry-run)")
    parser.add_argument("--confirm-reviewed", action="store_true", help="Ownership evidence reviewed OFFLINE")
    args = parser.parse_args()
    try:
        uid, place_id, case = valid_uid(args.uid), valid_place(args.place_id), valid_case(args.case)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Target Firestore: {PROJECT}/(default); action: {args.action}; review case: {case}")
    if not args.apply:
        print("DRY-RUN ONLY: no cloud calls, credentials, or writes; no business was contacted.")
        return
    if args.action == "approve" and not args.confirm_reviewed:
        parser.error("Approval requires --confirm-reviewed after external business ownership review")
    # Confirmation is intentional: never approve a merchant through automated installation.
    expected = "APPROVE" if args.action == "approve" else "REVOKE"
    if input(f"Type {expected} to confirm the Firestore change: ").strip() != expected:
        parser.error("Operator confirmation failed. No changes made")

    # Imports happen only after explicit confirmation; no cloud connection during dry-run.
    import firebase_admin
    from firebase_admin import auth
    from google.cloud import firestore
    from app.evidence_firestore_13b2 import _hash

    try:
        admin_app = firebase_admin.get_app("needproof-merchant-review")
    except ValueError:
        admin_app = firebase_admin.initialize_app(options={"projectId": PROJECT}, name="needproof-merchant-review")
    if args.action == "approve":
        user = auth.get_user(uid, app=admin_app)
        if not merchant_is_eligible(user):
            raise SystemExit("STOP: Firebase user must have a verified email and be enabled")

    client = firestore.Client(project=PROJECT, database="(default)")
    ref = client.collection(GRANTS).document(_hash(uid, place_id))
    audit = client.collection(AUDIT).document(str(uuid4()))
    now = datetime.now(timezone.utc)
    record = grant_record(uid, place_id, case, args.action, now)
    batch = client.batch()
    batch.set(ref, record)
    batch.create(audit, {**record, "recorded_at": now, "action": args.action})
    batch.commit()
    print(f"SUCCESS: {args.action} recorded with an audit entry. This is NOT independent merchant or stock verification.")


if __name__ == "__main__":
    main()
