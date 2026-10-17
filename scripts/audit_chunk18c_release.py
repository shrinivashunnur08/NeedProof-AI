#!/usr/bin/env python3
"""Offline-only final release evidence audit. Does NOT deploy or attest live services.

Designed to evaluate actual results from earlier verification commands, not to
rerun cloud integrations, invent testimonials or authorize real transactions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / 'qa_reports' / '18c' / 'local_release_audit.json'
A18 = ROOT / 'qa_reports' / '18a' / 'fictional_validation.json'
B18 = ROOT / 'qa_reports' / '18b' / 'engineering_results.json'
COST = ROOT / 'qa_reports' / '18b' / 'hypothetical_economics.json'
CLAIMS = ROOT / 'validation' / '18c' / 'release_claims.json'

REQUIRED_FILES = (
    'backend/app/fresh_journey_17c.py',
    'backend/app/cloud_decision_api.py',
    'frontend/src/FreeShowcase.tsx',
    'frontend/package.json',
    'scripts/verify_chunk17g.cmd',
    'scripts/verify_chunk18a.cmd',
    'scripts/verify_chunk18b.cmd',
    'validation/18a/fictional_cases.json',
    'validation/18b/hypothetical_cost_inputs.json',
    'firebase.json',
)

# Only tracked files are inspected.  Public Firebase client configuration is not
# itself proof of credential leakage; service-account secrets and private keys are.
SENSITIVE_NAME_EXACT = {'service-account.json', 'service_account.json', 'credentials.json', 'firebase-adminsdk.json', '.env', '.env.local', '.env.production'}
SENSITIVE_SUFFIXES = ('.pem', '.p12', '.pfx', '.jks', '.keystore')
PRIVATE_KEY_MARKERS = (b'-----BEGIN PRIVATE KEY-----', b'-----BEGIN RSA PRIVATE KEY-----', b'-----BEGIN OPENSSH PRIVATE KEY-----')


def _json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def validate_18a(report: dict) -> list[str]:
    errors = []
    if report.get('provenance') != 'AUTHOR_CREATED_FICTIONAL_18A':
        errors.append('18A provenance is not fictional')
    if report.get('total_cases') != 47 or report.get('passed') != 47 or report.get('failed') != 0:
        errors.append('18A case coverage or pass count is not 47/47')
    for field in ('real_participants', 'real_merchants', 'verified_inventory', 'actual_gemini_calls', 'actual_cloud_calls'):
        if report.get(field) != 0:
            errors.append(f'18A {field} changed: require independent provenance review')
    if len(report.get('results', [])) != 47 or not all(case.get('pass') is True for case in report.get('results', [])):
        errors.append('18A individual results missing or failing')
    return errors


def validate_18b(report: dict) -> list[str]:
    errors = []
    if report.get('schema') != 'NEEDPROOF_18B_OFFLINE_ENGINEERING_V1' or report.get('provenance') != 'AUTHOR_CREATED_FICTIONAL_18A':
        errors.append('18B schema/provenance mismatch')
    if report.get('passed') is not True or report.get('failures') != []:
        errors.append('18B engineering report is not passing')
    policies = report.get('policies', {})
    expected = {'NEEDPROOF_17E': (37, 0), 'PRICE_ONLY': (25, 12), 'STOCK_AND_BUDGET': (34, 3), 'STRUCTURED_EVIDENCE_RULES': (37, 0)}
    for policy, (correct, unsafe) in expected.items():
        d = policies.get(policy, {})
        if d.get('tested') != 37 or d.get('correct') != correct or d.get('false_provisional') != unsafe:
            errors.append(f'18B {policy}: mismatch; do not modify comparator results to pass')
    if len(report.get('schema_rejected_cases', [])) != 10 or len(report.get('input_signal_counterfactuals', [])) != 5:
        errors.append('18B invalid-case or counterfactual coverage mismatch')
    if any(report.get(k) != 0 for k in ('actual_participants', 'actual_merchants', 'verified_stock_observations', 'live_gemini_calls', 'cloud_calls')):
        errors.append('18B external validation fields changed; audit provenance before using')
    return errors


def validate_cost(report: dict) -> list[str]:
    errors = []
    if report.get('source') != 'USER_EDITABLE_ILLUSTRATIVE_ASSUMPTIONS_NOT_VENDOR_PRICES':
        errors.append('18B cost model provenance mismatch')
    for k in ('actual_billed_usd', 'observed_shopper_value_usd', 'observed_roi'):
        if report.get(k, 'missing') is not None:
            errors.append(f'18B cost field {k} is not explicitly null')
    return errors


def validate_claims(claims: dict) -> list[str]:
    errors = []
    if claims.get('schema') != 'NEEDPROOF_18C_RELEASE_CLAIMS_V1':
        errors.append('Release claims schema missing')
    if claims.get('external_validation_claims') != {
        'live_gemini_verified': False,
        'secure_hosted_e2e_verified': False,
        'real_merchant_inventory_verified': False,
        'independent_user_pilot_completed': False,
        'actual_cost_and_roi_measured': False,
    }:
        errors.append('External claims changed; offline bundle may not certify external services')
    if claims.get('purchase_authorization_enabled') is not False:
        errors.append('Purchase authorization flag must remain explicitly false')
    if claims.get('evidence_class') != 'OFFLINE_AUTHOR_CREATED_FICTIONAL':
        errors.append('Evidence class changed')
    return errors


def tracked_file_scan(root: Path) -> dict:
    result = subprocess.run(['git', 'ls-files', '-z'], cwd=root, capture_output=True, check=True)
    files = [Path(x.decode('utf-8', errors='replace')) for x in result.stdout.split(b'\0') if x]
    matches = []
    for rel in files:
        if rel.name.lower() in SENSITIVE_NAME_EXACT or rel.suffix.lower() in SENSITIVE_SUFFIXES:
            matches.append({'path': rel.as_posix(), 'type': 'sensitive_filename'})
        p = root / rel
        if p.is_file() and p.stat().st_size <= 2_000_000 and p.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.pdf', '.zip'):
            if any(marker in p.read_bytes() for marker in PRIVATE_KEY_MARKERS):
                matches.append({'path': rel.as_posix(), 'type': 'private_key_marker'})
    return {'tracked_paths_scanned': len(files), 'possible_exposures': matches}


def bundle_warning(root: Path) -> list[dict]:
    base = root / 'frontend' / 'dist' / 'assets'
    if not base.is_dir():
        return []
    return [{'asset': p.name, 'bytes': p.stat().st_size} for p in sorted(base.glob('*.js')) if p.stat().st_size > 500_000]


def make_report(root: Path = ROOT) -> dict:
    errors = []
    tracked_dirty = False
    git_head = 'UNKNOWN'
    try:
        git_head = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=root, text=True, stderr=subprocess.PIPE).strip()
        tracked_dirty = bool(subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=root, text=True, stderr=subprocess.PIPE).strip())
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f'Cannot read Git checkout: {type(exc).__name__}')
    if tracked_dirty:
        errors.append('Tracked working tree has uncommitted changes')
    missing = [p for p in REQUIRED_FILES if not (root / p).is_file()]
    if missing:
        errors.append('Missing required source files: ' + ', '.join(missing))
    sources = {name: root / filename for name, filename in {'18a': 'qa_reports/18a/fictional_validation.json', '18b': 'qa_reports/18b/engineering_results.json', 'cost': 'qa_reports/18b/hypothetical_economics.json', 'claims': 'validation/18c/release_claims.json'}.items()}
    loaded = {}
    digests = {}
    for k, path in sources.items():
        try:
            loaded[k] = _json(path)
            digests[k] = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f'Missing/invalid {k} evidence: {type(exc).__name__}')
    if '18a' in loaded: errors += validate_18a(loaded['18a'])
    if '18b' in loaded: errors += validate_18b(loaded['18b'])
    if 'cost' in loaded: errors += validate_cost(loaded['cost'])
    if 'claims' in loaded: errors += validate_claims(loaded['claims'])
    try:
        scan = tracked_file_scan(root)
        if scan['possible_exposures']:
            errors.append('Potential credentials in tracked repository paths; investigate and rotate if genuine')
    except (OSError, subprocess.CalledProcessError) as exc:
        scan = {'error': type(exc).__name__}
        errors.append('Tracked-file credential scan could not complete')
    return {
        'schema': 'NEEDPROOF_18C_LOCAL_RELEASE_AUDIT_V1',
        'repo_head': git_head,
        'local_evidence_gate_passed': not errors,
        'local_gate_errors': errors,
        'claim_provenance': 'BUILDER_AUTHORED_FICTIONAL_AND_LOCAL_ONLY',
        'evidence_sha256': digests,
        'source_missing': missing,
        'credential_scan': scan,
        'frontend_large_chunks': bundle_warning(root),
        'release_classification': 'OFFLINE_JUDGE_DEMO_ONLY' if not errors else 'LOCAL_GATE_BLOCKED',
        'cloud_deploy_performed': False,
        'firebase_auth_appcheck_e2e_verified': False,
        'real_gemini_performed': False,
        'live_merchant_pilot_performed': False,
        'actual_cloud_cost_measured': False,
        'manual_acceptance_completed': False,
        'comment': 'Offline code/report audit only. Never represents production readiness, independently verified inventory, or a deployed release.',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='NeedProof 18C offline evidence audit')
    parser.add_argument('--out', type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        report = make_report()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print('LOCAL RELEASE AUDIT:', 'PASS' if report['local_evidence_gate_passed'] else 'FAIL')
        print('Git HEAD:', report['repo_head'])
        print('Classification:', report['release_classification'])
        print('Possible credential exposures:', len(report.get('credential_scan', {}).get('possible_exposures', [])))
        if report['frontend_large_chunks']:
            print('PERFORMANCE WARNING: oversized frontend JS bundle(s) found; inspect before publishing')
        for err in report['local_gate_errors']:
            print('FAIL:', err)
        print('REPORT:', args.out.resolve())
        print('PENDING: approved live Gemini, Auth/AppCheck/Cloud Run E2E, real users/merchants, independently verified inventory, real spend, manual judge QA.')
        return 0 if report['local_evidence_gate_passed'] else 1
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('ERROR:', type(exc).__name__, str(exc)[:200])
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
