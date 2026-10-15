"""Create ONLY the new 13B tables. Does not create Cloud SQL instances.

Run once with correct DATABASE_BACKEND, Cloud SQL connection settings and --confirm.
Do not use database credentials in shell command history; use Secret Manager or a protected env file.
"""
import argparse
from sqlalchemy import inspect
from app.db.session import get_engine
from app.merchant_evidence_13b import EvidenceInquiry13B, EvidenceRevision13B, MerchantGrant13B


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    engine = get_engine()
    tables = [EvidenceInquiry13B.__table__, MerchantGrant13B.__table__, EvidenceRevision13B.__table__]
    present = set(inspect(engine).get_table_names())
    for table in tables:
        print(("EXISTS" if table.name in present else "WOULD CREATE"), table.name)
    if not args.confirm:
        print("Dry run. Re-run with --confirm after reviewing the target database.")
        return
    for table in tables:
        table.create(bind=engine, checkfirst=True)
    print("Chunk 13B tables confirmed.")


if __name__ == "__main__":
    main()
