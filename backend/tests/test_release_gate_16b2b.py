"""Offline checks; no Firebase tokens, CLI cloud calls or production access."""
import importlib.util
import shutil
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_chunk16b2b.py"
spec = importlib.util.spec_from_file_location("np16b2b", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ROOT = SCRIPT.parents[1]

def test_report_does_not_claim_live_pass():
    row = module.report([])
    assert row["local_security_gate"] == "PASS"
    assert row["production_real_id_tokens"] == "UNVERIFIED"
    assert row["cross_project_firestore_io"] == "UNVERIFIED"
    assert row["deployments_performed"] == row["cloud_calls_performed"] == 0

def test_stop_on_failed_audit():
    row = module.report(["changed header check"])
    assert row["local_security_gate"] == "STOP"
    assert len(row["issues"]) == 1

def test_ten_feature_flags_are_audited():
    assert len(module.REQUIRED_FLAGS) == 10
    assert "GUIDED_JOURNEY_16A_ENABLED" in module.REQUIRED_FLAGS

def test_no_network_or_gcloud_in_default_checker():
    code = SCRIPT.read_text(encoding="utf-8")
    assert "requests.get(" not in code
    assert '"gcloud"' not in code
    assert "firebase deploy" not in code.split('def audit(')[1].split('def report(')[0]

def test_local_reconstructed_source_passes_offline_check():
    assert module.audit(ROOT, verify_git=False) == []

def test_detects_missing_live_readiness_file(tmp_path: Path):
    dest = tmp_path / "repo"
    shutil.copytree(ROOT / "backend/app", dest / "backend/app")
    (dest / "frontend/src/lib").mkdir(parents=True)
    for name in ("cloudDecisions.ts", "guidedJourney16a.ts"):
        shutil.copy2(ROOT / "frontend/src/lib" / name, dest / "frontend/src/lib" / name)
    shutil.copy2(ROOT / "firestore.rules", dest / "firestore.rules")
    (dest / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/preflight_chunk16b2.py", dest / "scripts/preflight_chunk16b2.py")
    (dest / "docs").mkdir(parents=True)
    shutil.copy2(ROOT / "docs/CHUNK16B_LIVE_READINESS.md", dest / "docs/CHUNK16B_LIVE_READINESS.md")
    assert any("Missing release documentation" in x for x in module.audit(dest, verify_git=False))
