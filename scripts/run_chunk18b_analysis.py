#!/usr/bin/env python3
"""18B reproducible OFFLINE engineering study; authored fictional 18A inputs.

No Google APIs, network, cloud billing, merchant contact, or purchase action.
Only actual 17C orchestrator and already-existing 17F comparator policies run.
Ablations are explicitly input-signal omission counterfactuals, not module removal.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from pydantic import ValidationError
from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c
from app.benchmark_17f import simple_baseline, POLICIES

DATASET = ROOT / 'validation' / '18a' / 'fictional_cases.json'
OUT = ROOT / 'qa_reports' / '18b'
EXPECTED_POLICIES = ('NEEDPROOF_17E', 'PRICE_ONLY', 'STOCK_AND_BUDGET', 'STRUCTURED_EVIDENCE_RULES')


def _canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def _assert_safe(response):
    w = response['workflow']
    p = response['evidence_passport']
    q = response['verification_queue_17e']
    digest = w['snapshot_sha256']
    for key in ('purchase_allowed', 'stock_independently_verified', 'gemini_called', 'merchant_contacted', 'database_written'):
        if response.get(key) is not False:
            raise AssertionError(f'{key} must explicitly be false')
    if w.get('purchase_allowed') is not False or p.get('purchase_allowed') is not False or q.get('purchase_allowed') is not False:
        raise AssertionError('Purchase authorization boundary broken')
    if p.get('snapshot_sha256') != digest or q.get('snapshot_sha256') != digest:
        raise AssertionError('Evidence fingerprint mismatch')
    if len(w.get('workflow_trace', [])) != 5:
        raise AssertionError('Incomplete workflow trace')
    return {'passport_bound': True, 'verification_queue_bound': True, 'five_stage_trace': True, 'purchase_blocked': True}


def _time_eval(model, repetitions):
    times = []
    first = None
    for _ in range(repetitions):
        start = time.perf_counter_ns()
        result = evaluate_fresh_journey_17c(model)
        times.append((time.perf_counter_ns() - start) / 1_000_000)
        _assert_safe(result)
        if first is None:
            first = result
        elif result['workflow']['workflow_state'] != first['workflow']['workflow_state']:
            raise AssertionError('Repeated local evaluation changed workflow state')
    return first, times


def _baseline_state(model, name):
    if name not in EXPECTED_POLICIES[1:]:
        raise ValueError('Unexpected policy')
    return simple_baseline(model, name)['workflow_state']


def _counterfactual(model, kind):
    if kind == 'WITHHOLD_CONFLICT_SIGNAL':
        if model.synthetic_documents != 'conflicting_fixtures':
            raise ValueError('Counterfactual applies only to document-conflict cases')
        altered = model.model_copy(update={'synthetic_documents': 'not_submitted'})
    elif kind == 'WITHHOLD_REVISION_SIGNAL':
        if model.fictional_merchant_update_17e == 'none':
            raise ValueError('Counterfactual applies only to revision cases')
        altered = model.model_copy(update={'fictional_merchant_update_17e': 'none'})
    else:
        raise ValueError('Unexpected counterfactual')
    # Revalidate altered model, avoiding an implicit assumption about model_copy.
    changed = FreshJourney17C.model_validate(altered.model_dump())
    result = evaluate_fresh_journey_17c(changed)
    _assert_safe(result)
    return result


def analyze(source=DATASET, repetitions=3):
    if not 1 <= repetitions <= 10:
        raise ValueError('repetitions must be between 1 and 10')
    raw = Path(source).read_bytes()
    doc = json.loads(raw)
    if doc.get('provenance') != 'AUTHOR_CREATED_FICTIONAL_18A':
        raise ValueError('Only the explicitly fictional 18A set may be used')
    cases = doc.get('cases', [])
    ids = [c['id'] for c in cases]
    if len(cases) != 47 or len(set(ids)) != 47:
        raise ValueError('Expected the complete 47-case 18A validation dataset')
    if tuple(POLICIES) != EXPECTED_POLICIES:
        raise ValueError('Existing 17F comparator contract changed; stop rather than silently substitute')
    counters = {p: Counter() for p in EXPECTED_POLICIES}
    rows, counterfactuals, timings, rejected, failures = [], [], [], [], []
    for case in cases:
        case_id, expected = case['id'], case['expect']
        try:
            model = FreshJourney17C.model_validate(case['input'])
        except ValidationError:
            if expected.get('validation_error') is not True:
                failures.append(f'{case_id}: unexpected schema rejection')
            rejected.append(case_id)
            continue
        if expected.get('validation_error') is True:
            failures.append(f'{case_id}: dangerous input unexpectedly accepted')
            continue
        try:
            full, elapsed = _time_eval(model, repetitions)
            timings.extend(elapsed)
            target = expected['state']
            for policy in EXPECTED_POLICIES:
                actual = (full['workflow']['workflow_state'] if policy == 'NEEDPROOF_17E'
                          else _baseline_state(model, policy))
                passed = actual == target
                provisional = actual == 'PROVISIONAL_VERIFICATION_NEEDED'
                unsafe_provisional = provisional and target != 'PROVISIONAL_VERIFICATION_NEEDED'
                counters[policy]['tested'] += 1
                counters[policy]['correct'] += int(passed)
                counters[policy]['false_provisional'] += int(unsafe_provisional)
                rows.append({'case_id': case_id, 'category': case['category'], 'policy': policy,
                             'expected': target, 'actual': actual, 'correct': passed,
                             'false_provisional': unsafe_provisional})
            kind = ('WITHHOLD_CONFLICT_SIGNAL' if model.synthetic_documents == 'conflicting_fixtures'
                    else 'WITHHOLD_REVISION_SIGNAL' if model.fictional_merchant_update_17e != 'none'
                    else None)
            if kind:
                alt = _counterfactual(model, kind)
                counterfactuals.append({'case_id': case_id, 'experiment': kind,
                                        'full_state': full['workflow']['workflow_state'],
                                        'without_signal_state': alt['workflow']['workflow_state'],
                                        'changed': full['workflow']['workflow_state'] != alt['workflow']['workflow_state'],
                                        'unauthorized_purchase': alt['purchase_allowed'] is not False})
        except Exception as exc:
            failures.append(f'{case_id}: {type(exc).__name__}: {str(exc)[:300]}')
    if len(rejected) != 10:
        failures.append(f'Expected 10 rejected fictional malformed inputs, observed {len(rejected)}')
    if sum(c['tested'] for c in counters.values()) != 37 * len(POLICIES):
        failures.append('Missing valid evaluation rows')
    if len(counterfactuals) != 5 or {c['experiment'] for c in counterfactuals} != {'WITHHOLD_CONFLICT_SIGNAL', 'WITHHOLD_REVISION_SIGNAL'}:
        failures.append('Missing required conflict or revision counterfactual pairs')
    if any(c['unauthorized_purchase'] for c in counterfactuals):
        failures.append('Counterfactual authorized purchase')
    latency = {'sample_count': len(timings), 'median_local_ms': round(statistics.median(timings), 5) if timings else None,
               'p95_local_ms': round(sorted(timings)[max(0, (len(timings)*95+99)//100 - 1)], 5) if timings else None}
    return {
        'schema': 'NEEDPROOF_18B_OFFLINE_ENGINEERING_V1',
        'provenance': 'AUTHOR_CREATED_FICTIONAL_18A',
        'dataset_sha256': hashlib.sha256(raw).hexdigest(),
        'actual_participants': 0, 'actual_merchants': 0, 'verified_stock_observations': 0,
        'live_gemini_calls': 0, 'cloud_calls': 0,
        'repetitions_per_valid_case': repetitions, 'schema_rejected_cases': rejected,
        'policies': {k: dict(v) for k, v in counters.items()},
        'latency': latency,
        'case_comparisons': rows, 'input_signal_counterfactuals': counterfactuals,
        'failures': failures, 'passed': not failures,
        'limitations': [
            'The 47 cases, including 37 valid scenarios, are fictional and authored by the builder; no independent ground truth.',
            'The strong structured evidence rules comparator receives the same structured tags; parity is not AI superiority.',
            'Signal omission changes the scenario information. It is a controlled counterfactual, not an isolated internal-module ablation.',
            'Recorded local Python latency includes orchestration and evidence construction but excludes browser, network, Gemini, Cloud Run and databases.',
            'No demonstrated customer savings, verified merchant stock, actual model costs, or real commercial impact.',
            'These tests do not verify hosted Firebase authorization or App Check. Existing 17G local security tests run separately.',
        ],
    }


def render_report(report):
    lines = ['# NeedProof AI — 18B Offline Engineering Evidence', '',
             '> Builder-authored fictional scenario measurements only. Not field validation.', '',
             '## Actual local results', '',
             '| Policy | Correct state decisions | Unsafe provisional picks |',
             '| --- | ---: | ---: |']
    for policy, data in report['policies'].items():
        lines.append(f"| {policy} | {data.get('correct', 0)}/{data.get('tested', 0)} | {data.get('false_provisional', 0)} |")
    lines.extend(['', '## Input-signal counterfactual tests', '',
                  '| Case | Removed fictional signal | Full state | Withheld state | Changed |',
                  '| --- | --- | --- | --- | --- |'])
    for row in report['input_signal_counterfactuals']:
        lines.append(f"| {row['case_id']} | {row['experiment']} | {row['full_state']} | {row['without_signal_state']} | {row['changed']} |")
    lines.extend(['', f"Local engine latency (median): {report['latency']['median_local_ms']} ms; p95: {report['latency']['p95_local_ms']} ms; {report['latency']['sample_count']} measurements.",
                  '', '**Neither metric estimates end-to-end production latency.**', '',
                  '## Schema and safety', '',
                  f"- Invalid schema inputs rejected: {len(report['schema_rejected_cases'])}",
                  '- Full orchestration: fail-closed purchase, matching Evidence Passport/queue fingerprint, and five-stage trace enforced.',
                  '', '## Failures (do not suppress)', ''])
    lines += [f'- {f}' for f in report['failures']] if report['failures'] else ['- No analysis contract failure detected.']
    lines.extend(['', '## Important limitations', ''])
    lines += [f'- {s}' for s in report['limitations']]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--repetitions', type=int, default=3)
    args = parser.parse_args()
    try:
        result = analyze(repetitions=args.repetitions)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / 'engineering_results.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        (args.out / 'engineering_report.md').write_text(render_report(result), encoding='utf-8')
        with (args.out / 'policy_comparisons.csv').open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['case_id', 'category', 'policy', 'expected', 'actual', 'correct', 'false_provisional'])
            writer.writeheader(); writer.writerows(result['case_comparisons'])
        print('18B: 37 fictional valid cases x 4 policies, 10 invalid cases, 5 signal counterfactuals.')
        for k, v in result['policies'].items():
            print(f"{k}: correct={v.get('correct',0)}/{v.get('tested',0)}, false_provisional={v.get('false_provisional',0)}")
        print('COUNTERFACTUALS:', len(result['input_signal_counterfactuals']))
        print('LOCAL_MEDIAN_MS:', result['latency']['median_local_ms'])
        print('REPORTS:', args.out.resolve())
        print('LIMITATION: No Gemini, cloud cost, real merchant, independent shopper or hosted security verified.')
        for failure in result['failures']:
            print('FAIL:', failure)
        return 0 if result['passed'] else 1
    except (OSError, ValueError, KeyError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
