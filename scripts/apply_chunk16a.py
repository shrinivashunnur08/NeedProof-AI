"""16A source-hash-guarded, local-only installer for the synthetic guided journey.

Only patches cloud_decision_api.py and FreeShowcase.tsx. All other files in the ZIP
are additions. No networking, shell-out, git mutation, env mutation, or cloud APIs.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACK = ROOT / "backend/app/cloud_decision_api.py"
FRONT = ROOT / "frontend/src/FreeShowcase.tsx"
ADDITIONS = [
    "backend/app/guided_journey_16a.py", "backend/tests/test_cloud_16a.py",
    "frontend/src/components/GuidedJourney16A.tsx", "frontend/src/lib/guidedJourney16a.ts",
]
EXPECTED_SHA = {
    "backend/app/cloud_decision_api.py": "094479fc808c647cbbe43f4340faedb2d926610107f6222b075229cbdc52a19e",
    "frontend/src/FreeShowcase.tsx": "b9fce0f5754c7ad54915a0d572c0e76f743750836a22c280f1677c63b413c34c",
}
IMPORT_ANCHOR = "from app.api_guard_15a import BoundedAPIGuard15A"
ROUTE_ANCHOR = '@app.post("/api/v1/analytics/command-center")'
UI_IMPORT_ANCHOR = 'import { biCommandCenter14b4Enabled } from "./lib/biCommandCenter14b4";'
UI_LAZY_ANCHOR = 'const BusinessCommandCenter14B4 = lazy(() => import("./components/BusinessCommandCenter14B4"));'
UI_PANEL_ANCHOR = '          {productGrounding13c1Enabled && ('
PATCH_FLAGS = (
    'from app.guided_journey_16a import GuidedJourneyInput16A, evaluate_guided_journey_16a',
    '@app.post("/api/v1/demo/guided-journey")',
    'import { guidedJourney16aEnabled } from "./lib/guidedJourney16a";',
    'const GuidedJourney16A = lazy(() => import("./components/GuidedJourney16A"));',
    '{guidedJourney16aEnabled && (',
)


def stop(reason: str):
    raise SystemExit("STOP: " + reason + "\nNo cloud configuration, feature flags, or deployment changed.")


def norm(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def once(value: str, token: str):
    if value.count(token) != 1:
        stop("Source anchor is missing or repeated: " + token[:90])


def main():
    parser=argparse.ArgumentParser(description="NeedProof 16A guarded local installer")
    choice=parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--check", action="store_true")
    choice.add_argument("--apply", action="store_true")
    args=parser.parse_args()
    required=[BACK, FRONT] + [ROOT/p for p in ADDITIONS]
    missing=[p for p in required if not p.is_file()]
    if missing:stop("Extract the ZIP into the project root; missing " + ", ".join(str(p.relative_to(ROOT)) for p in missing))

    backend=norm(BACK)
    frontend=norm(FRONT)
    seen=[PATCH_FLAGS[0] in backend, PATCH_FLAGS[1] in backend,
          PATCH_FLAGS[2] in frontend, PATCH_FLAGS[3] in frontend, PATCH_FLAGS[4] in frontend]
    if all(seen):
        for token in PATCH_FLAGS[:2]:once(backend,token)
        for token in PATCH_FLAGS[2:]:once(frontend,token)
        if 'GUIDED_JOURNEY_16A_ENABLED' not in backend or 'simulation_acknowledged' not in norm(ROOT/ADDITIONS[0]):
            stop("Partial/modified 16A implementation detected")
        print("PASS: 16A already installed; backend and frontend feature flags remain opt-in.")
        return
    if any(seen):stop("Partial 16A patch found. No automatic overwrite is allowed.")
    for p, original in ((BACK,backend),(FRONT,frontend)):
        relative=p.relative_to(ROOT).as_posix()
        if sha256(original.encode("utf-8")).hexdigest()!=EXPECTED_SHA[relative]:
            stop("Source SHA256 mismatch against 9104256 baseline: "+relative)
    for txt, marker in ((backend,IMPORT_ANCHOR),(backend,ROUTE_ANCHOR),
                        (frontend,UI_IMPORT_ANCHOR),(frontend,UI_LAZY_ANCHOR),(frontend,UI_PANEL_ANCHOR)):
        once(txt,marker)

    new_backend=backend.replace(IMPORT_ANCHOR,IMPORT_ANCHOR+'\n'+PATCH_FLAGS[0],1)
    new_backend=new_backend.replace(ROUTE_ANCHOR,'''@app.post("/api/v1/demo/guided-journey")
def guided_journey_16a(payload: GuidedJourneyInput16A, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("GUIDED_JOURNEY_16A_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Guided journey is disabled")
    return evaluate_guided_journey_16a(payload)


'''+ROUTE_ANCHOR,1)
    new_front=frontend.replace(UI_IMPORT_ANCHOR,PATCH_FLAGS[2]+'\n'+UI_IMPORT_ANCHOR,1)
    new_front=new_front.replace(UI_LAZY_ANCHOR,UI_LAZY_ANCHOR+'\n'+PATCH_FLAGS[3],1)
    new_front=new_front.replace(UI_PANEL_ANCHOR,'''          {guidedJourney16aEnabled && (
            <GuidedJourney16A onEvent={recordEvent} />
          )}

'''+UI_PANEL_ANCHOR,1)
    if any(new_backend.count(flag)!=1 for flag in PATCH_FLAGS[:2]):stop("Invalid proposed API integration")
    if any(new_front.count(flag)!=1 for flag in PATCH_FLAGS[2:]):stop("Invalid proposed React integration")
    print("PASS: 16A source SHA256 matches the reconstructed 9104256 baseline and anchors.")
    print("Would modify only backend/app/cloud_decision_api.py and frontend/src/FreeShowcase.tsx.")
    if args.check:
        print("DRY RUN: no changes, cloud calls, costs, or feature flags.")
        return

    backup=ROOT/"backup_16a"
    if backup.exists():stop("Backup folder already exists; preserve it and review manually")
    backup.mkdir()
    original={BACK:BACK.read_bytes(), FRONT:FRONT.read_bytes()}
    for p, raw in original.items():
        (backup/(p.name+".before_16a")).write_bytes(raw)
    try:
        for p,new in ((BACK,new_backend),(FRONT,new_front)):
            temporary=p.with_name(p.name+".16a.tmp")
            temporary.write_text(new, encoding="utf-8", newline="\n")
            os.replace(temporary,p)
    except Exception:
        for p,raw in original.items():p.write_bytes(raw)
        stop("Patch failed; previous files restored from in-memory copy")
    print("SUCCESS: Guided 16A experience integrated locally; release flags remain OFF by default.")
    print("Backups: "+str(backup))
    print(r"NEXT: scripts\verify_chunk16a.cmd")


if __name__=="__main__":
    main()
