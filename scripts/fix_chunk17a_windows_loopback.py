#!/usr/bin/env python3
"""Guarded, local-only fix for Chunk 17A Windows asyncio socketpair."""
import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = ROOT / "scripts/trace_chunk17a_backend.py"
TEST_PATH = ROOT / "backend/tests/test_chunk17a_audit.py"
OLD_TRACE_HASH = "321be5be7721897acd0cdfeb237257ad56e69d3b065c58a407a9307e68bf7d13"
OLD_TEST_HASH = "fbbf8d4c157699190b864c9193018c1a2651ca961d66995a85f4d0d1a68011fc"
NEW_TRACE_HASH = "ea83c695b453c69596e88a59b92df61fb49d7f358ac3be98cc60259aa5ceb006"
NEW_TEST_HASH = "69a4993d1cc19b2b95b68073c052792df691f13f710e0045751900dfe3c5eb3d"

OLD_GUARD = '# This executable is IN-PROCESS only. Block socket connections even if a\n# future imported SDK inadvertently tries to reach a paid cloud endpoint.\nimport socket\ndef _deny_outbound(*_args, **_kwargs):\n    raise RuntimeError("Chunk 17A local trace blocks ALL outbound socket connections")\nsocket.create_connection = _deny_outbound\nsocket.socket.connect = _deny_outbound\nsocket.socket.connect_ex = _deny_outbound\n'
NEW_GUARD = '# An in-process TestClient does not access a hosted service. On Windows,\n# asyncio/AnyIO builds its internal socketpair over 127.0.0.1. Reject external\n# TCP destinations while allowing local loopback for the event-loop wake-up.\n# This guard is a defensive smoke-test measure, not an OS-level egress sandbox.\nimport ipaddress\nimport socket\n\n_original_connect_17a = socket.socket.connect\n_original_connect_ex_17a = socket.socket.connect_ex\n_original_create_connection_17a = socket.create_connection\n\n\ndef _is_loopback_address_17a(address: object) -> bool:\n    if not isinstance(address, tuple) or not address:\n        return False\n    host = address[0]\n    if not isinstance(host, str):\n        return False\n    try:\n        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback\n    except ValueError:\n        return False  # Deny domain names: don\'t initiate a DNS lookup.\n\n\ndef _local_only_connect(self: socket.socket, address: object) -> None:\n    if not _is_loopback_address_17a(address):\n        raise RuntimeError("Chunk 17A blocks non-loopback TCP connections")\n    return _original_connect_17a(self, address)\n\n\ndef _local_only_connect_ex(self: socket.socket, address: object) -> int:\n    if not _is_loopback_address_17a(address):\n        raise RuntimeError("Chunk 17A blocks non-loopback TCP connections")\n    return _original_connect_ex_17a(self, address)\n\n\ndef _local_only_create_connection(address: object, *args, **kwargs):\n    if not _is_loopback_address_17a(address):\n        raise RuntimeError("Chunk 17A blocks non-loopback TCP connections")\n    return _original_create_connection_17a(address, *args, **kwargs)\n\n\nsocket.socket.connect = _local_only_connect\nsocket.socket.connect_ex = _local_only_connect_ex\nsocket.create_connection = _local_only_create_connection\n'
OLD_ASSERT = "    assert 'socket.socket.connect = _deny_outbound' in trace"
NEW_ASSERT = "    assert 'socket.socket.connect = _local_only_connect' in trace\n    assert 'socket.socket.connect_ex = _local_only_connect_ex' in trace\n    assert 'socket.create_connection = _local_only_create_connection' in trace"


def _read_and_hash(path: Path):
    if not path.is_file():
        raise RuntimeError(f"Missing source: {path}")
    raw = path.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n")
    return normalized.decode("utf-8"), hashlib.sha256(normalized).hexdigest(), b"\r\n" in raw


def _inspect():
    states = {}
    for name, path, before, after in [
        ("trace", TRACE_PATH, OLD_TRACE_HASH, NEW_TRACE_HASH),
        ("audit_test", TEST_PATH, OLD_TEST_HASH, NEW_TEST_HASH),
    ]:
        _, digest, _ = _read_and_hash(path)
        if digest == before:
            states[name] = "original"
        elif digest == after:
            states[name] = "patched"
        else:
            raise RuntimeError(f"REFUSING unexpected {name} SHA256={digest}. No files modified.")
    return states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        states = _inspect()
        print("PASS: Audited Chunk 17A trace and existing test; source hashes match.", states)
        if args.check:
            print("DRY RUN: Windows loopback socketpair allowed; external TCP denied. No changes made.")
            return 0
        patches = [
            (TRACE_PATH, "trace", OLD_GUARD, NEW_GUARD),
            (TEST_PATH, "audit_test", OLD_ASSERT, NEW_ASSERT),
        ]
        # Validate backups and replacement anchors for every file before any write.
        changes = []
        for path, name, old, new in patches:
            if states[name] == "patched":
                continue
            content, _, crlf = _read_and_hash(path)
            if content.count(old) != 1:
                raise RuntimeError(f"Unexpected replacement anchor: {path}")
            backup = path.with_name(path.name + ".before-windows-loopback-fix.bak")
            if backup.exists():
                raise RuntimeError(f"Backup already exists; refusing overwrite: {backup}")
            updated = content.replace(old, new, 1)
            expected = NEW_TRACE_HASH if name == "trace" else NEW_TEST_HASH
            if hashlib.sha256(updated.encode("utf-8")).hexdigest() != expected:
                raise RuntimeError(f"Patched source does not match expected hash: {path}")
            original_raw = path.read_bytes()
            target_raw = updated.replace("\n", "\r\n").encode("utf-8") if crlf else updated.encode("utf-8")
            changes.append((path, backup, original_raw, target_raw))
        for path, backup, original_raw, target_raw in changes:
            backup.write_bytes(original_raw)
            path.write_bytes(target_raw)
            print("PATCHED:", path.relative_to(ROOT))
        if _inspect() != {"trace": "patched", "audit_test": "patched"}:
            raise RuntimeError("Post-apply source validation failed")
        print("PASS: Offline guard now permits only numeric loopback addresses. No production code or cloud resources changed.")
        return 0
    except (OSError, UnicodeError, RuntimeError) as err:
        print("ERROR:", err)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
