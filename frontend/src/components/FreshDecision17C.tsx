import {useEffect, useRef, useState, type FormEvent} from "react";
import {fresh17CEnabled, local17C, runFresh17C, type FreshResult17C, type Simulation17C} from "../lib/freshJourney17c";

const readable = (s: string) => s.toLowerCase().replace(/_/g, " ");

export default function FreshDecision17C() {
  const [product, setProduct] = useState("65W USB-C PD laptop charger");
  const [budget, setBudget] = useState(1000);
  const [price, setPrice] = useState(720);
  const [location, setLocation] = useState("Thane");
  const [report, setReport] = useState<Simulation17C>("reported_offer");
  const [ack, setAck] = useState(false);
  const [result, setResult] = useState<FreshResult17C | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    controller.current?.abort();
    const next = new AbortController(); controller.current = next;
    setError(""); setBusy(true); setResult(null);
    try {
      const data = await runFresh17C({
        product_query: product.trim(), budget_inr: budget, location_note: location.trim(),
        reported_price_inr: price, simulated_report: report, simulation_acknowledged: true,
      }, next.signal);
      if (controller.current === next) setResult(data);
    } catch (cause) {
      if (!next.signal.aborted && controller.current === next)
        setError(cause instanceof Error ? cause.message : "The fresh decision failed.");
    } finally { if (controller.current === next) {setBusy(false); controller.current = null;} }
  }
  function invalidate() { controller.current?.abort(); setBusy(false); setResult(null); setError(""); }

  return <section aria-label="Fresh Python decision execution" id="fresh-decision-17c"
    className="space-y-4 rounded-2xl border border-cyan-700/60 bg-[#111827] p-4 sm:p-5">
    <div className="flex flex-wrap justify-between gap-2">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-cyan-300">Chunk 17C · Fresh decision execution</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Change the request. Recompute the evidence.</h2>
      </div>
      <span className="self-start rounded-full border border-amber-500/40 px-3 py-1 text-xs text-amber-200">FICTIONAL MERCHANT · NOT REAL INVENTORY</span>
    </div>
    <p className="text-sm leading-6 text-slate-300">Enter your own product and budget. The request is evaluated by the real Python orchestration engine, using an adjustable <strong>fictional</strong> merchant report. These fields are entered manually—Gemini extraction and real store discovery are <strong>not used</strong> in this run.</p>
    {!fresh17CEnabled && <p role="status" className="rounded-lg border border-slate-700 bg-slate-950 p-3 text-xs text-amber-200">Fresh API disabled. Run the dedicated local developer configuration to activate it; public cloud mode needs protected deployment and explicit flags.</p>}
    <form onSubmit={e => void submit(e)} className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-slate-300">Product / requirement<input required minLength={3} maxLength={160} value={product} onChange={e=>{invalidate();setProduct(e.target.value);}}
          className="mt-1 w-full rounded-lg border border-slate-600 bg-[#080D17] p-2 text-sm text-white"/></label>
        <label className="text-xs text-slate-300">Location note (not searched)<input value={location} maxLength={80} onChange={e=>{invalidate();setLocation(e.target.value);}}
          className="mt-1 w-full rounded-lg border border-slate-600 bg-[#080D17] p-2 text-sm text-white"/></label>
        <label className="text-xs text-slate-300">Budget (₹)<input type="number" required min={100} max={100000} step={1} value={budget} onChange={e=>{invalidate();setBudget(e.target.valueAsNumber);}}
          className="mt-1 w-full rounded-lg border border-slate-600 bg-[#080D17] p-2 text-sm text-white"/></label>
        <label className="text-xs text-slate-300">Fictional reported price (₹)<input type="number" required min={1} max={100000} step={1} value={price} onChange={e=>{invalidate();setPrice(e.target.valueAsNumber);}}
          className="mt-1 w-full rounded-lg border border-slate-600 bg-[#080D17] p-2 text-sm text-white"/></label>
      </div>
      <label className="block text-xs text-slate-300">What-if merchant evidence
        <select value={report} onChange={e=>{invalidate();setReport(e.target.value as Simulation17C);}}
          className="mt-1 w-full rounded-lg border border-slate-600 bg-[#080D17] p-2 text-sm text-white">
          <option value="reported_offer">Fictional report: 1 unit</option>
          <option value="stockout">Fictional update: 0 units (vs illustrative previous 1)</option>
          <option value="no_merchants">No merchant records provided</option>
        </select>
      </label>
      <label className="flex gap-2 text-xs leading-5 text-amber-200"><input type="checkbox" checked={ack} onChange={e=>{invalidate();setAck(e.target.checked);}} />I understand all merchant claims are fictional and no purchase can be approved.</label>
      <button type="submit" disabled={!fresh17CEnabled || !ack || busy} className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">{busy ? "Recomputing Python…" : "Execute fresh Python decision"}</button>
      <span className="ml-3 text-xs text-slate-400">{local17C ? "Local Vite → FastAPI" : "Firebase-protected cloud mode (when enabled)"}</span>
    </form>
    {error && <p role="alert" className="rounded-lg bg-rose-950 p-3 text-sm text-rose-200">{error}</p>}
    {result && <div aria-live="polite" className="space-y-3 rounded-xl border border-slate-700 p-4">
      <p className="text-xs font-bold uppercase text-cyan-300">Python result · {readable(result.workflow.workflow_state)}</p>
      <p className="text-sm text-slate-200">{result.workflow.reason}</p>
      <p className="text-xs text-amber-200">Next: {readable(result.workflow.recommended_next_action)}</p>
      <p className="text-xs text-slate-400">Selected candidate: {result.workflow.merchant_replanning.selected?.name ?? "None"} · Purchase allowed: NO</p>
      <p className="break-all text-xs text-slate-500">Snapshot SHA-256: {result.workflow.snapshot_sha256}</p>
      {result.workflow.change_detection.changed && <p className="text-xs text-amber-200">Hypothetical change: {result.workflow.change_detection.changes.map(c=>readable(c.event)).join(", ")}</p>}
      <h3 className="text-sm font-semibold text-white">Five-stage backend trace</h3>
      <ol className="grid gap-2 sm:grid-cols-2">{result.workflow.workflow_trace.map((step,i)=><li key={step.stage} className="rounded-lg bg-[#080D17] p-2 text-xs text-slate-300">{i+1}. {readable(step.stage)}<span className="block text-cyan-200">{readable(step.state)} · {readable(step.status)}</span></li>)}</ol>
      <p className="text-xs text-slate-400">No Gemini, merchant contact, independent inventory verification, geosearch, persistence or checkout. Document, EVSI and basket stages may show NOT PROVIDED.</p>
    </div>}
  </section>;
}
