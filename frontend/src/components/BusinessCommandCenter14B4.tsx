import { useState, type FormEvent } from "react";
import { BarChart3, ClipboardList, RefreshCcw, ShieldAlert, TrendingUp } from "lucide-react";
import { evaluateBI14B4, type BIInput14B4, type BIResult14B4 } from "../lib/biCommandCenter14b4";

const inputClass="mt-1 w-full rounded-lg border border-slate-600 bg-[#080D17] p-3 font-mono text-xs text-slate-100";
function demo():BIInput14B4 {
  return {
    as_of:new Date().toISOString().slice(0,10),synthetic_demo:true,
    forecast:{sku_code:"DEMO-SKU",projected_sales_units:53.4,horizon_days:7,backtest_wape_pct:17.5,reported_stockout_days:2},
    inventory:{sku_code:"DEMO-SKU",reported_on_hand_units:25,balance_mismatches:1,cross_day_gaps:0,unusual_sales_days:2,modeled_lead_time_shortfall_units:14.6},
    cohorts:{anonymous_profile_count:48,aggregate_cohort_count:2,minimum_cohort_size:9,association_rule_count:3},
    verification:{candidates_considered:4,unresolved_evidence_items:2,provisional_candidates:3},
  };
}
function priorityLabel(value:number){return value===1?"Review first":value===2?"Review soon":"Complete coverage";}
export default function BusinessCommandCenter14B4({onEvent}:{onEvent?:(kind:string,message:string,source:"CLOUD_RUN")=>void}){
  const [summary,setSummary]=useState(()=>JSON.stringify(demo(),null,2));
  const [ack,setAck]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [output,setOutput]=useState<BIResult14B4|null>(null);
  async function submit(e:FormEvent<HTMLFormElement>){
    e.preventDefault();setError("");setOutput(null);setBusy(true);
    try{
      if(!ack) throw new Error("Acknowledge the aggregate evidence limitations before analysis.");
      if(summary.length>12000) throw new Error("Use compact aggregate summaries (under 12,000 characters), not source customer records.");
      const data:unknown=JSON.parse(summary);
      if(!data || typeof data!=="object" || Array.isArray(data)) throw new Error("Enter one JSON summary object.");
      const result=await evaluateBI14B4(data as BIInput14B4);
      setOutput(result);
      onEvent?.("BI_COMMAND_CENTER_14B4",`Reviewed ${result.coverage.available_modules}/4 unverified aggregate modules; ${result.review_queue.length} follow-up actions.`,"CLOUD_RUN");
    }catch(ex){setError(ex instanceof Error?ex.message:"BI analysis failed.");}
    finally{setBusy(false);}
  }
  return <section id="bi-command-center-14b4" className="scroll-mt-20 space-y-4 rounded-2xl border border-[#30415B] bg-[#111827] p-4 sm:p-5">
    <div className="flex items-center gap-2"><BarChart3 size={18} className="text-sky-300"/><h2 className="text-base font-semibold">Business Intelligence Command Center · 14B.4</h2></div>
    <p className="text-xs leading-6 text-slate-300">Bring together <strong>aggregate summaries</strong> from demand forecasting (14B.1), anonymous cohorts (14B.2), reported inventory (14B.3), and evidence verification (13B/14A). Review provenance, coverage and the next operational questions. No customer IDs, live warehouse connections or BigQuery provisioning.</p>
    <form onSubmit={e=>void submit(e)} className="space-y-3">
      <label className="block text-xs text-slate-300">Aggregate scenario JSON · edit counts, remove an optional module, or paste your own de-identified summary
        <textarea rows={10} maxLength={12000} spellCheck={false} className={inputClass} value={summary}
          onChange={e=>{setSummary(e.target.value);setOutput(null);}}/>
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className="rounded-lg border border-slate-600 px-3 py-2 text-xs text-sky-300"
          onClick={()=>{setSummary(JSON.stringify(demo(),null,2));setOutput(null);setError("");}}>Reset explicitly synthetic example</button>
        <span className="text-xs text-amber-200">When using your own summaries, set synthetic_demo to false.</span>
      </div>
      <label className="flex items-start gap-2 text-xs text-amber-200"><input className="mt-0.5" type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>
        <span>All entries are caller-supplied aggregate claims. This panel does not validate past calculations, verify stock, diagnose fraud, or authorize purchases.</span>
      </label>
      <button type="submit" disabled={busy||!ack} className="inline-flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">
        <RefreshCcw size={15}/>{busy?"Compiling scenario…":"Build BI review dashboard"}
      </button>
    </form>
    {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
    {output && <div aria-live="polite" className="space-y-4">
      <p className="flex items-center gap-2 text-xs text-amber-200"><ShieldAlert size={16}/>{output.data_origin.replace(/_/g," ")} · UNVERIFIED · NOT LIVE BUSINESS DATA</p>
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-700 p-3">
        <p className="text-sm text-sky-100">{output.executive_summary}</p>
        <span className="text-xs text-slate-400">As of {output.as_of} · Age {output.snapshot_age_days} days</span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {Object.entries(output.coverage.supplied).map(([name,present])=><div key={name} className={`rounded-lg border p-3 ${present?"border-sky-900 bg-sky-950/30":"border-amber-950 bg-amber-950/20"}`}>
          <p className="text-xs capitalize text-slate-300">{name}</p><p className="text-sm font-semibold">{present?"Summary present":"Not supplied"}</p>
        </div>)}
      </div>
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {output.metrics.map(m=><div key={m.key} className="rounded-lg border border-slate-700 p-3" title={m.interpretation}>
          <p className="text-xs text-slate-400">{m.label}</p><p className="my-1 text-xl font-semibold text-slate-100">{m.value}<span className="ml-1 text-xs font-normal text-slate-400">{m.unit}</span></p>
          <p className="text-[11px] text-sky-300">{m.source_module} · supplied, not verified</p>
        </div>)}
      </div>
      <div className="space-y-2"><h3 className="flex items-center gap-2 text-sm font-semibold text-sky-200"><ClipboardList size={17}/> Prioritized review actions · heuristic, not EVSI</h3>
        {output.review_queue.length===0?<p className="text-xs text-slate-400">No configured review rules fired; this does not certify operational readiness.</p>:
          output.review_queue.map(a=><div key={a.key} className="rounded-lg border border-slate-700 p-3 text-xs">
            <div className="flex flex-wrap justify-between gap-2"><strong className="text-slate-100">{a.title}</strong><span className="text-amber-200">{priorityLabel(a.priority)} · {a.source_module}</span></div>
            <p className="mt-1 text-slate-300">{a.reason}</p>
          </div>)}
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-400"><TrendingUp size={15}/>This dashboard does not claim sales uplift or independent causal validation.</div>
      <details className="text-xs text-slate-400"><summary className="cursor-pointer text-sky-300">Evidence boundaries and statistical limitations</summary>
        <ul className="mt-2 list-disc space-y-2 pl-4">{output.limitations.map((s,i)=><li key={i}>{s}</li>)}</ul>
      </details>
    </div>}
  </section>;
}
