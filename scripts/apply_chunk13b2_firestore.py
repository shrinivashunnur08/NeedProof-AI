"""Safely switch NeedProof 13B evidence storage to optional Firestore.

Runs only against Chunk 13B.1 source anchors. It never changes cloud resources.
Usage: python scripts/apply_chunk13b2_firestore.py --check|--apply
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / 'backend/app/cloud_decision_api.py'
REQ = ROOT / 'backend/requirements-cloud.txt'
TS = ROOT / 'frontend/src/lib/evidence13b.ts'
ADAPTER = ROOT / 'backend/app/evidence_firestore_13b2.py'
TEST = ROOT / 'backend/tests/test_cloud_13b2_firestore.py'
BACKUP = ROOT / 'backup_13b2_firestore'
OLD = 'app.include_router(evidence_13b_router)'
NEW = '''# SQL backend remains the default for existing local tests and tooling.
# Firestore requires explicit deployment configuration; no automatic migration.
if os.environ.get("MERCHANT_EVIDENCE_STORAGE", "").strip().lower() == "firestore":
    from app.evidence_firestore_13b2 import router as evidence_13b_router
app.include_router(evidence_13b_router)'''
DEP = 'google-cloud-firestore>=2.14,<3'


def stop(reason):
    sys.exit('STOP: ' + reason + '\nNo project files changed by this invocation.')


def prepare():
    for p in (API, REQ, TS, ADAPTER, TEST):
        if not p.is_file():
            stop('Required file missing: ' + str(p.relative_to(ROOT)) + '. Extract package at repo root.')
    api = API.read_text('utf-8-sig')
    req = REQ.read_text('utf-8-sig')
    ts = TS.read_text('utf-8-sig')
    if OLD not in api and NEW not in api:
        stop('Expected Chunk 13B.1 API router anchor missing.')
    if api.count(OLD) != 1:
        stop('Unexpected evidence router count.')
    if 'from app.merchant_evidence_13b import router as evidence_13b_router' not in api:
        stop('SQL evidence router import missing; do not patch an unknown version.')
    if 'cloud-sql-python-connector' not in req or 'sqlalchemy' not in req:
        stop('Chunk 13B.1 Cloud Run requirements are missing.')
    if 'revision_id: number;' not in ts and 'revision_id: string;' not in ts:
        stop('Frontend evidence type differs from the verified 13B.1 component.')
    if NEW in api and DEP in req and 'revision_id: string;' in ts:
        print('PASS: Firestore 13B.2 integration already installed.')
        return {}
    if NEW in api or DEP in req or 'revision_id: string;' in ts:
        stop('Partial Firestore patch detected; inspect files before retry.')
    api = api.replace(OLD, NEW, 1)
    req = req.rstrip('\r\n') + '\n' + DEP + '\n'
    ts = ts.replace('revision_id: number;', 'revision_id: string;', 1)
    return {API: api, REQ: req, TS: ts}


def main():
    parser = argparse.ArgumentParser()
    opts = parser.add_mutually_exclusive_group(required=True)
    opts.add_argument('--check', action='store_true')
    opts.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    edits = prepare()
    if not edits:
        return
    print('PASS: 13B.1 API, requirements, TypeScript contract and Firestore module match expected anchors.')
    print('Would modify:', ', '.join(str(p.relative_to(ROOT)) for p in edits))
    if args.check:
        print('No files changed. No cloud resources created.')
        return
    if BACKUP.exists():
        stop('Backup folder exists: backup_13b2_firestore. Do not overwrite earlier backups.')
    BACKUP.mkdir()
    for p in edits:
        dest = BACKUP / (p.relative_to(ROOT).as_posix().replace('/', '__') + '.before')
        shutil.copy2(p, dest)
    # All replacements prepared before touching source. Backups retained for rollback.
    for p, content in edits.items():
        temp = p.with_name(p.name + '.firestore.tmp')
        temp.write_text(content, encoding='utf-8')
        temp.replace(p)
    print('SUCCESS: Optional Firestore backend integrated locally. All feature flags remain OFF.')
    print('Backups:', BACKUP)


if __name__ == '__main__':
    main()
