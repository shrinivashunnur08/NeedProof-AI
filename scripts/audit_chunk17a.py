#!/usr/bin/env python3
"""NeedProof Chunk 17A: offline read-only source wiring and trust-boundary audit.

Never reads .env values, tokens, local credentials or Google Cloud metadata.
No imports from the application and no network calls. --report only writes under
qa_reports/17a. The auditor is intentionally NOT a live integration test.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_FILES = (
    'frontend/src/App.tsx',
    'frontend/src/FreeShowcase.tsx',
    'frontend/src/NeedProofWorkspace.tsx',
    'frontend/src/components/JudgeReplay16C2.tsx',
    'frontend/src/generated/needproof16cReplay.json',
    'frontend/src/lib/cloudDecisions.ts',
    'frontend/src/lib/journeyStore.ts',
    'backend/app/cloud_decision_api.py',
    'backend/app/guided_journey_16a.py',
    'backend/app/algorithms/adaptive_replanning.py',
    'backend/app/evidence_planner_14a1.py',
    'backend/app/decision_orchestrator_14a3.py',
    'backend/app/merchant_evidence_13b.py',
    'backend/app/product_retrieval_13c2.py',
    'backend/app/bi_command_center_14b4.py',
    'firestore.rules',
    'firebase.json',
    '.firebaserc',
)
EXPECTED_STATES = {
    'reported_offer': 'PROVISIONAL_VERIFICATION_NEEDED',
    'stockout': 'MORE_EVIDENCE_NEEDED',
    'document_conflict': 'RESEARCH_CONFLICT',
    'no_merchants': 'DISCOVERY_NEEDED',
}
SOURCE_LINKS = (
    ('Browser Gemini path', 'frontend/src/FreeShowcase.tsx', 'getShowcaseGeminiModel', 'CLIENT_CODE_PRESENT_NOT_LIVE_PROVEN'),
    ('Firebase model factory', 'frontend/src/lib/cloudDecisions.ts', 'getGenerativeModel', 'CLIENT_CODE_PRESENT_NOT_LIVE_PROVEN'),
    ('React cloud decision client', 'frontend/src/lib/cloudDecisions.ts', '/api/v1/decision/replan', 'AUTHENTICATED_HTTP_PATH_NOT_LIVE_PROVEN'),
    ('Server replanning API', 'backend/app/cloud_decision_api.py', '/api/v1/decision/replan', 'API_ROUTE_PRESENT_NOT_LIVE_PROVEN'),
    ('Merchant discovery', 'backend/app/cloud_decision_api.py', '/api/v1/discovery/stores', 'API_ROUTE_PRESENT_NOT_LIVE_PROVEN'),
    ('Firebase user token verification', 'backend/app/cloud_decision_api.py', 'verify_id_token', 'STATIC_AUTH_WIRING_ONLY'),
    ('Firebase App Check verification', 'backend/app/cloud_decision_api.py', 'app_check.verify_token', 'STATIC_AUTH_WIRING_ONLY'),
    ('Browser App Check token', 'frontend/src/lib/cloudDecisions.ts', 'X-Firebase-AppCheck', 'STATIC_CLIENT_WIRING_ONLY'),
    ('Firestore journey persistence', 'frontend/src/lib/journeyStore.ts', 'saveJourney', 'CLIENT_CODE_PRESENT_NOT_LIVE_PROVEN'),
    ('Local 16A orchestration engine', 'backend/app/guided_journey_16a.py', 'evaluate_guided_journey_16a', 'LOCALLY_EXECUTABLE_NOT_HOSTED_PROVEN'),
    ('14A Bayesian evidence planner', 'backend/app/evidence_planner_14a1.py', '', 'LOCALLY_EXECUTABLE_NOT_HOSTED_PROVEN'),
    ('14A combined orchestration', 'backend/app/decision_orchestrator_14a3.py', '', 'LOCALLY_EXECUTABLE_NOT_HOSTED_PROVEN'),
    ('13C cited retrieval', 'backend/app/product_retrieval_13c2.py', '', 'LOCALLY_EXECUTABLE_NOT_HOSTED_PROVEN'),
    ('14B BI', 'backend/app/bi_command_center_14b4.py', '', 'LOCALLY_EXECUTABLE_NOT_HOSTED_PROVEN'),
)


def get_git_head(root: Path) -> dict[str, str | bool | None]:
    result: dict[str, str | bool | None] = {'head': None, 'baseline_c753fd6_ancestor': None}
    try:
        proc = subprocess.run(['git', '-C', str(root), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            result['head'] = proc.stdout.strip()
            check = subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', 'c753fd6', 'HEAD'], capture_output=True, timeout=5)
            result['baseline_c753fd6_ancestor'] = check.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        pass
    return result


def clean_read(root: Path, name: str) -> str:
    # Explicit allowlist: never read .env, keys or unrelated user data.
    if name not in REQUIRED_FILES and name not in [r[1] for r in SOURCE_LINKS]:
        raise ValueError('File not permitted by offline auditor')
    path = root / name
    return path.read_text(encoding='utf-8-sig') if path.is_file() else ''


def audit(root: Path) -> dict:
    root = root.resolve()
    missing = [path for path in REQUIRED_FILES if not (root / path).is_file()]
    routes = []
    api = clean_read(root, 'backend/app/cloud_decision_api.py')
    for method, path in re.findall(r'@app\.(get|post|put|patch|delete)\([\'"]([^\'"]+)', api):
        routes.append({'method': method.upper(), 'path': path})
    links = []
    for label, path, marker, mode in SOURCE_LINKS:
        content = clean_read(root, path)
        found = bool(content) and (not marker or marker in content)
        links.append({'capability': label, 'source': path, 'source_marker_found': found, 'evidence_class': mode if found else 'MISSING_OR_CHANGED_WIRING'})

    replay_check = {'present': False, 'synthetic': False, 'cases': {}, 'safety_pass': False}
    file = root / 'frontend/src/generated/needproof16cReplay.json'
    if file.is_file():
        try:
            data = json.loads(file.read_text(encoding='utf-8-sig'))
            cases = data.get('scenarios') or {}
            replay_check['present'] = True
            replay_check['synthetic'] = data.get('synthetic') is True
            for case, state in EXPECTED_STATES.items():
                d = cases.get(case) or {}
                workflow = d.get('workflow') or {}
                trace = workflow.get('workflow_trace') or []
                replay_check['cases'][case] = {
                    'state_matches': workflow.get('workflow_state') == state,
                    'five_stages': len(trace) == 5,
                    'purchase_denied': d.get('purchase_allowed') is False and workflow.get('purchase_allowed') is False,
                    'no_real_merchant_contact': d.get('real_merchant_contact') is False,
                    'no_live_model_claim': d.get('cloud_model_used') is False,
                }
            replay_check['safety_pass'] = replay_check['synthetic'] and all(all(c.values()) for c in replay_check['cases'].values()) and len(replay_check['cases']) == 4
        except (ValueError, UnicodeError, AttributeError, TypeError) as exc:
            replay_check['parse_error_type'] = type(exc).__name__  # no data leaked

    hosting = {}
    for name in ('firebase.json', '.firebaserc'):
        try:
            obj = json.loads(clean_read(root, name))
            if name == 'firebase.json':
                hosting['public_directory'] = obj.get('hosting', {}).get('public')
                hosting['spa_rewrite_present'] = any(x.get('destination') == '/index.html' for x in obj.get('hosting', {}).get('rewrites', []))
                hosting['firestore_rules_configured'] = 'firestore' in obj
            else:
                hosting['firebase_default_project'] = obj.get('projects', {}).get('default')
        except (ValueError, AttributeError, TypeError):
            hosting['configuration_invalid'] = True

    # Report only existence, NEVER CONTENTS or values of .env files.
    local_env = {'frontend_env_local_present': (root / 'frontend/.env.local').exists(),
                 'frontend_env_production_local_present': (root / 'frontend/.env.production.local').exists()}
    security = {
        'auth_token_verifier_source_present': 'verify_id_token' in api,
        'app_check_verifier_source_present': 'app_check.verify_token' in api,
        'browser_deny_fallback_source_present': 'allow read, write: if false' in clean_read(root, 'firestore.rules'),
        'api_cors_uses_origins_list': 'allow_origins=ALLOWED_ORIGINS' in api,
    }
    errors = []
    if missing: errors.append('Missing expected committed source files')
    if not replay_check['safety_pass']: errors.append('Offline replay safety invariants changed or missing')
    if not all(security.values()): errors.append('Security source invariants changed or missing')
    if not hosting.get('spa_rewrite_present'): errors.append('Hosting SPA rewrite missing or changed')
    if not all(x['source_marker_found'] for x in links): errors.append('Some declared source links changed: inspect capability inventory')
    return {
        'audit_type': 'STATIC_SOURCE_ONLY_NO_NETWORK',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'git': get_git_head(root),
        'result': 'PASS_OFFLINE_SOURCE_GATE' if not errors else 'NEEDS_INSPECTION',
        'errors': errors,
        'missing_paths': missing,
        'source_links': links,
        'cloud_api_routes': routes,
        'replay': replay_check,
        'security_source_checks': security,
        'hosting': hosting,
        'local_env_FILE_PRESENCE_ONLY': local_env,
        'NOT_VERIFIED': [
            'A fresh browser request actually reaches a deployed Cloud Run Python endpoint',
            'Live Gemini request, model identity, quotas, response schema or token costs',
            'Live Firebase ID token and App Check verification / CORS',
            'Production Firestore cross-project IAM, merchant claims, persistence and isolation',
            'True merchant stock, verified specifications, real customer outcomes',
            'Mobile rendering/accessibility or remotely hosted rollout of local source',
        ],
        'next_action': 'Run optional local backend trace, then decide 17B/17C scope using this inventory; approve live calls separately.',
    }


def report_md(data: dict) -> str:
    lines = [
        '# NeedProof AI — Chunk 17A Reality Audit', '',
        '> Local source inspection only. **This is NOT a live Google AI, Firebase, or Cloud Run integration test.**', '',
        f"**Result:** {data['result']}", f"**Git HEAD:** {data['git']['head'] or 'unavailable'}", '',
        '## Executable paths and source-based evidence', '',
        '| Capability | Local evidence class | Marker |', '|---|---|---|',
    ]
    for l in data['source_links']:
        lines.append(f"| {l['capability']} | `{l['evidence_class']}` | {'found' if l['source_marker_found'] else 'NOT FOUND'} |")
    lines += ['', '## API decorators found in deployed service source', '']
    for item in data['cloud_api_routes']:
        lines.append(f"- `{item['method']} {item['path']}` (source presence ≠ deployed availability)")
    lines += ['', '## Replay and safety', '', f"- Fictional replay states and no-purchase contract: {'PASS' if data['replay']['safety_pass'] else 'NEEDS INSPECTION'}"]
    for k, v in data['security_source_checks'].items():
        lines.append(f"- `{k}`: {'present' if v else 'MISSING'}")
    lines += ['', '## Firebase Hosting / environment (no values read)', '']
    for k, v in data['hosting'].items():
        lines.append(f'- `{k}`: `{v}`')
    for k, v in data['local_env_FILE_PRESENCE_ONLY'].items():
        lines.append(f'- `{k}`: `{v}`')
    lines += ['', '## Unverified until live approval', '']
    for item in data['NOT_VERIFIED']:
        lines.append('- ' + item)
    lines += ['', '## Reconciliation / blockers', '']
    if data['errors']:
        for item in data['errors']: lines.append('- **INSPECT:** ' + item)
    else: lines.append('- Source wiring is consistent with the expected local baseline; this does **not** mean cloud features work live.')
    lines += ['', '## Next build', '', '**17B:** validate one fresh Gemini extraction using schema validation and real model tracing. **17C:** connect it to a fresh Python decision with local proof first. Neither should use a paid cloud endpoint without explicit approval.', '']
    return '\n'.join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description='NeedProof 17A offline source reality audit; zero network calls')
    p.add_argument('--check', action='store_true', help='Read-only local checks; no report files')
    p.add_argument('--report', action='store_true', help='Write sanitized report to qa_reports/17a')
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1], help='Project root (for fixture tests)')
    args = p.parse_args()
    if not args.check and not args.report: p.error('Choose --check or --report')
    data = audit(args.root)
    print('NeedProof AI Chunk 17A | OFFLINE READ-ONLY SOURCE AUDIT')
    print('Git HEAD:', data['git']['head'] or 'not available', '| baseline descendant:', data['git']['baseline_c753fd6_ancestor'])
    print('Expected source files:', len(REQUIRED_FILES) - len(data['missing_paths']), '/', len(REQUIRED_FILES))
    print('Static source links:', sum(l['source_marker_found'] for l in data['source_links']), '/', len(data['source_links']))
    print('Cloud API route declarations:', len(data['cloud_api_routes']))
    print('Offline replay 4-case safety:', 'PASS' if data['replay']['safety_pass'] else 'INSPECT')
    print('Auth/App Check/Rules static checks:', sum(data['security_source_checks'].values()), '/', len(data['security_source_checks']))
    print('Real Gemini, hosted backend, Firestore IAM, merchant verification: UNVERIFIED')
    print('No .env contents, network endpoints, credentials, or cloud resources were accessed.')
    if args.report:
        folder = args.root / 'qa_reports/17a'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'reality_audit.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (folder / 'reality_audit.md').write_text(report_md(data), encoding='utf-8')
        print('REPORT:', folder / 'reality_audit.md')
    if data['errors']:
        for e in data['errors']: print('CHECK:', e)
        return 1
    print('PASS: Chunk 17A offline source readiness. Live integration remains unverified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
