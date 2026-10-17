import { useState, type FormEvent } from "react";
import { AlertTriangle, BarChart3, RefreshCw, ShieldCheck } from "lucide-react";
import { analyzeInventory14b3, type InventoryDay14B3, type InventoryResult14B3 } from "../lib/inventoryReview14b3";

const entry="mt-1 block w-full rounded-lg border border-slate-600 bg-[#080D17] p-2 text-slate-100";
const COLS="day,opening_units,received_units,sold_units,closing_units,reported_stockout";
function syntheticCSV():string {
  const rows=[COLS];let current=500;
  const today=new Date();today.setUTCHours(12,0,0,0);
  for(let i=0;i<56;i++){
    const day=new Date(today.getTime()-(55-i)*86400000).toISOString().slice(0,10);
    const received=i%7===0?20:0;
    const sold=i===40?32:4+(i%7===1?2:0);
    const closing=current+received-sold;
    rows.push(`${day},${current},${received},${sold},${closing},false`);
    current=closing;
  }
  return rows.join("\n");
}
function parseCSV(text:string):InventoryDay14B3[] {
  const lines=text.trim().split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  if(lines[0]?.toLowerCase()===COLS) lines.shift();
  if(lines.length<42||lines.length>90) throw new Error("Provide 42–90 consecutive daily observations.");
  return lines.map((line,index)=>{
    const cells=line.split(",").map(x=>x.trim());
    if(cells.length!==6 || !/^\d{4}-\d{2}-\d{2}$/.test(cells[0]) ||
       !cells.slice(1,5).every(x=>/^\d+$/.test(x) && Number.isSafeInteger(Number(x)) && Number(x)<=1000000) ||
       !/^(true|false)$/i.test(cells[5]))
      throw new Error(`Row ${index+1}: expected date, four nonnegative integer stock fields and true/false.`);
    return {day:cells[0],opening_units:Number(cells[1]),received_units:Number(cells[2]),
      sold_units:Number(cells[3]),closing_units:Number(cells[4]),reported_stockout:cells[5].toLowerCase()==="true"};
  });
}

export default function InventoryReview14B3({onEvent}:{onEvent?:(kind:string,message:string,source:"CLOUD_RUN")=>void}) {
  const [data,setData]=useState(syntheticCSV);
  const [sku,setSku]=useState("DEMO-SKU-14B3");
  const [lead,setLead]=useState("7");
  const [synthetic,setSynthetic]=useState(true);
  const [ack,setAck]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [result,setResult]=useState<InventoryResult14B3|null>(null);
  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setResult(null);setError("");setBusy(true);
    try {
      if(!ack) throw new Error("Acknowledge the unverified-data and non-fraud limitations first.");
      if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{1,31}$/.test(sku)) throw new Error("Use a short SKU code, not personal data.");
      const days=Number(lead);
      if(!Number.isInteger(days)||days<1||days>14) throw new Error("Lead time must be 1–14 days.");
      const response=await analyzeInventory14b3({sku_code:sku,history:parseCSV(data),
        lead_time_days:days,synthetic_demo:synthetic});
      setResult(response);
      onEvent?.("INVENTORY_REVIEW_14B3",`14B.3 reviewed ${response.record_count} reported daily stock records (${response.inventory_review.total_review_signals} review signals).`,"CLOUD_RUN");
    }catch(ex){setError(ex instanceof Error?ex.message:"Inventory review failed.");}
    finally{setBusy(false);}
  }
  return <section id="inventory-review-14b3" className="scroll-mt-20 space-y-3 rounded-2xl border border-[#30415B] bg-[#111827] p-4 sm:p-5">
    <div className="flex items-center gap-2"><BarChart3 size={18} className="text-sky-300"/><h2 className="font-semibold">Inventory Uncertainty & Review Signals · 14B.3</h2></div>
    <p className="text-xs leading-6 text-slate-300">Reconcile <strong>reported</strong> daily stock movements, review unusual sales, and compare unverified stock with 14B.1 forecast scenarios. No live inventory or fraud verification; no storage or restocking actions.</p>
    <form onSubmit={e=>void submit(e)} className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-xs text-slate-300">SKU code (no personal identifiers)
          <input className={entry} maxLength={32} value={sku} onChange={e=>setSku(e.target.value)}/>
        </label>
        <label className="text-xs text-slate-300">Reported replenishment lead time (days)
          <input type="number" className={entry} min={1} max={14} value={lead} onChange={e=>setLead(e.target.value)}/>
        </label>
      </div>
      <label className="block text-xs text-slate-300">Daily reported stock CSV · {COLS} (42–90 rows)
        <textarea className={`${entry} font-mono`} rows={7} maxLength={14000} value={data}
          onChange={e=>{setData(e.target.value);setSynthetic(false);}}/>
      </label>
      <button className="rounded border border-slate-600 px-3 py-2 text-xs text-sky-300" type="button"
        onClick={()=>{setData(syntheticCSV());setSku("DEMO-SKU-14B3");setLead("7");setSynthetic(true);setResult(null);}}>
        Reset labeled synthetic demo
      </button>
      <label className="flex items-start gap-2 text-xs text-amber-200">
        <input type="checkbox" className="mt-0.5" checked={ack} onChange={e=>setAck(e.target.checked)}/>
        <span>These are user-reported or synthetic observations. Signals do not establish fraud, live stock, supplier reliability, or purchase authorization.</span>
      </label>
      <button disabled={busy||!ack} className="inline-flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40" type="submit">
        <RefreshCw size={15}/>{busy?"Reviewing…":"Analyze inventory evidence"}
      </button>
    </form>
    {error && <p className="text-sm text-rose-300" role="alert">{error}</p>}
    {result && <div aria-live="polite" className="space-y-3">
      <p className="flex items-center gap-2 text-xs text-amber-200"><ShieldCheck size={15}/>{result.data_origin.replace(/_/g," ")} · UNVERIFIED · NO PURCHASE OR FRAUD FINDING</p>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {([
          ["Reported closing units",result.reported_closing_units],
          ["Inventory review signals",result.inventory_review.total_review_signals],
          ["Reported stockout days",result.observed_stockout_days],
          ["Lead-time gap scenario",result.lead_time_scenario.gap_to_empirical_80p_units??"N/A"],
        ] as const).map(([label,value])=><div className="rounded-lg border border-slate-700 p-3" key={label}><p className="text-xs text-slate-400">{label}</p><p className="text-xl font-semibold">{value}</p></div>)}
      </div>
      <div className="rounded-lg border border-slate-700 p-3 space-y-1 text-xs text-slate-300">
        <p className="font-semibold text-sky-200">Lead-time scenario: {result.lead_time_scenario.status.replace(/_/g," ")}</p>
        <p>14B.1 selected method: {result.forecast_model_reused_14b1} · Forecast sales proxy: {result.lead_time_scenario.forecast_sales_proxy_units} units</p>
        <p>Historical clean windows: {result.lead_time_scenario.clean_windows} · Empirical 80th percentile: {result.lead_time_scenario.empirical_80p_units??"Not available"} units</p>
        <p>Illustrative observed-sales coverage: {result.coverage_days_at_observed_sales_rate??"Not available"} days</p>
        <p>{result.lead_time_scenario.interpretation}</p>
      </div>
      <div className="space-y-2"><h3 className="flex items-center gap-2 text-sm font-semibold text-sky-200"><AlertTriangle size={16}/>Review signals · first 15</h3>
        {result.inventory_review.signals.length===0?<p className="text-xs text-slate-400">No monitored signals on this dataset. That does not verify inventory accuracy.</p>:
          <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="text-slate-400"><th className="p-2">Day</th><th className="p-2">Signal</th><th className="p-2">Units</th><th className="p-2">Review reason</th></tr></thead>
            <tbody>{result.inventory_review.signals.map((signal,i)=><tr key={`${signal.day}-${signal.signal}-${i}`} className="border-t border-slate-700"><td className="p-2">{signal.day}</td><td className="p-2">{signal.signal.replace(/_/g," ")}</td><td className="p-2">{signal.difference_units??"—"}</td><td className="p-2">{signal.detail}</td></tr>)}</tbody>
          </table></div>}
        {result.inventory_review.signals_truncated && <p className="text-xs text-amber-200">Showing only 15 of {result.inventory_review.total_review_signals} review signals.</p>}
      </div>
      <div><h3 className="mb-1 text-sm font-semibold text-sky-200">Next verification actions</h3><ul className="list-disc pl-5 text-xs text-slate-300 space-y-1">{result.review_actions.map((action,i)=><li key={i}>{action}</li>)}</ul></div>
      <details className="text-xs text-slate-400"><summary className="cursor-pointer text-sky-300">Source and statistical limitations</summary><ul className="mt-2 list-disc pl-4 space-y-2">{result.limitations.map((x,i)=><li key={i}>{x}</li>)}</ul></details>
    </div>}
  </section>;
}
