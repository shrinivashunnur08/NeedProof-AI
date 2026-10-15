"""Manually approve a Firebase UID for one Place ID after external ownership review.

This action is not exposed over HTTP. No claim is self-approving.
"""
import argparse
from sqlalchemy import select
from app.db.session import get_session_factory
from app.db.models import utc_now
from app.merchant_evidence_13b import MerchantGrant13B


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uid", required=True, help="Verified, non-anonymous Firebase Auth UID")
    parser.add_argument("--place-id", required=True)
    parser.add_argument("--confirm-reviewed", action="store_true", help="Confirm offline ownership review was performed")
    args = parser.parse_args()
    if not args.confirm_reviewed:
        parser.error("Approval is disabled without --confirm-reviewed after external review")
    if not (3 <= len(args.place_id) <= 300 and 1 <= len(args.uid) <= 128):
        parser.error("Invalid UID or place ID")
    with get_session_factory()() as db:
        grant = db.scalar(select(MerchantGrant13B).where(MerchantGrant13B.merchant_uid == args.uid, MerchantGrant13B.place_id == args.place_id))
        if not grant:
            grant = MerchantGrant13B(merchant_uid=args.uid, place_id=args.place_id, approval_status="OPERATOR_APPROVED_CLAIM", approved_at=utc_now())
            db.add(grant)
        else:
            grant.approval_status = "OPERATOR_APPROVED_CLAIM"
            grant.approved_at = utc_now()
        db.commit()
    print("Approved operator-reviewed claim (NOT independent business verification).")


if __name__ == "__main__":
    main()
