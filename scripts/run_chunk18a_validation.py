"""Chunk 18A: offline *fictional* scenario validation against actual 17C Python.

This is NOT a blinded user study, merchant pilot, genuine-inventory audit,
Gemini measurement, or an independent ground-truth benchmark.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from pydantic import ValidationError
from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c

DATASET = ROOT / 'validation' / '18a' / 'fictional_cases.json'
OUT = ROOT / 'qa_reports' / '18a' / 'fictional_validation.json'


def _check(case: dict) -> dict:
    data = case['input']
    errors = []
    expected = case['expect']
    try:
        model = FreshJourney17C.model_validate(data)
    except ValidationError as exc:
        if expected.get('validation_error'):
            return {'id': case['id'], 'kind': 'schema_rejection', 'pass': True,
                    'expected': 'validation_error', 'actual': 'validation_error',
                    'error_codes': sorted(set(e['type'] for e in exc.errors()))}
        return {'id': case['id'], 'kind': 'unexpected_rejection', 'pass': False,
                'expected': expected.get('state'), 'actual': 'validation_error',
                'errors': [e['type'] for e in exc.errors()]}
    if expected.get('validation_error'):
        return {'id': case['id'], 'kind': 'unsafe_acceptance', 'pass': False,
                'expected': 'validation_error', 'actual': 'accepted'}
    try:
        response = evaluate_fresh_journey_17c(model)
        workflow = response['workflow']
        actual = workflow['workflow_state']
        if actual != expected['state']:
            errors.append(f'expected {expected["state"]}, got {actual}')
        for key in ('purchase_allowed', 'stock_independently_verified',
                    'gemini_called', 'merchant_contacted', 'database_written'):
            if response.get(key) is not False:
                errors.append(f'{key} not explicitly false')
        if workflow.get('purchase_allowed') is not False:
            errors.append('workflow purchase not explicitly false')
        if len(workflow.get('workflow_trace', [])) != 5:
            errors.append('workflow trace is not five stages')
        passport = response['evidence_passport']
        queue = response['verification_queue_17e']
        fingerprint = workflow['snapshot_sha256']
        if passport.get('snapshot_sha256') != fingerprint or queue.get('snapshot_sha256') != fingerprint:
            errors.append('passport/queue hash binding mismatch')
        if passport.get('purchase_allowed') is not False or queue.get('purchase_allowed') is not False:
            errors.append('evidence planning permitted purchase')
        return {'id': case['id'], 'kind': case['category'], 'pass': not errors,
                'expected': expected['state'], 'actual': actual, 'errors': errors}
    except Exception as exc:  # report as a failing case, never silently skip
        return {'id': case['id'], 'kind': case['category'], 'pass': False,
                'expected': expected['state'], 'actual': type(exc).__name__,
                'errors': [str(exc)[:300]]}


def run_suite(data_file: Path = DATASET) -> dict:
    raw = data_file.read_bytes()
    data = json.loads(raw)
    if data.get('provenance') != 'AUTHOR_CREATED_FICTIONAL_18A':
        raise ValueError('Dataset must identify itself as authored fictional evidence')
    cases = data['cases']
    ids = [case['id'] for case in cases]
    if len(ids) != len(set(ids)) or len(cases) < 25:
        raise ValueError('Need >=25 uniquely identified evaluation cases')
    rows = [_check(case) for case in cases]
    return {
        'suite': 'NeedProof 18A authored fictional holdout-style scenarios',
        'provenance': 'AUTHOR_CREATED_FICTIONAL_18A',
        'real_participants': 0,
        'real_merchants': 0,
        'verified_inventory': 0,
        'actual_gemini_calls': 0,
        'actual_cloud_calls': 0,
        'method': 'Offline, real 17C Python decisions; expected states authored manually',
        'limitations': [
            'Cases are separately authored but NOT a truly blinded independent sample.',
            'Uses fictional merchant templates and synthesized input, not merchant inventories.',
            'Schema rejections are model-level, not HTTP authorization tests.',
            'Does not prove generalization, verified products, customer savings or Gemini quality.',
        ],
        'dataset_sha256': hashlib.sha256(raw).hexdigest(),
        'total_cases': len(rows),
        'passed': sum(bool(r['pass']) for r in rows),
        'failed': sum(not r['pass'] for r in rows),
        'categories': dict(sorted(Counter(r['kind'] for r in rows).items())),
        'results': rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    report = run_suite()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    csv_path = args.output.with_name('fictional_validation_cases.csv')
    with csv_path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['id','kind','pass','expected','actual','errors'])
        writer.writeheader()
        for row in report['results']:
            writer.writerow({key: ('; '.join(row.get('errors', [])) if key == 'errors' else row.get(key, '')) for key in writer.fieldnames})
    print(f'18A fictional offline scenarios: {report["passed"]}/{report["total_cases"]} passed')
    for row in report['results']:
        label = 'PASS' if row['pass'] else 'FAIL'
        print(f'{label}: {row["id"]}: {row["actual"]}' +
              (f' ({"; ".join(row.get("errors", []))})' if not row['pass'] else ''))
    print('REPORT:', args.output.resolve())
    print('CSV:', csv_path.resolve())
    print('LIMITATION: No real participants, merchants, verified stock, or Gemini tested.')
    return 0 if not report['failed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
