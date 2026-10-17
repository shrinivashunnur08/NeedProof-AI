"""Regression tests for Chunk 17C Windows standalone verification script."""
from pathlib import Path
import hashlib
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "verify_chunk17c.cmd"
FIXER = ROOT / "scripts" / "fix_chunk17c_runner_path.py"


def module():
    spec = importlib.util.spec_from_file_location("fix_chunk17c_runner_path", FIXER)
    assert spec and spec.loader
    instance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instance)
    return instance


def test_runner_sets_backend_path_before_pytest():
    lines = RUNNER.read_text(encoding="utf-8").splitlines()
    cd_idx = next(i for i,v in enumerate(lines) if v.startswith('cd /d "%~dp0.."'))
    py_idx = lines.index(r'set "PYTHONPATH=%CD%\backend"')
    run_idx = next(i for i,v in enumerate(lines) if " -m pytest " in v)
    assert cd_idx < py_idx < run_idx
    assert "setlocal" in lines[:py_idx]


def test_fix_rejects_changed_script():
    m = module()
    original = RUNNER.read_bytes()
    assert m.patch(original)[1] is True  # idempotent on installed runner
    try:
        m.patch(original.replace(b"NO CLOUD", b"INTERNET ACTIVE", 1))
    except RuntimeError as exc:
        assert "STOP" in str(exc)
    else:
        raise AssertionError("Guard unexpectedly accepted altered script")


def test_fix_rejects_unknown_source():
    m = module()
    try:
        m.patch(b"@echo off\nsetlocal\necho changed\n")
    except RuntimeError as exc:
        assert "STOP" in str(exc)
    else:
        raise AssertionError("Guard accepted unrelated batch file")
