import { useRef, useState, type FormEvent } from "react";
import { GitMerge, ShieldAlert, RefreshCw } from "lucide-react";
import { orchestrate14a3, type Orchestration14A3 } from "../lib/decisionOrchestrator14a3";

type Props = { requestedProduct: string | null; extractedBudget: number | null;
  onEvent: (kind:string, message:string, source:"CLOUD_RUN"|"USER") => void };
type Snapshot = { customer: {product_query:string;budget_minor:number;required_quantity:number;delivery_required:boolean};
  merchants: Array<{place_id:string;name:string;evidence?:unknown}> };
const field = "mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] px-3 py-2 text-sm text-slate-100";
const example = "USB PD supported. Output 20V/3250mA. Cable 5A rated.";

export default function DecisionOrchestrator14A3({requestedProduct, extractedBudget, onEvent}: Props) {
  const [product,setProduct] = useState("65W USB-C PD charger");
  const [budget,setBudget] = useState("1000");
  const [stock,setStock] = useState("1");
  const [researchOn,setResearchOn] = useState(true);
  const [conflicting,setConflicting] = useState(false);
  const [excerpt,setExcerpt] = useState(example);
  const [evsiOn,setEvsiOn] = useState(true);
  const [basketOn,setBasketOn] = useState(true);
  const [ack,setAck] = useState(false);
  const [pending,setPending] = useState(false);
  const [result,setResult] = useState<Orchestration14A3|null>(null);
  const [error,setError] = useState("");
  const previous = useRef<Snapshot|null>(null);
  const revision = useRef(0);
  const previousReport = useRef<{quantity:string;stamp:string}|null>(null);
  const execute = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setError(""); setPending(true);
    try {
      const amount = Math.round(Number(budget)*100);
      const qty = Number(stock);
      if (!product.trim() || !Number.isSafeInteger(amount) || amount<1 || amount>100_000_000 ||
          !Number.isInteger(qty) || qty<0 || qty>20) throw new Error("Enter a valid product, budget and stock quantity.");
      const now = new Date().toISOString();
      const reportStamp = previousReport.current?.quantity === stock ? previousReport.current.stamp : now;
      const snapshot:Snapshot = {customer:{product_query:product.trim(),budget_minor:amount,required_quantity:1,delivery_required:false},merchants:[
        {place_id:"illustrative_store_a",name:"Illustrative Store A",evidence:{product_query:product.trim(),status:"REPORTED_UNVERIFIED",submission:{product_name:product.trim(),stock_quantity:qty,price_minor:72000,currency:"INR",delivery_available:true,submitted_at:reportStamp},assessment:{status:"REPORTED_UNVERIFIED",freshness:"RECENT_REPORT",eligible_for_commitment:false}}},
        {place_id:"illustrative_store_b",name:"Illustrative Store B"},
      ]};
      const research = researchOn ? {query:`${product.trim()} power delivery specifications`, review:{
        product_label: product.trim(),device_model:"Illustrative laptop",device_supports_usb_pd:true,
        required_power_w:65,required_voltage_v:20,sources:[
          {source_id:"excerpt_a", title:"User supplied sample passage",captured_at:now,excerpt:excerpt.trim(),facts:[]},
          ...(conflicting ? [{source_id:"excerpt_b",title:"Contradictory sample passage",captured_at:now,excerpt:"USB PD not supported. Output 20V/3250mA. Cable 5A rated.",facts:[]}] : []),
        ]}} : null;
      const verification = evsiOn ? {snapshot,proposals:[
        {place_id:"illustrative_store_a",assumed_prior_feasible:"0.65",assumed_response_probability:"0.80",verification_cost_minor:800,verification_delay_minutes:3,compatibility_status:"UNKNOWN",indicative_price_minor:72000},
        {place_id:"illustrative_store_b",assumed_prior_feasible:"0.70",assumed_response_probability:"0.85",verification_cost_minor:700,verification_delay_minutes:2,compatibility_status:"UNKNOWN",indicative_price_minor:82000},
      ],deadline_minutes:15,assumption_acknowledged:true} : null;
      const basket = basketOn ? {items:[{item_id:"charger",name:"Illustrative charger",quantity:1}],merchants:[
        {merchant_id:"synthetic_1",name:"Synthetic merchant",fulfillment_fee_minor:5000}],offers:[
        {sku:"fixture_1",item_id:"charger",merchant_id:"synthetic_1",product_name:"Synthetic charger",unit_price_minor:60000,stock_on_hand:2,delivery_eta_minutes:10,merchant_verified:true,stock_verified:true,compatibility_verified:true,delivery_verified:true,evidence_source:"SIMULATION_VERIFIED"},
        {sku:"reported_1",item_id:"charger",merchant_id:"synthetic_1",product_name:"Unverified cheap claim",unit_price_minor:20000,stock_on_hand:99,delivery_eta_minutes:2,merchant_verified:true,stock_verified:true,compatibility_verified:true,delivery_verified:true,evidence_source:"MERCHANT_REPORTED_UNVERIFIED"},
      ],budget_minor:amount,deadline_minutes:60,max_merchants:1,hypothetical_scenario_acknowledged:true} : null;
      const data = await orchestrate14a3({snapshot,previous_snapshot:previous.current,product_research:research,
        verification_plan:verification,basket_scenario:basket,client_revision:revision.current,simulation_acknowledged:true});
      previous.current = snapshot; previousReport.current = {quantity:stock,stamp:reportStamp}; revision.current += 1;
      setResult(data);
      onEvent("EVIDENCE_ORCHESTRATED_14A3",`14A.3 recomputed state ${data.workflow_state} without purchases or merchant contact.`,"CLOUD_RUN");
    } catch (ex) { setError(ex instanceof Error?ex.message:"Orchestration failed."); }
    finally { setPending(false); }
  };
  return <section id="orchestrator-14a3" className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#111827] p-4 sm:p-5 space-y-3">
    <div className="flex items-center gap-2"><GitMerge size={18} className="text-sky-300"/><h2 className="font-semibold">Evidence-to-Decision Orchestrator</h2></div>
    <p className="text-xs leading-6 text-slate-300">One guarded workflow combines document review, merchant snapshot replanning, assumed EVSI verification and a separate synthetic basket. Change the reported quantity or add conflicting excerpts, then recompute to see the decision change. All sample stores are fictitious.</p>
    <form className="space-y-3" onSubmit={e=>void execute(e)}>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-xs text-slate-300">Product<input required minLength={3} maxLength={150} className={field} value={product} onChange={e=>setProduct(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Budget (₹)<input required type="number" min={1} max={1000000} className={field} value={budget} onChange={e=>setBudget(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Store A reported units<input type="number" min={0} max={20} className={field} value={stock} onChange={e=>setStock(e.target.value)}/></label>
      </div>
      <button type="button" className="rounded border border-slate-600 px-3 py-1.5 text-xs text-sky-300 disabled:opacity-40" disabled={!requestedProduct} onClick={()=>{if(requestedProduct) setProduct(requestedProduct); if(extractedBudget && extractedBudget>0) setBudget(String(extractedBudget));}}>Use current request</button>
      <div className="flex flex-wrap gap-4 text-xs text-slate-300">
        <label className="flex items-center gap-2"><input type="checkbox" checked={researchOn} onChange={e=>setResearchOn(e.target.checked)}/>Document review</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={evsiOn} onChange={e=>setEvsiOn(e.target.checked)}/>Hypothetical EVSI</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={basketOn} onChange={e=>setBasketOn(e.target.checked)}/>Synthetic basket</label>
      </div>
      {researchOn && <div className="space-y-2">
        <label className="block text-xs text-slate-300">User-supplied demo specification excerpt<textarea required minLength={10} maxLength={2000} rows={2} className={field} value={excerpt} onChange={e=>setExcerpt(e.target.value)}/></label>
        <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={conflicting} onChange={e=>setConflicting(e.target.checked)}/>Inject contradictory sample text to test escalation</label>
      </div>}
      <label className="flex items-start gap-2 text-xs text-amber-200"><input className="mt-0.5" type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>All stores, probability assumptions and basket fixtures are illustrative. No live stock, automated outreach or purchasing.</label>
      <button type="submit" disabled={!ack||pending} className="inline-flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40"><RefreshCw size={15}/>{pending?"Recomputing…":"Run / replan workflow"}</button>
    </form>
    {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
    {result && <div className="space-y-3" aria-live="polite">
      <p className="flex items-center gap-2 text-xs text-amber-200"><ShieldAlert size={15}/>NO PURCHASE · UNVERIFIED INPUTS · DETERMINISTIC WORKFLOW</p>
      <div className="rounded-lg border border-sky-500/25 bg-sky-500/5 p-3"><p className="text-sm font-semibold text-sky-200">{result.workflow_state.replace(/_/g," ")}</p><p className="mt-1 text-xs">Next action: {result.recommended_next_action.replace(/_/g," ")}</p><p className="mt-1 text-xs text-slate-400">{result.reason}</p></div>
      <div className="grid gap-2 md:grid-cols-2">{result.workflow_trace.map(step=><article key={step.stage} className="rounded border border-slate-700 bg-[#080D17] p-3 text-xs"><p className="font-semibold">{step.stage.replace(/_/g," ")}</p><p className="mt-1 text-slate-300">{step.status} · {step.state}</p><p className="mt-1 text-slate-500">{step.source.replace(/_/g," ")}</p></article>)}</div>
      <p className="text-xs text-slate-300">Evidence changes: {result.change_detection.changed === null ? "First calculation" : result.change_detection.changed ? result.change_detection.changes.map(c=>c.event.replace(/_/g," ")).join(", ") : "No client-input changes"}.</p>
      {result.product_research && <p className="text-xs text-slate-300">Supplied product evidence: {result.product_research.review.status.replace(/_/g," ")} · {result.product_research.passages.length} cited passages (source authenticity not checked).</p>}
      {result.hypothetical_verification_plan && <p className="text-xs text-slate-300">Assumed EVSI next: {result.hypothetical_verification_plan.recommended_action_id ?? "none"} (uncalibrated).</p>}
      {result.synthetic_basket_scenario && <p className="text-xs text-slate-300">Separate basket fixture: {result.synthetic_basket_scenario.scenario_status}; {result.synthetic_basket_scenario.verification_backlog.length} excluded unverified offer(s).</p>}
      <details className="text-xs text-slate-400"><summary className="cursor-pointer text-sky-300">Limitations and transparency</summary><ul className="mt-2 list-disc pl-4 space-y-2">{result.limitations.map((t,i)=><li key={i}>{t}</li>)}</ul></details>
    </div>}
  </section>;
}
