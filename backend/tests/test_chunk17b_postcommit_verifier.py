from __future__ import annotations
from pathlib import Path
import hashlib
import subprocess
import sys


def test_17b_verifier_does_not_require_old_git_head_after_commit():
    source = Path(__file__).resolve().parents[2] / 'scripts' / 'verify_chunk17b.cmd'
    data = source.read_text(encoding='utf8')
    assert 'scripts\\apply_chunk17b.py --check' not in data
    assert 'backend\\.venv\\Scripts\\python.exe -m pytest -q' in data
    assert 'scripts\\trace_chunk17b_offline.py' in data
    assert 'MOCKED GEMINI ONLY - NO CLOUD REQUESTS' in data
    assert 'LIVE GEMINI REMAINS UNVERIFIED' in data
