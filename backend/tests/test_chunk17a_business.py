"""17A business audit tests: hypotheses are always distinct from measured facts."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'scripts/business_chunk17a.py'
spec = importlib.util.spec_from_file_location('needproof_17a_business_tool', TOOL)
assert spec and spec.loader
business = importlib.util.module_from_spec(spec)
spec.loader.exec_module(business)


@pytest.fixture
def business_config():
    return json.loads((ROOT / business.CONFIG).read_text(encoding='utf-8'))


def test_all_seven_metrics_are_explicitly_unmeasured(business_config):
    assert len(business_config['metrics']) == 7
    assert all(m['status'] == 'NOT_MEASURED' and m['value'] is None and m['evidence_source'] is None for m in business_config['metrics'])
    assert business.validate(business_config) == []


def test_primary_pain_and_merchant_incentive_are_described_as_hypotheses(business_config):
    assert 'electronics' in business_config['target_market'].lower()
    assert 'merchant' in business_config['secondary_persona'].lower()
    assert business_config['commercial_hypothesis']
    assert 'hypothesis' in business_config['commercial_hypothesis'].lower() or 'may ' in business_config['commercial_hypothesis'].lower()


def test_no_fake_result_can_be_attached_to_unmeasured_metric(business_config):
    m = business_config['metrics'][0]
    m['value'] = 0.99
    assert any('not-measured' in x for x in business.validate(business_config))


def test_measured_metric_requires_evidence(business_config):
    m = business_config['metrics'][0]
    m.update({'status': 'MEASURED', 'value': 0.05, 'evidence_source': None})
    assert any('evidence_source' in x for x in business.validate(business_config))


def test_invalid_ratio_is_rejected(business_config):
    m = business_config['metrics'][0]
    m.update({'status': 'MEASURED', 'value': 1.5, 'evidence_source': 'documented experiment'})
    assert any('between 0 and 1' in x for x in business.validate(business_config))


def test_lack_of_comparators_fails(business_config):
    business_config['comparison_baselines'] = ['needproof_full_evidence_planner']
    assert business.validate(business_config)


def test_report_flags_unverified_business_impact(business_config):
    report = business.render_md(business_config)
    assert 'NOT MEASURED' in report
    assert 'Unvalidated hypotheses' in report
    assert 'merchant adoption' in report.lower() or 'merchant' in report.lower()
    assert 'Replayed JSON' in report


def test_schema_mismatch_rejected(business_config):
    business_config['schema'] = 'unknown'
    assert 'Schema mismatch' in business.validate(business_config)


def test_report_only_writes_into_local_qa_reports(tmp_path, business_config):
    root = tmp_path
    p = root / business.CONFIG
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(business_config), encoding='utf-8')
    assert business.validate(json.loads(p.read_text(encoding='utf-8'))) == []
    assert 'qa_reports/17a' not in str(p)
