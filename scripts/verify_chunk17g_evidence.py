#!/usr/bin/env python3
"""No-network integrity gate for the public 17F summary displayed in 17G React.

Run after scripts/run_chunk17f_benchmark.py. Uses existing deterministic
semantic digests, not microsecond timing numbers.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PIN=ROOT/'frontend/src/generated/benchmark17fReview.json'
REPORT=ROOT/'qa_reports/17f/benchmark_results.json'


def verify_summary(pin_path=PIN, result_path=REPORT):
    displayed=json.loads(Path(pin_path).read_text(encoding='utf-8'))
    report=json.loads(Path(result_path).read_text(encoding='utf-8'))
    if displayed.get('schema')!='NEEDPROOF_17G_PUBLISHED_SYNTHETIC_BENCHMARK_V1':
        raise ValueError('Wrong published benchmark schema')
    for label,field in [('dataset_size','dataset_size'),('dataset_sha256','dataset_sha256'),('semantic_results_sha256','semantic_results_sha256')]:
        if displayed.get(label)!=report.get(field):
            raise ValueError(f'STALE JURY EVIDENCE: mismatch in {label}')
    if displayed.get('source_commit')!='4874ff7':
        raise ValueError('Wrong benchmark source baseline')
    for key in ('independent_ground_truth','live_gemini_tested','real_merchants_contacted','observed_real_customer_outcomes'):
        if displayed.get(key) is not False:
            raise ValueError(f'Unsupported verification claim: {key}')
    if not isinstance(displayed.get('policies'),list) or len(displayed['policies'])!=4:
        raise ValueError('Exactly four policies required')
    ids=[x['id'] for x in displayed['policies']]
    if len(ids)!=len(set(ids)) or set(ids)!=set(report['policies']):
        raise ValueError('Baseline identity mismatch')
    for row in displayed['policies']:
        observed=report['policies'][row['id']]
        for a,b in [('correct','correct_state'),('first_checks_correct','correct_first_check'),('unsafe_provisional','false_provisional_offer')]:
            if row.get(a)!=observed[b]:
                raise ValueError(f'STALE JURY EVIDENCE: {row["id"]}.{a}')
    if displayed['policies'][0]['id']!='NEEDPROOF_17E':
        raise ValueError('Unstable benchmark ordering')
    if (report['policies']['NEEDPROOF_17E']['correct_state'] !=
        report['policies']['STRUCTURED_EVIDENCE_RULES']['correct_state']):
        raise ValueError('Baseline tie changed; review judge-facing text before publishing')
    print('PASS: 17G React benchmark summary matches freshly generated 17F report and acknowledges rule-baseline tie.')
    print('DATASET_SHA256:',displayed['dataset_sha256'])
    print('SEMANTIC_SHA256:',displayed['semantic_results_sha256'])
    print('ALL EXTERNAL VALIDATION FLAGS: False')
    return True


if __name__=='__main__':
    verify_summary()
