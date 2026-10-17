"""Offline-only guard behavior. Does not import tokens or call cloud services."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "preflight_chunk16b2.py"
spec = importlib.util.spec_from_file_location("np16b2_preflight", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_audited_source_passes_without_using_git():
    assert module.audit(REPO, verify_git=False) == []


def test_no_network_api_imports_in_gate():
    txt = SCRIPT.read_text(encoding="utf-8")
    assert "import requests" not in txt
    assert "import urllib" not in txt
    assert "import socket" not in txt
    assert "gcloud " not in txt
    assert "firebase deploy" not in txt


def test_detects_changed_backend(tmp_path: Path):
    shutil.copytree(REPO / "backend" / "app", tmp_path / "backend" / "app")
    (tmp_path / "frontend/src/lib").mkdir(parents=True)
    for f in ("cloudDecisions.ts", "guidedJourney16a.ts"):
        shutil.copy2(REPO / "frontend/src/lib" / f, tmp_path / "frontend/src/lib" / f)
    shutil.copy2(REPO / "firestore.rules", tmp_path / "firestore.rules")
    path = tmp_path / "backend/app/cloud_decision_api.py"
    path.write_text(
    path.read_text(encoding="utf-8").replace(
        "allow_origins=ALLOWED_ORIGINS",
        "allow_origins=['*']"
    ),
    encoding="utf-8"
)
    issues = module.audit(tmp_path, verify_git=False)
    assert any("cloud_decision_api.py" in i for i in issues)
    assert any("Origin allowlist" in i for i in issues)


def test_detects_missing_firestore_rules(tmp_path: Path):
    issues = module.audit(tmp_path, verify_git=False)
    assert any("firestore.rules" in i for i in issues)


def test_handles_windows_newlines(tmp_path: Path):
    src = REPO / "firestore.rules"
    dst = tmp_path / "firestore.rules"
    dst.write_bytes(src.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert module.sha256_normalized(dst) == module.EXPECTED["firestore.rules"]


def test_live_plan_does_not_execute_calls():
    p = subprocess.run([sys.executable, str(SCRIPT), "--print-live-plan"],
                       capture_output=True, text=True, timeout=10)
    assert p.returncode == 0
    assert "NOT AUTHORIZED" in p.stdout
    assert p.stderr == ""
