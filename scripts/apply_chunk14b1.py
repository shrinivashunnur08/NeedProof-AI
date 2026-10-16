"""Guarded offline 14B.1 patch for audited 450a552 source; no cloud calls."""
from __future__ import annotations
import argparse
from hashlib import sha256
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACK = ROOT / "backend/app/cloud_decision_api.py"
FRONT = ROOT / "frontend/src/FreeShowcase.tsx"
ADDITIONS = [
    "backend/app/retail_forecast_14b1.py", "backend/tests/test_cloud_14b1.py",
    "frontend/src/components/RetailForecast14B1.tsx", "frontend/src/lib/retailForecast14b1.ts",
]
BASE_HASH = {
    "backend/app/cloud_decision_api.py":"cceb1bd130e2cc34ced4485158785fdc2431c4c91acd196906707b47e68e0d37",
    "frontend/src/FreeShowcase.tsx":"f355af0182a8ee23d24240921b3db6654e0d0efd8c0ee409886a47980f4a31cf",
}
BACK_ANCHOR = "from app.decision_orchestrator_14a3 import OrchestrationInput14A3, orchestrate_decision_14a3"
ROUTE_ANCHOR = '@app.post("/api/v1/decision/orchestrate")'
FRONT_ANCHOR = 'import DecisionOrchestrator14A3 from "./components/DecisionOrchestrator14A3";'
FRONT_JSX = "          <MerchantEvidenceDesk />"
NEW_IMPORT = "from app.retail_forecast_14b1 import ForecastInput14B1, evaluate_retail_forecast_14b1"
NEW_ROUTE = '@app.post("/api/v1/analytics/sales-forecast")'
NEW_FRONT = 'import RetailForecast14B1 from "./components/RetailForecast14B1";'
NEW_FLAG = 'import { retailForecast14b1Enabled } from "./lib/retailForecast14b1";'
NEW_TAG = "<RetailForecast14B1"


def abort(msg):
    raise SystemExit("STOP: " + msg + "\nNo cloud configuration, services, or source were changed by this failed preflight.")


def normalized(path):
    return path.read_text("utf-8-sig").replace("\r\n", "\n")


def main():
    p=argparse.ArgumentParser()
    m=p.add_mutually_exclusive_group(required=True)
    m.add_argument("--check",action="store_true")
    m.add_argument("--apply",action="store_true")
    args=p.parse_args()
    missing=[x for x in (BACK, FRONT, *(ROOT / a for a in ADDITIONS)) if not x.is_file()]
    if missing:
        abort("Missing package/source files. Extract into repository root: " + ", ".join(str(x.relative_to(ROOT)) for x in missing))
    back,front = normalized(BACK),normalized(FRONT)
    marks=[NEW_IMPORT in back,NEW_ROUTE in back,NEW_FRONT in front,NEW_FLAG in front,NEW_TAG in front]
    if all(marks):
        print("PASS: Chunk 14B.1 already integrated. Flags remain OFF by default.")
        return
    if any(marks):
        abort("Partial 14B.1 integration; do not overwrite manually")
    for path,content in ((BACK,back),(FRONT,front)):
        key=path.relative_to(ROOT).as_posix()
        if sha256(content.encode("utf-8")).hexdigest()!=BASE_HASH[key]:
            abort("Source drift from audited 450a552 source: " + key)
    for content,anchor in ((back,BACK_ANCHOR),(back,ROUTE_ANCHOR),(front,FRONT_ANCHOR),(front,FRONT_JSX)):
        if content.count(anchor)!=1:
            abort("Missing/duplicate integration anchor: " + anchor)
    route='''@app.post("/api/v1/analytics/sales-forecast")
def bounded_sales_forecast_14b1(payload: ForecastInput14B1, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("RETAIL_FORECAST_14B1_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Retail forecasting is disabled")
    return evaluate_retail_forecast_14b1(payload)


'''
    back=back.replace(BACK_ANCHOR,BACK_ANCHOR+"\n"+NEW_IMPORT,1)
    back=back.replace(ROUTE_ANCHOR,route+ROUTE_ANCHOR,1)
    front=front.replace(FRONT_ANCHOR,FRONT_ANCHOR+"\n"+NEW_FRONT+"\n"+NEW_FLAG,1)
    jsx='''          {retailForecast14b1Enabled && (
            <RetailForecast14B1 onEvent={recordEvent} />
          )}

          <MerchantEvidenceDesk />'''
    front=front.replace(FRONT_JSX,jsx,1)
    if back.count(NEW_ROUTE)!=1 or front.count(NEW_TAG)!=1:
        abort("Patch sanity check failed")
    print("PASS: Chunk 14B.1 anchors and SHA256 match reconstructed 450a552 baseline.")
    print("Would modify only backend/app/cloud_decision_api.py and frontend/src/FreeShowcase.tsx.")
    if args.check:
        print("DRY RUN: no source changes, cloud calls, flags, or charges.")
        return
    backup = ROOT / "backup_14b1"
    if backup.exists(): abort("backup_14b1 already exists; stop instead of overwriting")
    originals = {BACK:BACK.read_bytes(), FRONT:FRONT.read_bytes()}
    backup.mkdir()
    for path,data in originals.items():
        (backup / (path.name+".before_14b1")).write_bytes(data)
    try:
        for path,content in ((BACK,back),(FRONT,front)):
            tmp=path.with_name(path.name+".14b1.tmp")
            tmp.write_text(content,encoding="utf-8",newline="\n")
            os.replace(tmp,path)
    except Exception as exc:
        for path,raw in originals.items(): path.write_bytes(raw)
        abort("Write failed; originals restored (" + type(exc).__name__ + ")")
    print("SUCCESS: Chunk 14B.1 installed locally; API + React flags still OFF.")
    print("Backup folder: " + str(backup))
    print(r"NEXT: scripts\verify_chunk14b1.cmd")

if __name__=="__main__": main()
