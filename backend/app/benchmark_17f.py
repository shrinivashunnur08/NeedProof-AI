"""Chunk 17F: reproducible, explicitly *synthetic* comparison.

No model calls, shopping contacts, purchase, filesystem writes or networking.
Fixtures contain authored policy expectations; independent labels and actual
consumer outcomes have NOT been collected. The strongest comparator sees the
same structured evidence tags as NeedProof. No LLM-only baseline is claimed.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
import json
import statistics
import time

from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c

P = 'PROVISIONAL_VERIFICATION_NEEDED'
M = 'MORE_EVIDENCE_NEEDED'
C = 'RESEARCH_CONFLICT'
D = 'DISCOVERY_NEEDED'
STATES = {P, M, C, D}
ACTIONS = {'CHECK_COMPATIBILITY', 'REFRESH_ALTERNATIVES', 'RECONCILE_CONFLICT', 'DISCOVER_MERCHANTS'}
POLICIES = ('NEEDPROOF_17E', 'PRICE_ONLY', 'STOCK_AND_BUDGET', 'STRUCTURED_EVIDENCE_RULES')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def load_cases(path: Path):
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    cases = doc['cases']
    if doc['schema'] != 'NEEDPROOF_SYNTHETIC_BENCHMARK_17F_V1' or len(cases) != 40 or doc.get('labels_independently_validated') is not False:
        raise ValueError('Unexpected 17F dataset or mislabeled source')
    ids = [c['case_id'] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case IDs')
    groups = Counter(c['family'] for c in cases)
    if len(groups) < 7:
        raise ValueError('Benchmark lacks scenario diversity')
    for c in cases:
        inp = FreshJourney17C.model_validate(c['input'])
        exp = c['expected']
        if exp['workflow_state'] not in STATES or exp['first_verification_action'] not in ACTIONS:
            raise ValueError(f"Unknown authored labels in {c['case_id']}")
        if exp['purchase_allowed'] is not False or exp['provisional_candidate_allowed'] != (exp['workflow_state'] == P):
            raise ValueError(f"Unsafe expected label in {c['case_id']}")
        if not c.get('ground_truth_rationale') or inp.simulation_acknowledged is not True:
            raise ValueError('Missing label rationale or fictional acknowledgment')
    return doc


def effective_report(i: FreshJourney17C):
    return ('stockout' if i.fictional_merchant_update_17e == 'stockout_after_report'
            else 'reported_offer' if i.fictional_merchant_update_17e == 'restock_after_stockout'
            else i.simulated_report)


def simple_baseline(inp: FreshJourney17C, policy: str):
    """Same structured input for every comparator; intentionally explicit heuristics."""
    final = effective_report(inp)
    no_offer = final == 'no_merchants'
    price_ok = inp.reported_price_inr <= inp.budget_inr
    stock_ok = final == 'reported_offer'
    conflict = inp.synthetic_documents == 'conflicting_fixtures'
    if policy == 'PRICE_ONLY':
        if no_offer: state, action = D, 'DISCOVER_MERCHANTS'
        elif price_ok: state, action = P, 'CHECK_COMPATIBILITY'
        else: state, action = M, 'REFRESH_ALTERNATIVES'
    elif policy == 'STOCK_AND_BUDGET':
        if no_offer: state, action = D, 'DISCOVER_MERCHANTS'
        elif not price_ok or not stock_ok: state, action = M, 'REFRESH_ALTERNATIVES'
        else: state, action = P, 'CHECK_COMPATIBILITY'
    elif policy == 'STRUCTURED_EVIDENCE_RULES':
        # Strong deterministic competitor gets the same structured conflict tags
        # and revision updates. Parity here is not evidence of AI superiority.
        if no_offer: state, action = D, 'DISCOVER_MERCHANTS'
        elif conflict: state, action = C, 'RECONCILE_CONFLICT'
        elif not price_ok or not stock_ok: state, action = M, 'REFRESH_ALTERNATIVES'
        else: state, action = P, 'CHECK_COMPATIBILITY'
    else:
        raise ValueError('Unknown baseline')
    return {'workflow_state': state, 'first_verification_action': action,
            'provisional_candidate_selected': state == P, 'purchase_allowed': False}


def run_one(case, policy):
    inp = FreshJourney17C.model_validate(case['input'])
    start = time.perf_counter_ns()
    if policy == 'NEEDPROOF_17E':
        data = evaluate_fresh_journey_17c(inp)
        w = data['workflow']
        q = data['verification_queue_17e']
        result = {'workflow_state': w['workflow_state'],
                  'first_verification_action': q['recommended_action_id'],
                  'provisional_candidate_selected': w['workflow_state'] == P and w['merchant_replanning']['selected'] is not None,
                  'purchase_allowed': w['purchase_allowed']}
        if data['gemini_called'] or data['merchant_contacted'] or data['database_written']:
            raise RuntimeError('Benchmark unexpectedly used model, merchant, or DB')
        if data['purchase_allowed'] or data['stock_independently_verified'] or q['merchant_verified']:
            raise RuntimeError('Unsafe benchmark engine contract')
    else:
        result = simple_baseline(inp, policy)
    duration_us = (time.perf_counter_ns()-start)/1000
    exp = case['expected']
    result.update({
        'case_id': case['case_id'], 'family': case['family'],
        'correct_state': result['workflow_state'] == exp['workflow_state'],
        'correct_first_check': result['first_verification_action'] == exp['first_verification_action'],
        'false_provisional_offer': result['provisional_candidate_selected'] and not exp['provisional_candidate_allowed'],
        'missed_provisional_offer': not result['provisional_candidate_selected'] and exp['provisional_candidate_allowed'],
        'unauthorized_purchase': result['purchase_allowed'] is not False,
        'expected_state': exp['workflow_state'],
        'expected_first_check': exp['first_verification_action'],
        'elapsed_microseconds': round(duration_us, 3),
    })
    return result


def run_suite(doc, *, repetitions=1):
    """No randomization or hidden case filtering. One semantic decision per case."""
    if repetitions < 1 or repetitions > 20:
        raise ValueError('Repetitions must be 1..20')
    cases = doc['cases']
    individual = {}
    aggregates = {}
    for policy in POLICIES:
        rows = []
        samples = []
        for case in cases:
            for attempt in range(repetitions):
                row = run_one(case, policy)
                samples.append(row['elapsed_microseconds'])
                if attempt == 0: rows.append(row)
        # Runtime is system-dependent. Semantic comparison is derived from the first run.
        totals = {k: sum(bool(r[k]) for r in rows) for k in ('correct_state','correct_first_check','false_provisional_offer','missed_provisional_offer','unauthorized_purchase')}
        aggregates[policy] = {
            'case_count': len(rows), **totals,
            'state_accuracy_fraction': round(totals['correct_state']/len(rows), 4),
            'first_check_accuracy_fraction': round(totals['correct_first_check']/len(rows), 4),
            'median_local_microseconds': round(statistics.median(samples),2),
            'p95_local_microseconds': round(sorted(samples)[min(len(samples)-1, int(0.95 * len(samples)))],2),
            'runtime_samples':len(samples),
        }
        individual[policy]=rows
    semantics = {p:[{k:r[k] for k in ('case_id','workflow_state','first_verification_action','provisional_candidate_selected','purchase_allowed','correct_state','correct_first_check','false_provisional_offer')} for r in individual[p]] for p in POLICIES}
    return {
        'schema':'NEEDPROOF_17F_SIMULATED_COMPARISON_V1',
        'dataset_sha256':sha256(canonical(doc)).hexdigest(),
        'semantic_results_sha256':sha256(canonical(semantics)).hexdigest(),
        'dataset_size':len(cases),
        'family_counts':dict(sorted(Counter(c['family'] for c in cases).items())),
        'dataset_origin':'HAND_CURATED_FICTIONAL_CASES_AUTHOR_DEFINED_EXPECTED_LABELS',
        'ground_truth_independently_validated':False,
        'live_gemini_or_llm_baseline_executed':False,
        'policies':aggregates,
        'per_case':individual,
        'limitations':[
            'Synthetic cases authored by the builders; expected labels are policy hypotheses, not independently verified ground truth.',
            'This is NOT evidence of real shopper time saved, fewer wasted trips, merchant adoption or revenue impact.',
            'Comparators receive identical structured inputs; STRUCTURED_EVIDENCE_RULES is a strong non-LLM baseline, not a real LLM-only baseline.',
            'Numerical EVSI priors are hypothetical and uncalibrated; no measured claim is derived from their values.',
            'Local runtimes exclude network, model, database and UI, and vary with host hardware and Python environment.',
            'All offers, document excerpts and merchant stock claims are fictional; no purchases are authorized.',
        ],
    }
