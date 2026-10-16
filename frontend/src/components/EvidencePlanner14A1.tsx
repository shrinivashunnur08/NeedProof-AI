import { useState, type FormEvent } from "react";
import { BrainCircuit, ShieldAlert } from "lucide-react";
import { evidence13bEnabled, getEvidenceInquiry, type EvidenceInquiry13B } from "../lib/evidence13b";
import { requestEvidencePlan14A1, type EvidencePlan14A1Result, type EvidenceProposal14A1 } from "../lib/evidencePlanner14a1";

type Props = { requestedProduct: string | null; extractedBudget: number | null;
  onEvent: (kind: string, message: string, source: "CLOUD_RUN" | "USER") => void };

type CandidateInput = { id: string; name: string; price: string; prior: string; response: string; cost: string; delay: string; compatibility: EvidenceProposal14A1["compatibility_status"] };
const defaults: CandidateInput[] = [
  { id: "sample_candidate_a", name: "Illustrative candidate A", price: "720", prior: "0.65", response: "0.80", cost: "8", delay: "3", compatibility: "UNKNOWN" },
  { id: "sample_candidate_b", name: "Illustrative candidate B", price: "870", prior: "0.75", response: "0.85", cost: "6", delay: "2", compatibility: "UNKNOWN" },
];
const box = "mt-1 w-full min-w-0 rounded-lg border border-slate-700 bg-[#080D17] px-3 py-2 text-sm text-slate-100";

export default function EvidencePlanner14A1({ requestedProduct, extractedBudget, onEvent }: Props) {
  const [product, setProduct] = useState("65W USB-C PD charger");
  const [budget, setBudget] = useState("1000");
  const [deadline, setDeadline] = useState("15");
  const [candidates, setCandidates] = useState<CandidateInput[]>(defaults);
  const [inquiryId, setInquiryId] = useState("");
  const [linkedInquiry, setLinkedInquiry] = useState<EvidenceInquiry13B | null>(null);
  const [result, setResult] = useState<EvidencePlan14A1Result | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);

  function edit(index: number, name: keyof CandidateInput, value: string) {
    setCandidates(old => old.map((c,i) => i === index ? {...c,[name]: value} : c));
    setLinkedInquiry(null); setResult(null);
  }
  async function importInquiry() {
    if (!evidence13bEnabled) return;
    setError(""); setPending(true);
    try {
      const inquiry = await getEvidenceInquiry(inquiryId.trim());
      if (inquiry.product_query !== product.trim()) throw new Error("Inquiry product must match the planning request exactly.");
      setCandidates(old => old.map((c, i) => i === 0 ? {
        ...c, id: inquiry.place_id, name: "Merchant evidence candidate (Place ID)",
        price: inquiry.current_report?.price_minor ? (inquiry.current_report.price_minor / 100).toString() : c.price,
      } : c));
      setLinkedInquiry(inquiry);
      onEvent("PLANNER_INQUIRY_LINKED", "Loaded an authorized merchant evidence inquiry for hypothetical verification planning.", "CLOUD_RUN");
    } catch (ex) { setError(ex instanceof Error ? ex.message : "Inquiry import failed."); }
    finally { setPending(false); }
  }
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(""); setPending(true); setResult(null);
    try {
      const minor = (v:string) => Math.round(Number(v)*100);
      const totalBudget = minor(budget);
      if (!Number.isFinite(totalBudget) || totalBudget <= 0 || totalBudget > 100_000_000) throw new Error("Provide a valid positive INR budget.");
      const merchants = candidates.map((c,i) => {
        const report = i === 0 && linkedInquiry ? linkedInquiry.current_report : null;
        return { place_id: c.id.trim(), name: c.name.trim(), evidence: report ? {
          product_query: linkedInquiry!.product_query, status: "REPORTED_UNVERIFIED" as const,
          submission: {product_name: linkedInquiry!.product_query, stock_quantity: report.stock_quantity,
            price_minor: report.price_minor, currency: report.currency, delivery_available: report.delivery_available,
            submitted_at: report.recorded_at},
          assessment: {status: "REPORTED_UNVERIFIED", freshness: "RECENT_REPORT", eligible_for_commitment: false as const},
        } : null };
      });
      const proposals: EvidenceProposal14A1[] = candidates.map(c => ({
        place_id: c.id.trim(), indicative_price_minor: minor(c.price),
        assumed_prior_feasible: Number(c.prior), assumed_response_probability: Number(c.response),
        verification_cost_minor: minor(c.cost), verification_delay_minutes: Number(c.delay),
        compatibility_status: c.compatibility, source_reference_ids: [], signals: [],
      }));
      const output = await requestEvidencePlan14A1({
        snapshot: {customer: {product_query: product.trim(), budget_minor: totalBudget,
          required_quantity: 1, delivery_required: false}, merchants},
        proposals, deadline_minutes: Number(deadline), assumption_acknowledged: true,
      });
      setResult(output);
      onEvent("HYPOTHETICAL_EVSI_14A1", "Ranked uncalibrated verification actions against customer-entered evidence; no merchant contacted.", "CLOUD_RUN");
    } catch (ex) {setError(ex instanceof Error ? ex.message : "Verification planning failed.");}
    finally {setPending(false);}
  }
  return <section id="evidence-planner-14a1" className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#111827] p-4 sm:p-5">
    <div className="flex gap-2 items-center"><BrainCircuit size={18} className="text-sky-400"/><h2 className="font-semibold">Active Evidence Planner · Bayesian / EVSI</h2></div>
    <p className="mt-2 text-xs leading-6 text-slate-300">Compare what to verify next using the existing decision engine. Priors, response rates and costs are <strong>hypothetical user assumptions</strong>, not calibrated model scores. A reported merchant claim or pasted product excerpt is never proof of inventory or compatibility.</p>
    <button className="mt-3 rounded border border-slate-600 px-3 py-2 text-xs text-sky-300 disabled:opacity-40" disabled={!requestedProduct}
      onClick={()=>{if(requestedProduct)setProduct(requestedProduct);if(extractedBudget!==null)setBudget(String(extractedBudget));setResult(null);}}
      type="button">Use current Gemini product and budget</button>
    <form onSubmit={e => void submit(e)} className="mt-4 space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-xs text-slate-300">Requested product<input className={box} required maxLength={250} minLength={3} value={product} onChange={e=>{setProduct(e.target.value); setLinkedInquiry(null);setResult(null);}}/></label>
        <label className="text-xs text-slate-300">Budget (₹)<input className={box} type="number" required min={1} max={1000000} value={budget} onChange={e=>setBudget(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Verification deadline (minutes)<input className={box} type="number" required min={0} max={120} value={deadline} onChange={e=>setDeadline(e.target.value)}/></label>
      </div>
      {candidates.map((c,i) => <div key={i} className="rounded-xl border border-slate-700 bg-[#0A101B] p-3">
        <p className="mb-2 text-sm font-semibold">Candidate {i+1} {i===0 && linkedInquiry ? "· authorized 13B inquiry linked" : "· entered estimate"}</p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs text-slate-300">Place/reference ID<input className={box} value={c.id} maxLength={300} required onChange={e=>edit(i,"id",e.target.value)}/></label>
          <label className="text-xs text-slate-300">Candidate label<input className={box} value={c.name} required onChange={e=>edit(i,"name",e.target.value)}/></label>
          <label className="text-xs text-slate-300">Indicative price (₹)<input className={box} type="number" required min={1} value={c.price} onChange={e=>edit(i,"price",e.target.value)}/></label>
          <label className="text-xs text-slate-300">Specification status<select className={box} value={c.compatibility} onChange={e=>edit(i,"compatibility",e.target.value)}><option value="UNKNOWN">Unknown</option><option value="CONDITIONAL_SPEC_MATCH">Conditional spec match (unverified)</option><option value="REPORTED_SPEC_MISMATCH">Reported mismatch</option><option value="INSUFFICIENT_SPEC_INPUT">Missing specifications</option><option value="INSUFFICIENT_SOURCE_EVIDENCE">Source evidence missing</option></select></label>
          <label className="text-xs text-slate-300">Assumed feasibility prior (0–1)<input className={box} type="number" min={0} max={1} step="0.01" value={c.prior} onChange={e=>edit(i,"prior",e.target.value)}/></label>
          <label className="text-xs text-slate-300">Assumed response rate (0–1)<input className={box} type="number" min={0} max={1} step="0.01" value={c.response} onChange={e=>edit(i,"response",e.target.value)}/></label>
          <label className="text-xs text-slate-300">Verify cost (₹)<input className={box} type="number" min={0} max={1000} value={c.cost} onChange={e=>edit(i,"cost",e.target.value)}/></label>
          <label className="text-xs text-slate-300">Delay (minutes)<input className={box} type="number" min={0} max={120} value={c.delay} onChange={e=>edit(i,"delay",e.target.value)}/></label>
        </div>
      </div>)}
      {evidence13bEnabled && <div className="rounded-lg border border-slate-700 p-3">
        <label className="text-xs text-slate-300">Optional: existing 13B inquiry ID (your authorized inquiry)<input className={box} placeholder="UUID" maxLength={36} value={inquiryId} onChange={e=>setInquiryId(e.target.value)}/></label>
        <button disabled={pending || !inquiryId.trim()} type="button" onClick={()=>void importInquiry()} className="mt-2 rounded border border-sky-500/50 px-3 py-2 text-xs text-sky-300 disabled:opacity-40">Import merchant-reported evidence as candidate 1</button>
        {linkedInquiry && <p className="mt-2 text-xs text-amber-200">Evidence linked; it remains merchant-reported and unverified. No merchant is contacted.</p>}
      </div>}
      <label className="flex gap-2 items-start text-xs text-amber-200"><input type="checkbox" className="mt-0.5" checked={acknowledged} onChange={e=>setAcknowledged(e.target.checked)}/><span>I understand that all priors, reliability assumptions and EVSI utilities are hypothetical; these are not measured real-world probabilities.</span></label>
      <button type="submit" disabled={pending || !acknowledged} className="rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-semibold text-slate-950 disabled:opacity-40">{pending ? "Planning…" : "Calculate next evidence action"}</button>
    </form>
    {error && <p role="alert" className="mt-3 text-sm text-rose-300">{error}</p>}
    {result && <div className="mt-4 space-y-3" aria-live="polite">
      <div className="flex items-center gap-2 text-amber-200 text-xs"><ShieldAlert size={15}/>HYPOTHETICAL / UNCALIBRATED · NO PURCHASE AUTHORIZED</div>
      <p className="text-sm font-semibold">{result.recommended_action_id ? `Next test: ${result.recommended_action_id}` : "No positive feasible verification action under current assumptions"}</p>
      <div className="grid gap-2 sm:grid-cols-2">{result.actions.map(a=><article key={a.action_id} className="rounded-lg border border-slate-700 bg-[#080D17] p-3 text-xs"><p className="font-semibold text-sky-200">{a.merchant}</p><p className="mt-1 text-slate-300">Assumed net value: ₹{a.net_evsi_inr}</p>{a.skip_reason && <p className="mt-1 text-amber-300">Excluded from ranking: {a.skip_reason.replace(/_/g," ")}</p>}</article>)}</div>
      <p className="text-xs text-slate-400">Evidence now: {result.snapshot_replanning.recommended_next_action.replace(/_/g," ")}. The model does not independently authenticate stores, stock or documents.</p>
      <details className="text-xs text-slate-400"><summary className="cursor-pointer text-sky-300">Model limitations and assumptions</summary><ul className="mt-2 list-disc pl-5 space-y-1">{result.assumptions.map((a,i)=><li key={i}>{a}</li>)}</ul></details>
    </div>}
  </section>;
}
