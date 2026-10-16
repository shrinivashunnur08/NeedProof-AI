import { useState, type FormEvent } from "react";
import { ChartScatter, ShieldCheck, RefreshCw } from "lucide-react";
import { analyzeRetail14b2, type Profile14B2, type RetailInsights14B2 } from "../lib/retailInsights14b2";

const field="mt-1 block w-full rounded-lg border border-slate-600 bg-[#080D17] p-2 text-slate-100";

function syntheticProfiles():string {
  const rows=["recency_days,orders_90d,spend_minor_90d"];
  for(let cohort=0;cohort<3;cohort++) for(let j=0;j<10;j++)
    rows.push(`${[3,35,150][cohort]+j%3},${[24,8,1][cohort]+j%2},${[120000,32000,1800][cohort]+j*100}`);
  return rows.join("\n");
}
function syntheticBaskets():string {
  const rows=["product_codes_in_order"];
  for(const [a,b] of [["USB-C","CASE"],["CHARGER","CABLE"],["SCREEN","MOUSE"]])
    for(let j=0;j<10;j++) rows.push(`${a},${b}`);
  return rows.join("\n");
}
function parseProfiles(csv:string):Profile14B2[] {
  const rows=csv.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  if(rows[0]?.toLowerCase()==="recency_days,orders_90d,spend_minor_90d") rows.shift();
  if(rows.length<24 || rows.length>120) throw new Error("Provide 24–120 aggregate customer profiles.");
  return rows.map((row,i)=>{
    const parts=row.split(",").map(x=>x.trim());
    if(parts.length!==3 || !parts.every(x=>/^\d+$/.test(x))) throw new Error(`Profile row ${i+1}: expected three nonnegative integers.`);
    const [recency_days,orders_90d,spend_minor_90d]=parts.map(Number);
    if(!Number.isSafeInteger(recency_days)||recency_days>365||
       !Number.isSafeInteger(orders_90d)||orders_90d>200||
       !Number.isSafeInteger(spend_minor_90d)||spend_minor_90d>200000000)
      throw new Error(`Profile row ${i+1}: numbers outside allowed range.`);
    return {recency_days,orders_90d,spend_minor_90d};
  });
}
function parseBaskets(csv:string):string[][] {
  const rows=csv.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  if(rows[0]?.toLowerCase()==="product_codes_in_order") rows.shift();
  if(rows.length<24 || rows.length>200) throw new Error("Provide 24–200 order baskets.");
  const all=new Set<string>();
  const baskets=rows.map((row,i)=>{
    const products=row.split(",").map(x=>x.trim());
    if(products.length<2||products.length>8||new Set(products).size!==products.length||
      !products.every(p=>/^[A-Za-z0-9][A-Za-z0-9_.-]{0,31}$/.test(p)))
      throw new Error(`Basket row ${i+1}: use 2–8 unique short product codes (no personal data).`);
    products.forEach(p=>all.add(p));
    return products;
  });
  if(all.size>30) throw new Error("Use at most 30 distinct product codes.");
  return baskets;
}

export default function RetailInsights14B2({onEvent}:{onEvent?:(kind:string,message:string,source:"CLOUD_RUN")=>void}) {
  const [profiles,setProfiles]=useState(syntheticProfiles);
  const [baskets,setBaskets]=useState(syntheticBaskets);
  const [synthetic,setSynthetic]=useState(true);
  const [threshold,setThreshold]=useState("3");
  const [ack,setAck]=useState(false);
  const [result,setResult]=useState<RetailInsights14B2|null>(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const submit=async(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();setError("");setResult(null);setBusy(true);
    try {
      if(!ack) throw new Error("Acknowledge the privacy and non-causal limitations first.");
      const minPairs=Number(threshold);
      if(!Number.isInteger(minPairs)||minPairs<3||minPairs>20) throw new Error("Minimum co-occurring orders must be 3–20.");
      const data=await analyzeRetail14b2({profiles:parseProfiles(profiles),baskets:parseBaskets(baskets),
        minimum_pair_orders:minPairs,synthetic_demo:synthetic});
      setResult(data);
      onEvent?.("RETAIL_INSIGHTS_14B2",`14B.2 analyzed ${data.segmentation.profile_count} anonymous aggregate profiles and ${data.basket_analysis.basket_count} supplied baskets.`,"CLOUD_RUN");
    } catch(ex) {setError(ex instanceof Error?ex.message:"Cohort and basket analysis failed.");}
    finally {setBusy(false);}
  };
  return <section id="retail-insights-14b2" className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#111827] p-4 sm:p-5 space-y-3">
    <div className="flex items-center gap-2"><ChartScatter size={18} className="text-sky-300"/><h2 className="font-semibold">Customer Cohorts & Basket Patterns · 14B.2</h2></div>
    <p className="text-xs leading-6 text-slate-300">Descriptive RFM cohorts and item co-occurrence from <strong>anonymous aggregated profiles</strong> and unlinked order baskets. No customer IDs, individual segment assignments, sales history uploads, AI model calls, or persistence.</p>
    <form onSubmit={e=>void submit(e)} className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-xs text-slate-300">Aggregate profiles CSV · recency days, orders in 90d, spend in minor currency units (24–120 rows)
          <textarea rows={6} maxLength={16000} className={`${field} font-mono`} value={profiles} onChange={e=>{setProfiles(e.target.value);setSynthetic(false);}}/>
        </label>
        <label className="text-xs text-slate-300">Unlinked order baskets CSV · one order per line, product codes only (24–200 rows)
          <textarea rows={6} maxLength={15000} className={`${field} font-mono`} value={baskets} onChange={e=>{setBaskets(e.target.value);setSynthetic(false);}}/>
        </label>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-300">Minimum orders per pair <input type="number" min="3" max="20" className={`${field} w-28`} value={threshold} onChange={e=>setThreshold(e.target.value)}/></label>
        <button type="button" className="rounded border border-slate-600 px-3 py-2 text-xs text-sky-300" onClick={()=>{setProfiles(syntheticProfiles());setBaskets(syntheticBaskets());setSynthetic(true);setResult(null);}}>Reset labeled synthetic demo</button>
      </div>
      <label className="flex items-start gap-2 text-xs text-amber-200"><input type="checkbox" className="mt-0.5" checked={ack} onChange={e=>setAck(e.target.checked)}/><span>Inputs must contain no personal identifiers. These are descriptive associations, not causal cross-sell forecasts or permission for individualized targeting.</span></label>
      <button disabled={busy||!ack} type="submit" className="inline-flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40"><RefreshCw size={15}/>{busy?"Analyzing…":"Analyze cohorts and baskets"}</button>
    </form>
    {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
    {result && <div className="space-y-4" aria-live="polite">
      <div className="flex items-center gap-2 text-xs text-amber-200"><ShieldCheck size={16}/>{result.data_origin.replace(/_/g," ")} · UNVERIFIED · NO TARGETING OR CHECKOUT</div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {[ ["Profiles",result.segmentation.profile_count],["Cohorts",result.segmentation.selected_k],["Order baskets",result.basket_analysis.basket_count],["Eligible rules",result.basket_analysis.eligible_rules_before_cap]].map(([label,value])=><div key={label} className="rounded-lg border border-slate-700 p-3"><p className="text-xs text-slate-400">{label}</p><p className="text-lg font-semibold">{value}</p></div>)}
      </div>
      <div><h3 className="mb-2 text-sm font-semibold text-sky-200">RFM segments (no individuals displayed)</h3>
        <div className="grid gap-2 md:grid-cols-3">{result.segmentation.segments.map(segment=><div key={segment.segment} className="rounded-lg border border-slate-700 p-3 space-y-2"><p className="text-sm font-semibold">{segment.segment} · {segment.count} profiles</p><div className="h-2 overflow-hidden rounded bg-slate-700"><div className="h-full rounded bg-sky-400" style={{width:`${Math.max(0,Math.min(100,segment.share_pct))}%`}}/></div><p className="text-xs text-slate-300">Share {segment.share_pct}% · Recency {segment.mean_recency_days}d · Orders {segment.mean_orders_90d} · Average spend (minor units) {segment.mean_spend_minor_90d.toLocaleString()}</p></div>)}</div>
        <p className="mt-2 text-xs text-slate-400">Exploratory silhouette: {result.segmentation.exploratory_silhouette ?? "not applicable (one cohort)"}. Min released cohort: {result.segmentation.min_reported_group_size}.</p>
      </div>
      <div><h3 className="mb-2 text-sm font-semibold text-sky-200">Basket associations · sample-derived, not causal</h3>
        {result.basket_analysis.rules.length===0?<p className="text-xs text-slate-400">No pair rules met the minimum count, support and lift thresholds. We do not fabricate opportunities.</p>:<div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="text-slate-400"><th className="p-2">Observed pair</th><th className="p-2">Orders</th><th className="p-2">Support</th><th className="p-2">Confidence</th><th className="p-2">Wilson lower</th><th className="p-2">Lift</th></tr></thead><tbody>{result.basket_analysis.rules.map(rule=><tr className="border-t border-slate-700" key={`${rule.antecedent_sku}|${rule.consequent_sku}`}><td className="p-2">{rule.antecedent_sku} → {rule.consequent_sku}</td><td className="p-2">{rule.cooccurring_orders}</td><td className="p-2">{rule.support_pct}%</td><td className="p-2">{rule.confidence_pct}%</td><td className="p-2">{rule.confidence_wilson95_lower_pct}%</td><td className="p-2">{rule.lift}</td></tr>)}</tbody></table></div>}
      </div>
      <details className="text-xs text-slate-400"><summary className="cursor-pointer text-sky-300">Methods, sample limitations and privacy safeguards</summary><ul className="mt-2 list-disc pl-4 space-y-2">{result.limitations.map((x,i)=><li key={i}>{x}</li>)}</ul></details>
    </div>}
  </section>;
}
