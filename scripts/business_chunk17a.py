#!/usr/bin/env python3
"""Chunk 17A: business-jury hypothesis and evidence-readiness report.

Does not import app code, load credentials, contact any external service, or
fabricate validation metrics. Reads only the allowlisted hypotheses file.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

CONFIG = 'docs/CHUNK17A_BUSINESS_HYPOTHESES.json'
REQUIRED_IDS = frozenset({
    'unsupported_recommendation_rate', 'correct_abstention_rate',
    'useful_decision_rate', 'median_time_to_decision_seconds',
    'merchant_submission_seconds', 'unit_cost_per_journey_inr',
    'prevented_wasted_visits',
})


def validate(config: dict) -> list[str]:
    errors: list[str] = []
    if config.get('schema') != 'needproof_17a_business_hypotheses_v1':
        errors.append('Schema mismatch')
    for field in ('target_market', 'primary_persona', 'secondary_persona', 'flagship_scenario',
                  'problem_claim', 'value_proposition', 'differentiation_hypothesis',
                  'commercial_hypothesis'):
        if not isinstance(config.get(field), str) or not config[field].strip():
            errors.append(f'Missing business hypothesis: {field}')
    metrics = config.get('metrics')
    if not isinstance(metrics, list):
        return errors + ['Metric list is required']
    ids = [m.get('id') for m in metrics if isinstance(m, dict)]
    if set(ids) != REQUIRED_IDS or len(ids) != len(REQUIRED_IDS):
        errors.append('Expected exactly the seven agreed metrics')
    for item in metrics:
        if not isinstance(item, dict):
            errors.append('Metric entries must be objects')
            continue
        metric_id = item.get('id', 'UNKNOWN')
        status, value, source = item.get('status'), item.get('value'), item.get('evidence_source')
        if status == 'NOT_MEASURED':
            if value is not None or source is not None:
                errors.append(f'{metric_id}: not-measured metric cannot contain values or evidence')
        elif status == 'MEASURED':
            if not isinstance(value, (float, int)) or isinstance(value, bool) or not math.isfinite(value):
                errors.append(f'{metric_id}: measured metric requires a finite numeric value')
            if not isinstance(source, str) or not source.strip():
                errors.append(f'{metric_id}: measured metric must cite its evidence_source')
            if metric_id in ('unsupported_recommendation_rate', 'correct_abstention_rate', 'useful_decision_rate') and isinstance(value, (float, int)) and not 0 <= value <= 1:
                errors.append(f'{metric_id}: ratio must be between 0 and 1')
        else:
            errors.append(f'{metric_id}: invalid metric status')
    for field in ('business_questions', 'comparison_baselines', 'business_risks', 'success_criteria'):
        if not isinstance(config.get(field), list) or not config[field]:
            errors.append(f'{field}: non-empty list required')
    if len(config.get('comparison_baselines', [])) < 3:
        errors.append('Minimum three comparison baselines required')
    return errors


def render_md(config: dict) -> str:
    lines = [
        '# NeedProof AI — 17A Business-Jury Readiness', '',
        '> **Unvalidated hypotheses.** Generated offline. This is not market research, a pilot, or measured business impact.', '',
        '## Executive positioning', '',
        f"**Initial market:** {config['target_market']}", '',
        f"**Primary customer:** {config['primary_persona']}", '',
        f"**Merchant persona:** {config['secondary_persona']}", '',
        f"**Flagship demo:** {config['flagship_scenario']}", '',
        f"**Problem to validate:** {config['problem_claim']}", '',
        f"**Value proposition to validate:** {config['value_proposition']}", '',
        f"**Differentiation to prove:** {config['differentiation_hypothesis']}", '',
        f"**Business model hypothesis:** {config['commercial_hypothesis']}", '',
        '## Required measurable evidence (none invented)', '',
        '| KPI | Current value | Evidence | Measurement formula |', '|---|---|---|---|',
    ]
    for item in config['metrics']:
        value = 'NOT MEASURED' if item['value'] is None else f"{item['value']} {item['unit']}"
        evidence = item['evidence_source'] or 'Not collected'
        lines.append(f"| {item['label']} | {value} | {evidence} | {item['formula']} |")
    lines += ['', '## Minimum comparator approaches', '']
    lines.extend(f'- `{item}`' for item in config['comparison_baselines'])
    lines += ['', '## Questions for consenting shoppers and merchants', '']
    lines.extend(f'- {item}' for item in config['business_questions'])
    lines += ['', '## Business risks (open until proved otherwise)', '']
    for entry in config['business_risks']:
        lines.append(f"- **{entry['risk']}** — {entry['mitigation']} (**{entry['status']}**)" )
    lines += ['', '## Acceptance requirements for remaining chunks', '']
    lines.extend(f'- {item}' for item in config['success_criteria'])
    lines += ['', '## Judge-facing truth conditions', '',
        '- Store discovery ≠ confirmed inventory. Merchant statement ≠ independently verified stock.',
        '- Replayed JSON ≠ a freshly executed Gemini or FastAPI request.',
        '- Synthetic benchmarks ≠ observed customer savings.',
        '- A pilot is optional and only possible with informed, consenting participants.',
        '- Revenue models and unit economics are hypotheses until measured.',
        '- No 95+/100 score or shortlist probability can be inferred from the roadmap alone.', '',
        '## Next business action', '',
        '17A: review and accept hypotheses; 17F: run fair blind benchmarks; 18A: seek voluntary user/merchant feedback; 18B: record actual cost per journey. Keep evidence citations when values are populated.', '',
    ]
    return '\n'.join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description='NeedProof business hypothesis audit (offline only)')
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='Validate hypotheses, no filesystem writes')
    mode.add_argument('--report', action='store_true', help='Write local report under qa_reports/17a')
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    a = p.parse_args()
    root = a.root.resolve()
    try:
        config = json.loads((root / CONFIG).read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print('ERROR: business hypotheses file unavailable or invalid:', type(exc).__name__)
        return 2
    errors = validate(config)
    if errors:
        for error in errors:
            print('NEEDS_INSPECTION:', error)
        return 1
    print('PASS: Target retail market, personas, merchant incentive, and value proposition defined as hypotheses')
    print('PASS: 7/7 KPIs tracked with evidence status; no unsupported measured results')
    print('PASS: Three comparison baselines and pilot/business risks included')
    print('NOT VERIFIED: merchant adoption, real cost per journey, shopper outcomes, commercial viability')
    if a.report:
        folder = root / 'qa_reports' / '17a'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'business_readiness.md'
        path.write_text(render_md(config), encoding='utf-8')
        print('REPORT:', path)
    print('No external requests, credentials, cloud config changes, or new spending.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
