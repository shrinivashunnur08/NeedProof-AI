"""Guarded 13B.3 UI installer. No network operations, Firestore changes or cloud deployments.

Run at repository root:
 python scripts\\apply_chunk13b3.py --check
 python scripts\\apply_chunk13b3.py --apply
"""
from __future__ import annotations
import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "frontend/src/FreeShowcase.tsx"
UI = ROOT / "frontend/src/components/MerchantEvidenceDesk.tsx"
CLIENT = ROOT / "frontend/src/lib/merchantEvidence13b3.ts"
FIRESTORE = ROOT / "backend/app/evidence_firestore_13b2.py"
APPROVAL = ROOT / "backend/scripts/review_merchant_claim_13b3.py"
TEST = ROOT / "backend/tests/test_cloud_13b3.py"
BACKUP = ROOT / "backup_13b3"
IMPORT = 'import MerchantEvidenceDesk from "./components/MerchantEvidenceDesk";'
FLAG = 'import { evidence13bEnabled } from "./lib/evidence13b";'
SIDE = '{evidence13bEnabled && <a href="#merchant-evidence-desk" className="block rounded-lg border border-sky-500/20 px-3 py-3 text-xs text-sky-300">Merchant Desk</a>}'
MOBILE = '{evidence13bEnabled && <a href="#merchant-evidence-desk" className="shrink-0 rounded-lg border border-sky-500/25 px-3 py-2 text-xs text-sky-200">Merchant Desk</a>}'


def stop(message):
    sys.exit("STOP: " + message + "\nNo project source modified by this invocation.")


def prepare():
    for file in (FRONT, UI, CLIENT, FIRESTORE, APPROVAL, TEST):
        if not file.is_file():
            stop("Missing " + str(file.relative_to(ROOT)) + ". Extract the ZIP into the project root.")
    fs = FIRESTORE.read_text("utf-8-sig")
    if 'router = APIRouter(prefix="/api/v1/evidence"' not in fs or 'np_merchant_grants_13b' not in fs:
        stop("Expected Chunk 13B.2 Firestore adapter is absent or differs.")
    api = (ROOT / "backend/app/cloud_decision_api.py").read_text("utf-8-sig")
    if 'MERCHANT_EVIDENCE_STORAGE' not in api:
        stop("Expected optional Firestore router selection is missing.")
    ts = FRONT.read_text('utf-8-sig')
    if IMPORT in ts and '<MerchantEvidenceDesk />' in ts and SIDE in ts and MOBILE in ts and FLAG in ts:
        print("PASS: Chunk 13B.3 already installed. No changes needed.")
        return None
    if any(part in ts for part in (IMPORT, '<MerchantEvidenceDesk', SIDE, MOBILE, FLAG)):
        stop("Partial Chunk 13B.3 integration detected. Inspect FreeShowcase.tsx; no automatic overwrite.")
    anchor = 'import RealStoresDiscovery from "./components/RealStoresDiscovery";'
    if ts.count(anchor) != 1:
        stop("FreeShowcase import anchor differs. Expected exactly one RealStoresDiscovery import.")
    ts = ts.replace(anchor, anchor + '\n' + IMPORT + '\n' + FLAG, 1)
    r = re.search(r'(?s)<RealStoresDiscovery\b[^>]*?/>\s*(?=<EvidenceWorkbench\b)', ts)
    if not r:
        stop("Expected RealStoresDiscovery followed by EvidenceWorkbench, as in Chunk 13A/13B.1.")
    ts = ts[:r.end()] + '\n          <MerchantEvidenceDesk />\n\n' + ts[r.end():].lstrip('\n')
    side_anchor = '<a href="#real-store-discovery" className="block rounded-lg border border-sky-500/20 bg-sky-500/5 px-3 py-3 text-xs text-sky-300">Discover Real Stores</a>'
    mobile_anchor = '<a href="#real-store-discovery" className="shrink-0 rounded-lg border border-sky-500/25 px-3 py-2 text-xs text-sky-200">Real Stores</a>'
    if ts.count(side_anchor) != 1 or ts.count(mobile_anchor) != 1:
        stop("Workspace navigation anchors differ; do not patch unknown layout.")
    ts = ts.replace(side_anchor, side_anchor + '\n          ' + SIDE, 1)
    ts = ts.replace(mobile_anchor, mobile_anchor + '\n            ' + MOBILE, 1)
    return ts


def main():
    parser = argparse.ArgumentParser()
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--check', action='store_true')
    choice.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    replacement = prepare()
    if replacement is None:
        return
    print("PASS: 13B.2 Firestore dependency and frontend anchors verified.")
    print("Would modify: frontend/src/FreeShowcase.tsx only.")
    if args.check:
        print("DRY RUN: no source changes, no credentials or cloud calls.")
        return
    if BACKUP.exists():
        stop("Backup folder already exists; do not overwrite earlier rollback data.")
    BACKUP.mkdir()
    shutil.copy2(FRONT, BACKUP / 'FreeShowcase.tsx.before_13b3')
    temp = FRONT.with_name(FRONT.name + '.13b3.tmp')
    temp.write_text(replacement, encoding='utf-8')
    temp.replace(FRONT)
    print("SUCCESS: Merchant Evidence Desk installed locally with feature flag OFF by default.")
    print("Original dashboard backed up to", BACKUP)
    print("No Firestore grants, Google Cloud services, Firebase settings or production features changed.")

if __name__ == '__main__':
    main()
