import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowRight, CheckCircle2, ClipboardList, RefreshCw, ShieldAlert } from "lucide-react";
import {
  runGuidedJourney16A, type JourneyResult16A, type Scenario16A,
} from "../lib/guidedJourney16a";

const cases: Array<{id:Scenario16A; label:string; detail:string}> = [
  {id:"reported_offer",label:"1 · Reported offer",detail:"A fictional shop claims one charger is in stock"},
  {id:"stockout",label:"2 · Stock-out",detail:"Stock claim changes from one unit to zero"},
  {id:"document_conflict",label:"3 · Document conflict",detail:"Two excerpts disagree about compatibility"},
  {id:"no_merchants",label:"4 · No merchants",detail:"Missing store evidence forces discovery"},
];

const readable=(value:string)=>value.toLowerCase().replace(/_/g," ");

export default function GuidedJourney16A({onEvent}: {
  onEvent?:(kind:string,message:string,source:"CLOUD_RUN")=>void;
}){
  const [scenario,setScenario]=useState<Scenario16A>("reported_offer");
  const [ack,setAck]=useState(false);
  const [showBI,setShowBI]=useState(true);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");
  const [result,setResult]=useState<JourneyResult16A|null>(null);
  const controller=useRef<AbortController|null>(null);
  useEffect(()=>()=>controller.current?.abort(),[]);

  function choose(value:Scenario16A){
    controller.current?.abort();setScenario(value);setResult(null);setError("");setLoading(false);
  }
  async function submit(e:FormEvent<HTMLFormElement>){
    e.preventDefault();
    if(!ack){setError("Acknowledge the fictional evidence boundary before running the demo.");return;}
    controller.current?.abort();const c=new AbortController();controller.current=c;
    setLoading(true);setError("");setResult(null);
    try{
      const next=await runGuidedJourney16A(scenario,showBI,c.signal);
      if(controller.current!==c)return;
      setResult(next);
      onEvent?.("GUIDED_JOURNEY_16A",`Synthetic scenario ${scenario} → ${next.workflow.workflow_state}. No purchase authorized.`,"CLOUD_RUN");
    }catch(reason){
      if(c.signal.aborted)return;
      setError(reason instanceof Error?reason.message:"Could not run the guided scenario.");
    }finally{if(controller.current===c){controller.current=null;setLoading(false);}}
  }

  return <section id="guided-journey-16a" className="scroll-mt-20 space-y-4 rounded-2xl border border-sky-800/70 bg-[#111827] p-4 sm:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-sky-300">Chunk 16A · Integrated walkthrough</p>
        <h2 className="mt-1 text-lg font-semibold text-white">From missing evidence to the next decision</h2>
      </div>
      <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-bold text-amber-200">SYNTHETIC · NOT REAL STOCK</span>
    </div>
    <p className="max-w-3xl text-sm leading-6 text-slate-300">Four scripted cases exercise the actual product research, merchant replanning, hypothetical EVSI and separate synthetic basket engine. The optional retail BI context is a <strong>separate illustrative aggregate</strong>, not a live POS feed or data from this journey.</p>

    <form className="space-y-4" onSubmit={e=>void submit(e)}>
      <div className="grid gap-2 sm:grid-cols-2">
        {cases.map(item=><button key={item.id} type="button" aria-pressed={scenario===item.id} onClick={()=>choose(item.id)}
          className={`rounded-xl border p-3 text-left transition-colors ${scenario===item.id?"border-sky-400 bg-sky-950/50":"border-slate-700 bg-[#080D17] hover:border-slate-500"}`}>
          <span className="text-sm font-semibold text-white">{item.label}</span>
          <span className="mt-1 block text-xs text-slate-400">{item.detail}</span>
        </button>)}
      </div>
      <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={showBI}
        onChange={e=>{setShowBI(e.target.checked);setResult(null);}}/>Include separate fictional retailer analytics context</label>
      <label className="flex items-start gap-2 text-xs text-amber-200"><input className="mt-0.5" type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>
        <span>I understand all prices, store claims, documents and stock in this tour are fictional. Any EVSI value and basket outcome is modeled, not a verified purchasing opportunity.</span>
      </label>
      <button type="submit" disabled={loading||!ack} className="inline-flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">
        <RefreshCw size={16} className={loading?"animate-spin":""}/>{loading?"Running the engine…":"Run evidence-to-decision walkthrough"}
      </button>
    </form>
    {error&&<p role="alert" className="rounded-lg border border-rose-500/30 bg-rose-950/30 p-3 text-sm text-rose-200">{error}</p>}

    {result&&<div aria-live="polite" className="space-y-4">
      <div className="rounded-xl border border-sky-700/50 bg-sky-950/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-sky-300">Decision state · {readable(result.workflow.workflow_state)}</p>
        <h3 className="mt-2 text-base font-semibold text-white">{result.title}</h3>
        <p className="mt-2 text-sm leading-6 text-slate-300">{result.workflow.reason}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-amber-200">
          <ShieldAlert size={15}/><span>No stock verification · No merchant contact · No purchase approval</span>
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-700 p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-white"><ArrowRight size={16} className="text-sky-300"/>Next review action</h3>
          <p className="mt-2 break-words text-sm text-sky-200">{readable(result.workflow.recommended_next_action)}</p>
          {result.workflow.change_detection.changed&&<p className="mt-2 text-xs text-amber-200">Evidence changed: {result.workflow.change_detection.changes.map(c=>readable(c.event)).join(", ")}</p>}
          <p className="mt-3 text-xs text-slate-400">Product excerpts: {readable(result.workflow.product_research?.review.status??"not provided")}. The hypothetical basket is independent of merchant evidence.</p>
        </div>
        <div className="rounded-xl border border-slate-700 p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-white"><ClipboardList size={16} className="text-sky-300"/>Algorithm trace</h3>
          <ol className="mt-2 space-y-2">{result.workflow.workflow_trace.map(step=><li key={step.stage} className="text-xs text-slate-300">
            <span className="font-medium text-sky-200">{readable(step.stage)}</span>
            <span className="block">{readable(step.state)} · {readable(step.status)}</span>
          </li>)}</ol>
        </div>
      </div>
      {result.separate_illustrative_business_context&&<div className="rounded-xl border border-slate-700 p-4">
        <h3 className="text-sm font-semibold text-white">Separate fictional retailer's BI review</h3>
        <p className="mt-1 text-xs text-amber-200">Illustrative aggregate fixture, not derived from the charger decision or real sales.</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">{result.separate_illustrative_business_context.metrics.slice(0,3).map(m=><div key={m.key} className="rounded-lg bg-[#080D17] p-3">
          <p className="text-xs text-slate-400">{m.label}</p>
          <p className="mt-1 text-base font-semibold text-white">{m.value} <span className="text-xs font-normal text-slate-400">{m.unit}</span></p>
        </div>)}</div>
        <p className="mt-3 text-xs text-slate-300">{result.separate_illustrative_business_context.coverage.available_modules}/4 hypothetical BI summaries present · {result.separate_illustrative_business_context.review_queue.length} review checks</p>
      </div>}
      <div className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300"><CheckCircle2 size={16} className="text-sky-300"/>Real decision algorithms running on server-owned synthetic data; all outputs remain non-purchasable.</div>
      <details className="text-xs text-slate-400"><summary className="cursor-pointer text-sky-300">Provenance and limitations</summary>
        <ul className="mt-2 list-disc space-y-2 pl-4">{result.limitations.map((line,i)=><li key={i}>{line}</li>)}</ul>
      </details>
    </div>}
  </section>;
}
