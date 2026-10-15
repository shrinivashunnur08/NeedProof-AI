import { useEffect, useRef, useState } from "react";
import { Building2, ExternalLink, MapPin, Search, ShieldAlert } from "lucide-react";
import { cloudApiUrl } from "../lib/cloudDecisions";
import { discoverRealStores, type DiscoveryResult, type StoreCandidate } from "../lib/storeDiscovery";
import { createEvidenceInquiry, getEvidenceInquiry, evidence13bEnabled, type EvidenceInquiry13B } from "../lib/evidence13b";

type Props = {
  requestedProduct: string | null;
  location: string | null;
  onEvent: (kind: string, message: string, source: "CLOUD_RUN" | "USER") => void;
};

/** Live Google Places discovery: businesses only, no inferred merchant evidence. */
export default function RealStoresDiscovery({ requestedProduct, location, onEvent }: Props) {
  const [product, setProduct] = useState(requestedProduct ?? "65W USB-C laptop charger");
  const [area, setArea] = useState(location ?? "Thane, Maharashtra");
  const [result, setResult] = useState<DiscoveryResult | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const abort = useRef<AbortController | null>(null);
  const [tracked, setTracked] = useState<Record<string, EvidenceInquiry13B>>({});
  const [trackingPlace, setTrackingPlace] = useState<string | null>(null);
  const [trackingError, setTrackingError] = useState("");

  useEffect(() => () => abort.current?.abort(), []);

  useEffect(() => {
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

  function importGemini() {
    if (!requestedProduct) return;
    abort.current?.abort();
    setProduct(requestedProduct.slice(0, 120));
    if (location) setArea(location.slice(0, 80));
    setResult(null);
    setTracked({});
    setError("");
    onEvent("DISCOVERY_INPUTS", "Loaded Gemini-extracted product/location for candidate-business discovery.", "USER");
  }

  async function runSearch() {
    if (pending || !cloudApiUrl) return;
    const controller = new AbortController();
    abort.current?.abort();
    abort.current = controller;
    setPending(true);
    setError("");
    setResult(null);
    setTracked({});
    try {
      const next = await discoverRealStores(product, area, controller.signal);
      if (controller.signal.aborted) return;
      setResult(next);
      onEvent("STORE_DISCOVERY", `Google Places returned ${next.stores.length} candidate businesses; stock unverified.`, "CLOUD_RUN");
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Store discovery failed.");
    } finally {
      if (!controller.signal.aborted) setPending(false);
    }
  }

  return (
    <section id="real-store-discovery" className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#111827] p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-widest text-sky-400">Live merchant discovery</p>
          <h2 className="mt-2 flex items-center gap-2 text-lg font-semibold"><Building2 size={18} /> Find candidate businesses</h2>
        </div>
        <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-200">STOCK NOT VERIFIED</span>
      </div>
      <p className="mt-2 max-w-3xl text-xs leading-6 text-slate-400">
        Searches actual Google Maps business listings through authenticated Cloud Run. A business listing does not prove that a product is sold, in stock, compatible, or deliverable.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <label className="text-xs text-slate-300">Product/category
          <input value={product} maxLength={120} onChange={(e) => { setProduct(e.target.value); setResult(null); }} className="mt-2 w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm text-white" />
        </label>
        <label className="text-xs text-slate-300">City or area
          <input value={area} maxLength={80} onChange={(e) => { setArea(e.target.value); setResult(null); }} className="mt-2 w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm text-white" />
        </label>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" onClick={() => void runSearch()} disabled={pending || !cloudApiUrl || product.trim().length < 3 || area.trim().length < 2} className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-sky-500 px-4 py-2.5 text-xs font-semibold text-slate-950 disabled:opacity-40"><Search size={15} />{pending ? "Searching businesses..." : "Discover real stores"}</button>
        <button type="button" onClick={importGemini} disabled={!requestedProduct || pending} className="rounded-lg border border-slate-700 px-4 py-2.5 text-xs text-slate-200 disabled:opacity-40">Use Gemini request</button>
      </div>
      {!cloudApiUrl && <p className="mt-3 text-xs text-amber-300">Cloud Run URL not configured. Real discovery is disabled.</p>}
      {error && <p role="alert" className="mt-4 rounded-lg border border-rose-500/25 p-3 text-xs text-rose-300">{error}</p>}
      {trackingError && <p role="alert" className="mt-4 rounded-lg border border-rose-500/25 p-3 text-xs text-rose-300">{trackingError}</p>}
      {result && (
        <div className="mt-5 space-y-3" aria-live="polite">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold text-slate-200">{result.stores.length} candidate businesses</p>
            <span translate="no" className="whitespace-nowrap text-sm font-medium text-slate-300">Google Maps</span>
          </div>
          {!result.stores.length && <p className="text-sm text-slate-400">No matching business listings found. Try a broader category or a different area.</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            {result.stores.map((store) => (
              <article key={store.place_id} className="min-w-0 rounded-xl border border-[#304058] bg-[#0A101B] p-4">
                <h3 className="break-words text-sm font-semibold">{store.name}</h3>
                <p className="mt-2 flex items-start gap-2 break-words text-xs leading-5 text-slate-400"><MapPin size={13} className="mt-0.5 shrink-0" />{store.address || "Address not provided"}</p>
                <p className="mt-3 flex items-center gap-2 text-[11px] text-amber-300"><ShieldAlert size={13}/> Inventory, compatibility and delivery: unknown</p>
                {store.maps_url && <a className="mt-3 inline-flex items-center gap-2 text-xs font-medium text-sky-300 hover:text-sky-200" href={store.maps_url} target="_blank" rel="noopener noreferrer">View business on Google Maps <ExternalLink size={13}/></a>}
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
                )}
              </article>
            ))}
          </div>
          <p className="text-[11px] leading-5 text-slate-400">{result.disclaimer} Business results are displayed temporarily; this interface does not save Maps-sourced names or addresses to Firestore.</p>
        </div>
      )}
    </section>
  );
}
