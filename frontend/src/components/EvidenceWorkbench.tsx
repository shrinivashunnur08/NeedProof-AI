import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRightLeft,
  CheckCircle2,
  ChevronRight,
  FlaskConical,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import {
  cloudApiUrl,
  requestCloudReplan,
  type CloudReplanInput,
} from "../lib/cloudDecisions";
import type { DecisionResult } from "./AdaptiveDecisionPanel";

type LabMerchant = {
  id: "LAB_STORE_A" | "LAB_STORE_B" | "LAB_STORE_C";
  price: number;
  stock: number;
  delivers: boolean;
};

type Props = {
  requestedProduct: string | null;
  extractedBudget: number | null;
  onEvent: (kind: string, message: string, source: "CLOUD_RUN" | "USER") => void;
};

const REFERENCE_PRODUCT = "65W USB-C PD laptop charger";
const DEFAULTS: LabMerchant[] = [
  { id: "LAB_STORE_A", price: 899, stock: 3, delivers: true },
  { id: "LAB_STORE_B", price: 950, stock: 5, delivers: true },
  { id: "LAB_STORE_C", price: 840, stock: 2, delivers: false },
];

type Preset = "reference" | "stock_out" | "delivery_update" | "quantity_pressure";

function makePreset(preset: Preset): { merchants: LabMerchant[]; quantity: number } {
  const merchants = DEFAULTS.map((merchant) => ({ ...merchant }));
  if (preset === "stock_out") merchants[0].stock = 0;
  if (preset === "delivery_update") merchants[2].delivers = true;
  return { merchants, quantity: preset === "quantity_pressure" ? 6 : 1 };
}

function limitInteger(value: number, min: number, max: number): number {
  return Number.isFinite(value) ? Math.min(max, Math.max(min, Math.trunc(value))) : min;
}

function money(amount: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

/**
 * This is a controlled, synthetic evidence lab. It is NOT a merchant portal,
 * real business discovery, or proof that the input claims are correct.
 * Computation is delegated to the existing authenticated FastAPI endpoint.
 */
export default function EvidenceWorkbench({ requestedProduct, extractedBudget, onEvent }: Props) {
  const [product, setProduct] = useState(REFERENCE_PRODUCT);
  const [budget, setBudget] = useState(1000);
  const [quantity, setQuantity] = useState(1);
  const [merchants, setMerchants] = useState<LabMerchant[]>(() => makePreset("reference").merchants);
  const [decision, setDecision] = useState<DecisionResult | null>(null);
  const [evaluationKey, setEvaluationKey] = useState("");
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef<AbortController | null>(null);

  const snapshotKey = JSON.stringify([product, budget, quantity, merchants]);
  const activeDecision = evaluationKey === snapshotKey ? decision : null;
  const cheapest = [...merchants].sort((a, b) => a.price - b.price)[0];
  const backendConfigured = cloudApiUrl.length > 0;

  useEffect(() => () => pending.current?.abort(), []);

  function invalidate() {
    pending.current?.abort();
    pending.current = null;
    setEvaluating(false);
    setDecision(null);
    setEvaluationKey("");
    setError("");
  }

  function applyPreset(preset: Preset) {
    invalidate();
    const next = makePreset(preset);
    setMerchants(next.merchants);
    setQuantity(next.quantity);
    setBudget(1000);
    setProduct(REFERENCE_PRODUCT);
    onEvent("LAB_PRESET", `Evidence workbench scenario: ${preset}. Synthetic offers only.`, "USER");
  }

  function loadGeminiIntent() {
    if (!requestedProduct) return;
    invalidate();
    setProduct(requestedProduct.slice(0, 180));
    setBudget(limitInteger(extractedBudget && extractedBudget > 0 ? extractedBudget : 1000, 100, 100000));
    const base = limitInteger(extractedBudget && extractedBudget > 0 ? extractedBudget : 1000, 100, 100000);
    setMerchants([
      { id: "LAB_STORE_A", price: Math.max(1, Math.round(base * 0.899)), stock: 3, delivers: true },
      { id: "LAB_STORE_B", price: Math.max(1, Math.round(base * 0.95)), stock: 5, delivers: true },
      { id: "LAB_STORE_C", price: Math.max(1, Math.round(base * 0.84)), stock: 2, delivers: false },
    ]);
    setQuantity(1);
    onEvent("LAB_INTENT_LOADED", "Loaded Gemini product and budget into an explicitly synthetic evidence case.", "USER");
  }

  function updateMerchant(id: LabMerchant["id"], change: Partial<Omit<LabMerchant, "id">>) {
    invalidate();
    setMerchants((previous) => previous.map((merchant) => merchant.id === id ? { ...merchant, ...change } : merchant));
  }

  async function evaluate() {
    if (!backendConfigured || evaluating) return;
    const productName = product.trim();
    if (productName.length < 3 || budget < 100 || quantity < 1) {
      setError("Enter a product, a budget of at least ₹100, and a positive quantity.");
      return;
    }
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setEvaluating(true);
    setError("");
    setDecision(null);
    setEvaluationKey("");
    const recordedAt = new Date().toISOString();
    const payload: CloudReplanInput = {
      customer: {
        product_query: productName,
        budget_minor: budget * 100,
        required_quantity: quantity,
        delivery_required: true,
      },
      merchants: merchants.map((merchant) => ({
        place_id: merchant.id,
        name: merchant.id,
        evidence: {
          product_query: productName,
          status: "REPORTED_UNVERIFIED",
          submission: {
            product_name: productName,
            stock_quantity: merchant.stock,
            price_minor: merchant.price * 100,
            currency: "INR",
            delivery_available: merchant.delivers,
            submitted_at: recordedAt,
          },
          assessment: {
            status: "REPORTED_UNVERIFIED",
            freshness: "RECENT_REPORT",
            eligible_for_commitment: false,
          },
        },
      })),
    };
    try {
      const result = await requestCloudReplan(payload, controller.signal);
      if (controller.signal.aborted) return;
      setDecision(result);
      setEvaluationKey(snapshotKey);
      onEvent("EVIDENCE_WORKBENCH", `Cloud Run evaluated three synthetic reports; provisional result: ${result.selected?.name ?? "none"}.`, "CLOUD_RUN");
    } catch (reason) {
      if (!controller.signal.aborted) {
        setError(reason instanceof Error ? reason.message : "Cloud Run decision failed.");
      }
    } finally {
      if (!controller.signal.aborted) setEvaluating(false);
    }
  }

  const changedFromCheapest = activeDecision?.selected && activeDecision.selected.place_id !== cheapest.id;

  return (
    <section id="evidence-workbench" aria-label="Evidence Intelligence Workbench" className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#111827] p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sky-400"><FlaskConical size={19}/><h2 className="text-base font-semibold text-white">Evidence Intelligence Workbench</h2></div>
          <p className="mt-2 max-w-3xl text-xs leading-5 text-slate-400">Investigate why the cheapest offer may not satisfy the customer. Adjust synthetic evidence and ask the actual Python engine on Cloud Run to evaluate it.</p>
        </div>
        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-[11px] font-semibold text-amber-200">SYNTHETIC · NOT MERCHANT VERIFIED</span>
      </div>
      <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] p-3 text-xs leading-5 text-amber-100/85">
        <div className="flex items-start gap-2"><ShieldAlert size={15} className="mt-0.5 shrink-0"/><p>All three LAB_STORE records are invented. Prices, inventory, delivery and report freshness are user-controlled fixtures, not Google Places results or actual merchant submissions. The backend evaluates the input; it does not independently verify it.</p></div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" onClick={() => applyPreset("reference")} className="rounded-lg border border-slate-600 px-3 py-2 text-xs text-slate-200 hover:bg-slate-800">Baseline</button>
        <button type="button" onClick={() => applyPreset("stock_out")} className="rounded-lg border border-slate-600 px-3 py-2 text-xs text-slate-200 hover:bg-slate-800">Stock-out</button>
        <button type="button" onClick={() => applyPreset("delivery_update")} className="rounded-lg border border-slate-600 px-3 py-2 text-xs text-slate-200 hover:bg-slate-800">New delivery evidence</button>
        <button type="button" onClick={() => applyPreset("quantity_pressure")} className="rounded-lg border border-slate-600 px-3 py-2 text-xs text-slate-200 hover:bg-slate-800">Quantity pressure</button>
        <button type="button" disabled={!requestedProduct} onClick={loadGeminiIntent} className="rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-300 disabled:opacity-40">Use Gemini request</button>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_150px_125px]">
        <label className="text-xs text-slate-300">Product <input maxLength={180} value={product} onChange={(event) => { invalidate(); setProduct(event.target.value); }} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"/></label>
        <label className="text-xs text-slate-300">Total budget (₹)<input type="number" min={100} max={100000} value={budget} onChange={(event) => { invalidate(); setBudget(limitInteger(Number(event.target.value), 100, 100000)); }} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"/></label>
        <label className="text-xs text-slate-300">Quantity<input type="number" min={1} max={20} value={quantity} onChange={(event) => { invalidate(); setQuantity(limitInteger(Number(event.target.value), 1, 20)); }} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"/></label>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        {merchants.map((merchant) => (
          <div key={merchant.id} className="rounded-xl border border-[#304058] bg-[#080F1B] p-3">
            <div className="flex items-center justify-between gap-2"><h3 className="text-sm font-semibold text-white">{merchant.id}</h3><span className="text-[10px] text-amber-200">LAB FIXTURE</span></div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <label className="text-[11px] text-slate-400">Price (₹)<input type="number" min={1} max={100000} value={merchant.price} onChange={(event) => updateMerchant(merchant.id, { price: limitInteger(Number(event.target.value), 1, 100000) })} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-2 text-sm text-white"/></label>
              <label className="text-[11px] text-slate-400">Reported stock<input type="number" min={0} max={500} value={merchant.stock} onChange={(event) => updateMerchant(merchant.id, { stock: limitInteger(Number(event.target.value), 0, 500) })} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-2 text-sm text-white"/></label>
            </div>
            <label className="mt-3 flex cursor-pointer items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={merchant.delivers} onChange={(event) => updateMerchant(merchant.id, { delivers: event.target.checked })} className="accent-sky-400"/> Reports delivery available</label>
            <p className="mt-3 text-[11px] text-slate-500">Modeled subtotal: {money(merchant.price * quantity)} · Not a real quote</p>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" disabled={!backendConfigured || evaluating} onClick={() => void evaluate()} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-sky-500 px-5 py-2.5 text-xs font-semibold text-slate-950 hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-45">{evaluating ? <RefreshCw size={16} className="animate-spin"/> : <ArrowRightLeft size={16}/>} {evaluating ? "Computing with Cloud Run..." : "Evaluate evidence on Cloud Run"}</button>
        {!backendConfigured && <p role="status" className="text-xs text-amber-200">Cloud Run API URL isn't configured. This workbench has no browser-based decision fallback.</p>}
        {evaluating && <p role="status" className="text-xs text-sky-200">Validating Firebase credentials and evaluating synthetic evidence...</p>}
      </div>
      {error && <p role="alert" className="mt-3 rounded-lg border border-rose-500/25 bg-rose-500/10 p-3 text-xs text-rose-200">Cloud API error: {error}. No result has been fabricated.</p>}

      {activeDecision && (
        <div aria-live="polite" className="mt-5 space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-slate-700 bg-[#080D17] p-4">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">Naive lowest-price baseline</p>
              <p className="mt-2 text-lg font-semibold">{cheapest.id} · {money(cheapest.price)}</p>
              <p className="mt-2 text-xs text-slate-400">Price-only comparison; ignores stock, delivery and quantity. Not a recommendation.</p>
            </div>
            <div className="rounded-xl border border-sky-500/30 bg-[#091B2B] p-4">
              <p className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-sky-300"><CheckCircle2 size={13}/> Python constraint decision</p>
              <p className="mt-2 text-lg font-semibold">{activeDecision.selected?.name ?? "No provisional offer"}</p>
              <p className="mt-2 text-xs text-slate-300">{activeDecision.selected?.reported_subtotal_minor != null ? `${money(activeDecision.selected.reported_subtotal_minor / 100)} reported subtotal` : "Further merchant evidence or alternatives needed"}</p>
              {changedFromCheapest && <p className="mt-2 text-xs font-semibold text-amber-200">Decision differs from cheapest-first because constraints or evidence matter.</p>}
            </div>
          </div>
          <div className="rounded-xl border border-slate-700 bg-[#080D17] p-4">
            <p className="text-xs font-semibold text-white">Backend evaluation reasoning</p>
            <p className="mt-2 break-words text-xs text-sky-300">Next suggested action: {activeDecision.recommended_next_action.replaceAll("_", " ")}</p>
            <div className="mt-3 grid gap-2 lg:grid-cols-3">
              {activeDecision.candidates.map((candidate) => (
                <div key={candidate.place_id} className="min-w-0 rounded-lg border border-slate-700 p-3">
                  <p className="break-words text-xs font-semibold">{candidate.name}</p>
                  <p className="mt-1 text-[11px] text-slate-300">{candidate.status}</p>
                  <p className="mt-2 break-words text-[11px] text-amber-200">{candidate.reasons.length ? candidate.reasons.join(" · ") : "No modeled exclusion"}</p>
                  {!!candidate.evidence_gaps?.length && <p className="mt-2 break-words text-[11px] text-slate-400">Still missing: {candidate.evidence_gaps.join(" · ")}</p>}
                </div>
              ))}
            </div>
            <p className="mt-3 flex items-start gap-2 text-[11px] leading-5 text-amber-200/85"><AlertTriangle size={13} className="mt-0.5 shrink-0"/> Server-side evaluation does not establish authenticity, reported-stock truth or purchase authorization. This result is provisional.</p>
          </div>
          <p className="flex items-center gap-1 text-[11px] text-slate-500"><ChevronRight size={12}/> Source: authenticated Cloud Run `/api/v1/decision/replan`; no cached browser recommendation.</p>
        </div>
      )}
    </section>
  );
}
