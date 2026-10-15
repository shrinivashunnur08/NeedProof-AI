"""NeedProof Chunk 13B.1 guarded installer. From repo root:
   python scripts/apply_chunk13b1.py --check
   python scripts/apply_chunk13b1.py --apply
No cloud resources are created by this script.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend/app/cloud_decision_api.py"
DISCOVERY = ROOT / "frontend/src/components/RealStoresDiscovery.tsx"
REQUIREMENTS = ROOT / "backend/requirements-cloud.txt"
NEW_FILES = [
    "backend/app/merchant_evidence_13b.py",
    "backend/tests/test_cloud_13b.py",
    "backend/scripts/init_13b_schema.py",
    "backend/scripts/grant_13b_merchant.py",
    "frontend/src/lib/evidence13b.ts",
]
EXPECTED = {
    "backend/app/cloud_decision_api.py": "e935ca90d904664ea23bd443936fb8f4ec3839392111f7bd02c367a784832f24",
    "frontend/src/components/RealStoresDiscovery.tsx": "c170ac746bc0c7411190935dc3e6f282f5f4745ffb3fad8defb0ac5bcfac7ce9",
    "backend/requirements-cloud.txt": "84a64ce307a1c1ee5064f1d47fba27a1ac8ab71569b7a7e0f9cfb35e47505dd2",
}


def fail(msg):
    sys.exit("STOP: " + msg + "\nNo source files modified by this invocation.")


def replace_once(content, marker, replacement, filename):
    if content.count(marker) != 1:
        fail(f"Unexpected anchor in {filename}: {marker!r}. Do not force apply.")
    return content.replace(marker, replacement, 1)


def patched_sources():
    sources = {}
    for name, expected in EXPECTED.items():
        file = ROOT / name
        if not file.is_file():
            fail("Required file missing: " + name)
        actual = hashlib.sha256(file.read_bytes()).hexdigest()
        if actual != expected:
            fail(f"File differs from uploaded commit 9ae32a1: {name}. Send current file for a safe rebase; don't overwrite changes.")
        sources[name] = file.read_text(encoding="utf-8-sig")

    for name in NEW_FILES:
        if not (ROOT / name).is_file():
            fail("Extract the ZIP to the repo root. Missing: " + name)

    backend_name = "backend/app/cloud_decision_api.py"
    backend = sources[backend_name]
    backend = replace_once(
        backend,
        "from app.public_places import DiscoveryInput, discover_stores",
        "from app.public_places import DiscoveryInput, discover_stores\nfrom app.merchant_evidence_13b import router as evidence_13b_router",
        backend_name,
    )
    backend = replace_once(backend, '@app.post("/api/v1/discovery/stores")', 'app.include_router(evidence_13b_router)\n\n\n@app.post("/api/v1/discovery/stores")', backend_name)
    sources[backend_name] = backend

    requirements_name = "backend/requirements-cloud.txt"
    requirements = sources[requirements_name].rstrip("\r\n") + "\n"
    for line in [
        "sqlalchemy>=2,<3", "pydantic-settings>=2,<3", "cloud-sql-python-connector[pg8000]>=1.12,<2",
    ]:
        if not any(x.strip().casefold() == line.casefold() for x in requirements.splitlines()):
            requirements += line + "\n"
    sources[requirements_name] = requirements

    component_name = "frontend/src/components/RealStoresDiscovery.tsx"
    component = sources[component_name]
    component = replace_once(
        component,
        'import { discoverRealStores, type DiscoveryResult } from "../lib/storeDiscovery";',
        'import { discoverRealStores, type DiscoveryResult, type StoreCandidate } from "../lib/storeDiscovery";\nimport { createEvidenceInquiry, getEvidenceInquiry, evidence13bEnabled, type EvidenceInquiry13B } from "../lib/evidence13b";',
        component_name,
    )
    component = replace_once(
        component,
        '  const abort = useRef<AbortController | null>(null);',
        '''  const abort = useRef<AbortController | null>(null);
  const [tracked, setTracked] = useState<Record<string, EvidenceInquiry13B>>({});
  const [trackingPlace, setTrackingPlace] = useState<string | null>(null);
  const [trackingError, setTrackingError] = useState("");''',
        component_name,
    )
    component = replace_once(
        component,
        '  function importGemini() {',
        '''  useEffect(() => {
    if (!result || !evidence13bEnabled) return;
    const controller = new AbortController();
    for (const store of result.stores) {
      // Store only the stable Place ID and our own inquiry ID. No Maps name/address caching.
      let inquiryId: string | null = null;
      try { inquiryId = window.localStorage.getItem(`np13b:${store.place_id}`); } catch { /* private browsing */ }
      if (!inquiryId) continue;
      void getEvidenceInquiry(inquiryId, controller.signal).then((item) => {
        if (!controller.signal.aborted && item.product_query === product.trim()) {
          setTracked((previous) => ({ ...previous, [store.place_id]: item }));
        }
      }).catch(() => { /* Saved reference may belong to another signed-in user. */ });
    }
    return () => controller.abort();
  }, [result, product]);

  async function trackStore(store: StoreCandidate) {
    if (trackingPlace) return;
    setTrackingPlace(store.place_id);
    setTrackingError("");
    try {
      const inquiry = await createEvidenceInquiry(store.place_id, product);
      setTracked((previous) => ({ ...previous, [store.place_id]: inquiry }));
      try { window.localStorage.setItem(`np13b:${store.place_id}`, inquiry.inquiry_id); } catch { /* optional */ }
      onEvent("EVIDENCE_INQUIRY", "Evidence tracking record created. No merchant was contacted.", "CLOUD_RUN");
    } catch (exc) {
      setTrackingError(exc instanceof Error ? exc.message : "Could not create an evidence record.");
    } finally {
      setTrackingPlace(null);
    }
  }

  async function refreshStore(store: StoreCandidate) {
    const inquiry = tracked[store.place_id];
    if (!inquiry || trackingPlace) return;
    setTrackingPlace(store.place_id);
    setTrackingError("");
    try {
      const next = await getEvidenceInquiry(inquiry.inquiry_id);
      setTracked((previous) => ({ ...previous, [store.place_id]: next }));
      onEvent("EVIDENCE_REFRESH", "Retrieved the latest merchant evidence history from Cloud Run.", "CLOUD_RUN");
    } catch (exc) {
      setTrackingError(exc instanceof Error ? exc.message : "Could not refresh evidence.");
    } finally {
      setTrackingPlace(null);
    }
  }

  function importGemini() {''',
        component_name,
    )
    component = replace_once(
        component,
        '    setError("");\n    setResult(null);\n    try {',
        '    setError("");\n    setResult(null);\n    setTracked({});\n    try {',
        component_name,
    )
    component = replace_once(
        component,
        '    setResult(null);\n    setError("");\n    onEvent("DISCOVERY_INPUTS",',
        '    setResult(null);\n    setTracked({});\n    setError("");\n    onEvent("DISCOVERY_INPUTS",',
        component_name,
    )
    component = replace_once(
        component,
        '      {error && <p role="alert" className="mt-4 rounded-lg border border-rose-500/25 p-3 text-xs text-rose-300">{error}</p>}',
        '      {error && <p role="alert" className="mt-4 rounded-lg border border-rose-500/25 p-3 text-xs text-rose-300">{error}</p>}\n      {trackingError && <p role="alert" className="mt-4 rounded-lg border border-rose-500/25 p-3 text-xs text-rose-300">{trackingError}</p>}',
        component_name,
    )
    component = replace_once(
        component,
        '                {store.maps_url && <a className="mt-3 inline-flex items-center gap-2 text-xs font-medium text-sky-300 hover:text-sky-200" href={store.maps_url} target="_blank" rel="noopener noreferrer">View business on Google Maps <ExternalLink size={13}/></a>}',
        '''                {store.maps_url && <a className="mt-3 inline-flex items-center gap-2 text-xs font-medium text-sky-300 hover:text-sky-200" href={store.maps_url} target="_blank" rel="noopener noreferrer">View business on Google Maps <ExternalLink size={13}/></a>}
                {evidence13bEnabled && (
                  <div className="mt-3 border-t border-slate-700/70 pt-3 text-xs">
                    {!tracked[store.place_id] ? (
                      <button type="button" disabled={Boolean(trackingPlace)} onClick={() => void trackStore(store)} className="rounded-lg border border-sky-500/40 px-3 py-2 text-sky-200 disabled:opacity-40">
                        {trackingPlace === store.place_id ? "Creating record..." : "Track missing merchant evidence"}
                      </button>
                    ) : (
                      <div className="space-y-2">
                        <p className="font-semibold text-sky-200">{tracked[store.place_id].status.replace(/_/g, " ")}</p>
                        <p className="text-slate-400">{tracked[store.place_id].current_report
                          ? `Merchant-reported stock: ${tracked[store.place_id].current_report?.stock_quantity}; not independently verified.`
                          : "No merchant response. Creating an inquiry does not contact the store."}</p>
                        {tracked[store.place_id].current_report && <p className="text-slate-400">Decision: {tracked[store.place_id].replanning.candidates[0]?.status ?? "UNKNOWN"}. Next: {tracked[store.place_id].replanning.recommended_next_action.replace(/_/g, " ")}.</p>}
                        <p className="text-slate-500">{tracked[store.place_id].history.length} recorded update(s). Never a purchase authorization.</p>
                        <button type="button" disabled={Boolean(trackingPlace)} onClick={() => void refreshStore(store)} className="rounded-lg border border-slate-600 px-3 py-2 text-sky-200 disabled:opacity-40">Refresh evidence</button>
                      </div>
                    )}
                  </div>
                )}''',
        component_name,
    )
    sources[component_name] = component
    return sources


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if 'evidence_13b_router' in APP.read_text(encoding='utf-8-sig'):
        sys.exit("13B.1 integration already appears installed. Verify tests; this installer is one-time only.")
    staged = patched_sources()  # Every check happens before any write.
    if args.check:
        print("PASS: source hashes and patch anchors match uploaded commit 9ae32a1.")
        print("Would patch:", ", ".join(staged))
        print("New modules are in place; no source was modified.")
        return
    backup = ROOT / "backup_13b1"
    if backup.exists():
        fail("backup_13b1 already exists; won't overwrite prior backups")
    backup.mkdir()
    for rel in staged:
        dest = backup / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    written = []
    try:
        for rel, content in staged.items():
            path = ROOT / rel
            temp = path.with_name(path.name + ".13b1.tmp")
            temp.write_text(content, encoding="utf-8")
            temp.replace(path)
            written.append(rel)
    except Exception:
        for rel in written:
            shutil.copy2(backup / rel, ROOT / rel)
        raise
    print("SUCCESS: Chunk 13B.1 source integrated. Originals saved under backup_13b1.")
    print("Feature stays OFF until schema and runtime configuration are ready.")


if __name__ == "__main__":
    main()
