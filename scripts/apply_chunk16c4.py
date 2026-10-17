"""Guarded NeedProof 16C.4 route-level startup split; local filesystem only."""
from __future__ import annotations
import argparse
import hashlib
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_HASH = "0957f78df3bf3e630f9bd278a1a34f175d40a5d689711dc8b22051936271453a"
WORKSPACE_HASH = "e344ae2bbc0bedc9baa7f8730f6ed930d39aa321ef323aa248c8921196760a3e"
ROUTER_HASH = "46a19a2dc907e2b161feba651d4a6346dec6f96d756d0580472d98fe3194652b"
APP = Path("frontend/src/App.tsx")
WORKSPACE = Path("frontend/src/NeedProofWorkspace.tsx")
BACKUP = Path("backup_16c4_route_split/App.tsx")
TAIL = 'export default function NeedProofRouter() {\n  if (import.meta.env.VITE_PUBLIC_SHOWCASE === "true") {\n    return <FreeShowcase />;\n  }\n  const match = window.location.pathname.match(/^\\/verify\\/(\\d+)\\/?$/);\n\n  if (match) {\n    return (\n      <MerchantVerificationPage\n        requestId={Number(match[1])}\n        token={decodeURIComponent(window.location.hash.slice(1))}\n      />\n    );\n  }\n\n  return <App />;\n}\n'
ROUTER = 'import { lazy, Suspense } from "react";\n\n// Only the selected route is fetched. No workspace/merchant module is\n// eagerly downloaded by the public judge-facing showcase.\nconst FreeShowcase = lazy(() => import("./FreeShowcase"));\nconst NeedProofWorkspace = lazy(() => import("./NeedProofWorkspace"));\nconst MerchantVerificationPage = lazy(() => import("./components/MerchantVerificationPage"));\n\nfunction RouteLoading() {\n  return (\n    <div\n      role="status"\n      aria-live="polite"\n      className="flex min-h-dvh items-center justify-center bg-[#090E18] px-4 text-sm text-slate-300"\n    >\n      Loading NeedProof…\n    </div>\n  );\n}\n\nexport default function NeedProofRouter() {\n  // Preserve the previous precedence: showcase mode wins over verify routes.\n  if (import.meta.env.VITE_PUBLIC_SHOWCASE === "true") {\n    return <Suspense fallback={<RouteLoading />}><FreeShowcase /></Suspense>;\n  }\n  const match = window.location.pathname.match(/^\\/verify\\/(\\d+)\\/?$/);\n  if (match) {\n    return (\n      <Suspense fallback={<RouteLoading />}>\n        <MerchantVerificationPage\n          requestId={Number(match[1])}\n          token={decodeURIComponent(window.location.hash.slice(1))}\n        />\n      </Suspense>\n    );\n  }\n  return <Suspense fallback={<RouteLoading />}><NeedProofWorkspace /></Suspense>;\n}\n'


def normalized(data: str) -> str:
    return data.replace("\r\n", "\n")


def read(path: Path) -> str:
    return normalized(path.read_text(encoding="utf-8"))


def checksum(data: str) -> str:
    return hashlib.sha256(normalized(data).encode("utf-8")).hexdigest()


def derive_workspace(text: str) -> str:
    if checksum(text) != BASELINE_HASH or not text.endswith(TAIL):
        raise ValueError("App.tsx does not match the audited f765eff source; no modification made")
    changes = (
        ('import MerchantVerificationPage from "./components/MerchantVerificationPage";\n', ''),
        ('import FreeShowcase from "./FreeShowcase";\n', ''),
        ('function App() {', 'export default function NeedProofWorkspace() {'),
    )
    updated = text[:-len(TAIL)]
    for before, after in changes:
        if updated.count(before) != 1:
            raise ValueError(f"Expected unique source anchor missing: {before!r}")
        updated = updated.replace(before, after, 1)
    if checksum(updated) != WORKSPACE_HASH:
        raise ValueError("Workspace derivation mismatch; refused")
    return updated


def state(root: Path) -> str:
    if not (root / APP).is_file():
        raise ValueError("Missing frontend/src/App.tsx")
    app = read(root / APP)
    workspace = root / WORKSPACE
    if checksum(app) == BASELINE_HASH:
        if workspace.exists():
            raise ValueError("Workspace path already exists; refusing overwrite")
        derive_workspace(app)
        return "original"
    if checksum(app) == ROUTER_HASH and workspace.is_file() and checksum(read(workspace)) == WORKSPACE_HASH:
        # Existing legacy backup may be absent, but do not rebuild source.
        return "installed"
    raise ValueError("Unexpected App/workspace content. Keep local edits; inspect before proceeding")


def apply(root: Path) -> None:
    current = state(root)
    if current == "installed":
        print("PASS: 16C.4 already installed; no changes")
        return
    original = read(root / APP)
    workspace = derive_workspace(original)
    backup = root / BACKUP
    if backup.exists():
        raise ValueError("Backup already exists; refusing to overwrite: " + str(backup))
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / APP, backup)
    if checksum(read(backup)) != BASELINE_HASH:
        raise ValueError("Backup integrity check failed; no app changes")
    # Only App.tsx and new workspace are edited; this is reversible from backup.
    (root / WORKSPACE).write_text(workspace, encoding="utf-8", newline="\n")
    (root / APP).write_text(ROUTER, encoding="utf-8", newline="\n")
    assert state(root) == "installed"
    print("SUCCESS: The public showcase, merchant verification and workspace now load as separate routes.")
    print("Backup:", backup)
    print("NO Firebase, Cloud Run, token, flag, billing or deployment change")


def measure(root: Path) -> None:
    # A report, not an automated performance claim. Measures generated startup entry only.
    html = root / 'frontend/dist/index.html'
    if not html.is_file():
        raise ValueError("Build frontend with npm run build before --report")
    source = html.read_text(encoding='utf-8')
    candidates = re.findall(r'<script[^>]+src=["\']([^"\']+\.js)["\']', source)
    if not candidates:
        raise ValueError("No script entry located in built index.html")
    entry = candidates[0].split('/assets/')[-1]
    js = root / 'frontend/dist/assets' / entry
    if not js.is_file():
        raise ValueError("Build entry missing: " + str(js))
    import gzip
    raw = len(js.read_bytes())
    gz = len(gzip.compress(js.read_bytes(), compresslevel=9))
    report = root / 'qa_reports/16c4/performance.md'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# NeedProof 16C.4 — Local frontend entry report\n\n"
        "- Build mode: **public showcase** (VITE_PUBLIC_SHOWCASE=true).\n"
        f"- Initial JavaScript entry: `{js.name}`\n"
        f"- JavaScript entry: **{raw/1000:.2f} kB** (decimal); **{gz/1000:.2f} kB** gzip.\n"
        "- Previously reported entry: about **901.73 kB** before route splitting, built in the older environment. "
        "Treat this as a directional comparison, not a controlled performance benchmark.\n"
        "- This is **bundle size**, not a measured browser startup time or total network transfer.\n"
        "- Need manual Chrome DevTools Lighthouse tests on mobile, with cache off and before/after comparisons.\n"
        "- Real cloud/Auth/Firestore remain **unverified**. No deployment was performed.\n",
        encoding='utf-8', newline='\n'
    )
    print(f"PUBLIC BUILD entry: {raw/1000:.2f} kB JS, {gz/1000:.2f} kB gzip")
    print("Report:", report)


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument('--check', action='store_true')
    commands.add_argument('--apply', action='store_true')
    commands.add_argument('--report', action='store_true')
    args = parser.parse_args()
    try:
        if args.report:
            measure(ROOT)
        elif args.check:
            current = state(ROOT)
            print('PASS: 16C.4 audited App.tsx:', current)
            print('Route split: public showcase / merchant verification / internal workspace')
            print('No network requests, API flags, deployments or billing changes')
        else:
            apply(ROOT)
        return 0
    except (ValueError, OSError) as err:
        print('STOP:', err)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
