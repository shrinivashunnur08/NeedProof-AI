"""Read-only guarded compatibility preflight for the offline-only 15B benchmark.
Never installs dependencies, patches code, calls Google APIs, or changes flags.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import argparse
import subprocess

ROOT=Path(__file__).resolve().parents[1]
EXPECTED={
    'backend/app/cloud_decision_api.py':'094479fc808c647cbbe43f4340faedb2d926610107f6222b075229cbdc52a19e',
    'backend/app/product_retrieval_13c2.py':'7ac5d15c69ed0f4de769bb332d0424410991c6b875b31d89ee34e47fbb4b1898',
    'backend/app/evidence_planner_14a1.py':'bf9d79001a3d5db8d3aea20024f9233ae85b06b55406854938a80393cb3482dd',
    'backend/app/basket_optimizer_14a2.py':'ff1013c71919edc57e67e2a1b936dfbb77edfba17b4757d8b3f7d1bd802fb99c',
    'backend/app/retail_forecast_14b1.py':'9bd87f96c1a2b0fe660bf27f893a84e44377fce98b4c98032750a106a02ecb8b',
    'backend/app/api_guard_15a.py':'ea9a807b2cc3deb09a6f3305d37f3018cf94e1b4e935b1a85963290258ac5e34',
}
ADD=(
    'backend/benchmarks_15b/__init__.py',
    'backend/benchmarks_15b/runner.py',
    'backend/benchmarks_15b/fixtures.json',
    'backend/tests/test_benchmark_15b.py',
    'scripts/run_benchmarks15b.py',
    'scripts/run_benchmarks15b.cmd',
    'scripts/verify_chunk15b.cmd',
)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true',required=True)
    parser.parse_args()
    missing=[p for p in (*EXPECTED,*ADD) if not (ROOT/p).is_file()]
    if missing:
        raise SystemExit('STOP: Missing files (extract ZIP into project root): '+', '.join(missing))
    for rel,expected in EXPECTED.items():
        text=(ROOT/rel).read_text(encoding='utf-8-sig').replace('\r\n','\n').encode('utf-8')
        if sha256(text).hexdigest()!=expected:
            raise SystemExit('STOP: Source fingerprint mismatch; inspect before proceeding: '+rel)
    try:
        proc=subprocess.run(['git','rev-parse','--short=7','HEAD'],cwd=ROOT,capture_output=True,text=True,timeout=5)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise SystemExit('STOP: Git baseline could not be checked: '+str(exc))
    if proc.returncode!=0 or proc.stdout.strip()!='5a47898':
        raise SystemExit('STOP: Expected Git HEAD 5a47898; got '+repr(proc.stdout.strip())+'; do not proceed blindly')
    print('PASS: Chunk 15B evaluated source fingerprints and Git HEAD 5a47898.')
    print('PASS: Read-only benchmark-only files; no existing API/frontend files modified.')
    print('DRY RUN: no network calls, cloud resource changes, flags, data persistence, or charges.')

if __name__=='__main__':
    main()
