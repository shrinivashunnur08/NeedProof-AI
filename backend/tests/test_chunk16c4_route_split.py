"""NeedProof 16C.4: route splitting is reversible and avoids internal eager imports."""
from __future__ import annotations
import importlib.util
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('np16c4', ROOT / 'scripts/apply_chunk16c4.py')
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_live_repo_installed_route_split():
    assert mod.state(ROOT) == 'installed'
    router = mod.read(ROOT / mod.APP)
    assert 'lazy(() => import("./FreeShowcase"))' in router
    assert 'lazy(() => import("./NeedProofWorkspace"))' in router
    assert 'lazy(() => import("./components/MerchantVerificationPage"))' in router
    assert 'VITE_PUBLIC_SHOWCASE === "true"' in router
    assert 'decodeURIComponent(window.location.hash.slice(1))' in router
    assert 'Suspense' in router and 'role="status"' in router


def test_internal_workspace_preserves_application():
    workspace = mod.read(ROOT / mod.WORKSPACE)
    assert mod.checksum(workspace) == mod.WORKSPACE_HASH
    if (ROOT / mod.BACKUP).exists():
        original = mod.read(ROOT / mod.BACKUP)
        assert mod.derive_workspace(original) == workspace
    derived = workspace
    assert 'export default function NeedProofWorkspace()' in derived
    assert 'export default function NeedProofRouter()' not in derived
    assert 'MerchantVerificationPage' not in derived
    assert 'FreeShowcase' not in derived


def test_second_apply_idempotent_and_preserves_files():
    app = mod.read(ROOT / mod.APP)
    workspace = mod.read(ROOT / mod.WORKSPACE)
    mod.apply(ROOT)
    assert mod.read(ROOT / mod.APP) == app
    assert mod.read(ROOT / mod.WORKSPACE) == workspace


def test_modified_router_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp)
        target = copy / mod.APP
        target.parent.mkdir(parents=True)
        shutil.copy2(ROOT / mod.APP, target)
        ws = copy / mod.WORKSPACE
        ws.write_text(mod.read(ROOT / mod.WORKSPACE), encoding='utf-8')
        target.write_text(mod.read(target) + '\n// drift', encoding='utf-8')
        try:
            mod.state(copy)
        except ValueError as e:
            assert 'Unexpected' in str(e)
        else:
            assert False, 'drift must stop installer'


def test_original_derivation_guard():
    source = mod.read(ROOT / mod.BACKUP) if (ROOT / mod.BACKUP).exists() else mod.read(ROOT / mod.APP)
    try:
        mod.derive_workspace(source.replace('function App() {', 'function Changed() {', 1))
    except ValueError:
        pass
    else:
        assert False, 'Tampered source must be rejected'


def test_router_contains_no_eager_workspace_or_cloud_imports():
    router = mod.read(ROOT / mod.APP)
    assert 'import NeedProofWorkspace from' not in router
    assert 'import FreeShowcase from' not in router
    assert 'firebase' not in router.lower()
    assert 'cloudDecisions' not in router


def test_purchase_safety_replay_untouched():
    import json
    replay = json.loads((ROOT / 'frontend/src/generated/needproof16cReplay.json').read_text(encoding='utf-8'))
    assert len(replay['scenarios']) == 4
    assert all(not v['purchase_allowed'] and not v['workflow']['purchase_allowed'] for v in replay['scenarios'].values())
