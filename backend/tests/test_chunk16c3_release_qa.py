"""Offline final demo acceptance checks: no API and no real credentials."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('np16c3', REPO / 'scripts/audit_chunk16c3.py')
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class ReleaseAuditTests(unittest.TestCase):
    def test_actual_repo_passes_static_checks(self):
        report = mod.audit(REPO)
        self.assertEqual(report['failed'], 0, report)
        self.assertFalse(report['hosted_release_approved'])
        self.assertFalse(report['cloud_resources_modified'])

    def test_scenario_states_are_distinct(self):
        data = json.loads((REPO / 'frontend/src/generated/needproof16cReplay.json').read_text(encoding='utf-8'))
        states = [data['scenarios'][k]['workflow']['workflow_state'] for k in mod.CASES]
        self.assertEqual(len(set(states)), 4)

    def test_replay_never_allows_purchase(self):
        data = json.loads((REPO / 'frontend/src/generated/needproof16cReplay.json').read_text(encoding='utf-8'))
        for case in data['scenarios'].values():
            self.assertIs(case['purchase_allowed'], False)
            self.assertIs(case['workflow']['purchase_allowed'], False)

    def test_stockout_is_replan(self):
        data = json.loads((REPO / 'frontend/src/generated/needproof16cReplay.json').read_text(encoding='utf-8'))
        self.assertTrue(data['scenarios']['stockout']['workflow']['change_detection']['changed'])

    def test_tampered_purchase_flag_fails_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            files = ('frontend/src/FreeShowcase.tsx', 'frontend/src/components/JudgeReplay16C2.tsx',
                     'frontend/src/generated/needproof16cReplay.json')
            for rel in files:
                target = base / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO / rel, target)
            rel = base / files[-1]
            data = json.loads(rel.read_text(encoding='utf-8'))
            data['scenarios']['stockout']['purchase_allowed'] = True
            rel.write_text(json.dumps(data), encoding='utf-8')
            report = mod.audit(base)
            self.assertGreater(report['failed'], 0)

    def test_report_markdown_mentions_unverified_live_auth(self):
        report = mod.audit(REPO)
        markdown = mod.render_md(report)
        self.assertIn('production authentication', markdown)
        self.assertIn('Human acceptance matrix', markdown)


if __name__ == '__main__':
    unittest.main()
