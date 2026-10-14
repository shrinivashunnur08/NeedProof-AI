"""Install Chunk 13A into the current 12C dashboard and Cloud Run API.

Safely checks anchors, writes backups, and refuses partial installation.
Run: python scripts\\apply_chunk13a.py  (from repo root).
"""
from pathlib import Path
import os
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / 'frontend/src/FreeShowcase.tsx'
BACK = ROOT / 'backend/app/cloud_decision_api.py'
REQUIRED = [
    ROOT / 'frontend/src/components/RealStoresDiscovery.tsx',
    ROOT / 'frontend/src/lib/storeDiscovery.ts',
    ROOT / 'backend/app/public_places.py',
]


def fail(reason: str):
    sys.exit('ERROR: ' + reason + '\nNo project source files were modified.')


if not FRONT.exists() or not BACK.exists() or any(not p.exists() for p in REQUIRED):
    fail('Missing expected files. Extract ZIP into the NeedProof project ROOT.')
frontend = FRONT.read_text('utf-8-sig')
backend = BACK.read_text('utf-8-sig')
new_import = 'import RealStoresDiscovery from "./components/RealStoresDiscovery";'
back_import = 'from app.public_places import DiscoveryInput, discover_stores'
route_marker = '@app.post("/api/v1/discovery/stores")'

if new_import in frontend and '<RealStoresDiscovery' in frontend and back_import in backend and route_marker in backend:
    print('Already installed; no changes necessary.')
    sys.exit(0)
if any([new_import in frontend, '<RealStoresDiscovery' in frontend, back_import in backend, route_marker in backend]):
    fail('Partial installation found. Upload current files for a tailored patch.')

old_front_import = 'import EvidenceWorkbench from "./components/EvidenceWorkbench";'
if frontend.count(old_front_import) != 1:
    fail('Could not find the imported EvidenceWorkbench. Confirm 12C is installed.')
if not re.search(r'\b(recordEvent|onEvent)\b', frontend):
    fail('Journey event callback missing.')
if len(re.findall(r'<EvidenceWorkbench\b', frontend)) != 1:
    fail('Expected exactly one EvidenceWorkbench instance.')
frontend = frontend.replace(old_front_import, old_front_import + '\n' + new_import, 1)

# A component immediately before the evidence workbench; no fragile CSS matches.
match = re.search(r'(?m)^([ \t]*)<EvidenceWorkbench\b', frontend)
if not match:
    fail('Cannot locate workbench JSX insertion point.')
indent = match.group(1)
jsx = (
    f'{indent}<RealStoresDiscovery\n'
    f'{indent}  requestedProduct={{isCurrent && intent ? intent.requested_product : null}}\n'
    f'{indent}  location={{isCurrent && intent ? intent.delivery_location : null}}\n'
    f'{indent}  onEvent={{recordEvent}}\n'
    f'{indent}/>\n\n'
)
frontend = frontend[:match.start()] + jsx + frontend[match.start():]

# Mobile/sidebar anchors: inject based on accessible nav labels, not class names.
added = 0
for label, link in [
    ('Showcase workspace', '<a href="#real-store-discovery" className="block rounded-lg border border-sky-500/20 bg-sky-500/5 px-3 py-3 text-xs text-sky-300">Discover Real Stores</a>'),
    ('Mobile showcase navigation', '<a href="#real-store-discovery" className="shrink-0 rounded-lg border border-sky-500/25 px-3 py-2 text-xs text-sky-200">Real Stores</a>'),
]:
    matches = list(re.finditer(r'<nav\b(?=[^>]*aria-label=[\'"]' + re.escape(label) + r'[\'"])[^>]*>', frontend, re.DOTALL))
    if len(matches) > 1:
        fail(f'Unexpected duplicate navigation container: {label}')
    if matches:
        anchor = matches[0]
        start = frontend.rfind('\n', 0, anchor.start()) + 1
        nav_indent = re.match(r'[ \t]*', frontend[start:]).group(0)
        frontend = frontend[:anchor.end()] + '\n' + nav_indent + '  ' + link + frontend[anchor.end():]
        added += 1

# Update old text that inaccurately labels discovery as local-only.
frontend = frontend.replace(
    'Real store discovery<br/>Merchant evidence<br/>Commerce optimizer',
    'Merchant evidence<br/>Commerce optimizer',
)
old_back_import = 'from app.api.decisions import demo_evidence_plan'
if backend.count(old_back_import) != 1:
    fail('Backend API import anchor differs; do not overwrite your backend.')
if backend.count('@app.get("/health")') != 1:
    fail('Backend health route anchor differs; do not overwrite your backend.')
backend = backend.replace(old_back_import, old_back_import + '\n' + back_import, 1)
backend = backend.replace('@app.get("/health")',
    '@app.post("/api/v1/discovery/stores")\n'
    'async def candidate_store_discovery(payload: DiscoveryInput, user_id: Identity, response: Response):\n'
    '    response.headers["Cache-Control"] = "no-store"\n'
    '    return await discover_stores(payload, user_id)\n\n\n'
    '@app.get("/health")', 1)

# Validate everything before touching existing files.
assert frontend.count(new_import) == 1
assert backend.count(route_marker) == 1
backup = ROOT / 'backup_13a'
backup.mkdir(exist_ok=True)
for existing in (FRONT, BACK):
    dest = backup / (existing.name + '.before_13a')
    if dest.exists():
        fail(f'Backup exists: {dest}. Installer will not overwrite it.')
for existing in (FRONT, BACK):
    shutil.copy2(existing, backup / (existing.name + '.before_13a'))
for filename, content in ((FRONT, frontend), (BACK, backend)):
    temp = filename.with_name(filename.name + '.13a.tmp')
    temp.write_text(content, encoding='utf-8')
    os.replace(temp, filename)
print('SUCCESS: Chunk 13A integrated into FreeShowcase and Cloud Decision API.')
print(f'Navigation links inserted: {added}/2')
print('Originals backed up to:', backup)
print('Next: run backend tests and npm run build before deployment.')
