"""Chunk 17A socket guard test: only local loopback is permitted."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/trace_chunk17a_backend.py"


def _guard_prelude() -> str:
    raw = SOURCE.read_text(encoding="utf-8")
    start = raw.index("# An in-process TestClient does not access a hosted service.")
    end = raw.index("\nROOT = Path(", start)
    return raw[start:end]


def test_17a_guard_allows_windows_asyncio_socketpair_and_denies_external_tcp():
    # Run in a child Python process so monkey-patching socket.connect cannot
    # affect the main pytest process, its plugins or a developer's workstation.
    script = 'import socket\nimport ipaddress\n' + _guard_prelude() + r'''
# Windows socketpair emulates an internal wake-up over 127.0.0.1.
left, right = socket.socketpair()
left.sendall(b'x')
assert right.recv(1) == b'x'
left.close(); right.close()

listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listener.bind(('127.0.0.1', 0)); listener.listen(1)
peer = socket.create_connection(('127.0.0.1', listener.getsockname()[1]), timeout=1)
accepted, _ = listener.accept()
peer.close(); accepted.close(); listener.close()

for host in ['1.1.1.1', '8.8.8.8', 'example.com']:
    candidate = socket.socket()
    try:
        try:
            candidate.connect((host, 443))
        except RuntimeError as exc:
            assert 'non-loopback' in str(exc)
        else:
            raise AssertionError('External connection was not blocked')
        try:
            candidate.connect_ex((host, 443))
        except RuntimeError:
            pass
        else:
            raise AssertionError('External connect_ex was not blocked')
        try:
            socket.create_connection((host, 443), timeout=0.1)
        except RuntimeError:
            pass
        else:
            raise AssertionError('External create_connection was not blocked')
    finally:
        candidate.close()
print('PASS: internal socketpair/loopback allowed; external TCP blocked')
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=12)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "PASS: internal socketpair/loopback allowed" in result.stdout


def test_focused_guard_is_nonproduction_and_test_only():
    s = SOURCE.read_text(encoding="utf-8")
    assert 'LOCAL_TEST_IDENTITY_NOT_REAL_AUTH' in s
    assert 'app.dependency_overrides.pop(require_firebase_client, None)' in s
    assert 'socket.socket.connect = _local_only_connect' in s
    assert 'socket.socket.connect_ex = _local_only_connect_ex' in s
    assert 'socket.create_connection = _local_only_create_connection' in s
    assert 'Cloud Run' in s
