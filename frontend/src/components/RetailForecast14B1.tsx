import { useState, type FormEvent } from "react";
import { ChartNoAxesCombined, ShieldAlert, RefreshCw } from "lucide-react";
import { forecastRetail14b1, type DailySales14B1, type RetailForecast14B1 } from "../lib/retailForecast14b1";

const field = "mt-1 block w-full rounded-lg border border-slate-600 bg-[#080D17] p-2 text-slate-100";

function demoCSV(): string {
  const rows = ["day,units_sold,reported_stockout"];
  const today = new Date();
  const todayUtc = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  for (let i = 84; i >= 1; i--) {
    const day = new Date(todayUtc - i*86400000).toISOString().slice(0,10);
    const weekday = new Date(`${day}T12:00:00Z`).getUTCDay();
    const units = 7 + (weekday === 5 || weekday === 6 ? 7 : weekday === 0 ? 4 : 1) + ((84-i)%17===0 ? 3 : 0);
    rows.push(`${day},${units},false`);
  }
  return rows.join("\n");
}

function parseCSV(csv: string): DailySales14B1[] {
  const lines = csv.split(/\r?\n/).map(line=>line.trim()).filter(Boolean);
  if (lines[0]?.toLowerCase() === "day,units_sold,reported_stockout" || lines[0]?.toLowerCase() === "day,units_sold") lines.shift();
  if (lines.length < 42 || lines.length > 180) throw new Error("Provide 42–180 consecutive daily sales rows.");
  return lines.map((line, idx)=>{
    const parts = line.split(",").map(s=>s.trim());
    if (parts.length !== 2 && parts.length !== 3) throw new Error(`CSV row ${idx+1}: use date,units,stockout`);
    const [day, raw, flag="false"] = parts;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || !/^\d+$/.test(raw) || !/^(true|false)$/i.test(flag))
      throw new Error(`CSV row ${idx+1}: expected YYYY-MM-DD,nonnegative integer,true|false`);
    const quantity = Number(raw);
    if (!Number.isSafeInteger(quantity) || quantity > 1000000) throw new Error(`CSV row ${idx+1}: units out of range`);
    return {day,units_sold:quantity,reported_stockout:flag.toLowerCase()==="true"};
  });
}

export default function RetailForecast14B1({onEvent}:{onEvent?:(kind:string, message:string, source:"CLOUD_RUN")=>void}) {
  const [csv,setCsv] = useState(()=>demoCSV());
  const [synthetic,setSynthetic] = useState(true);
  const [product,setProduct] = useState("Fictitious 65W USB-C charger");
  const [horizon,setHorizon] = useState("7");
  const [onHand,setOnHand] = useState("80");
  const [lead,setLead] = useState("5");
  const [result,setResult] = useState<RetailForecast14B1|null>(null);
  const [pending,setPending] = useState(false);
  const [error,setError] = useState("");
  const [ack,setAck] = useState(false);
  const run = async (e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();setPending(true);setError("");setResult(null);
    try {
      if (!ack) throw new Error("Acknowledge that sales are an unverified demand proxy.");
      const history = parseCSV(csv);
      const horizonDays = Number(horizon);
      const hasStock = onHand.trim()!=="" || lead.trim()!=="";
      if (hasStock && (onHand.trim()==="" || lead.trim()==="")) throw new Error("Provide both stock and replenishment lead time, or leave both empty.");
      const data = await forecastRetail14b1({product_label:product,history,horizon_days:horizonDays,
        on_hand_units:hasStock?Number(onHand):null,replenishment_lead_days:hasStock?Number(lead):null,synthetic_demo:synthetic});
      setResult(data);
      onEvent?.("SALES_FORECAST_14B1",`14B.1 compared forecasting baselines for ${data.training_observations} ${data.data_origin.toLowerCase()} days.`,"CLOUD_RUN");
    } catch(ex) {setError(ex instanceof Error ? ex.message : "Sales forecast failed.");}
    finally {setPending(false);}
  };
  return <section id="forecast-14b1" className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#111827] p-4 sm:p-5 space-y-3">
    <div className="flex items-center gap-2"><ChartNoAxesCombined size={18} className="text-sky-300"/><h2 className="font-semibold">Retail Sales Forecast Lab · 14B.1</h2></div>
    <p className="text-xs leading-6 text-slate-300">Compare four transparent forecasting baselines on your daily sales CSV. Backtest against held-out history, inspect uncalibrated error bands and simulate inventory exposure. No Gemini, model training charges or persistence.</p>
    <form className="space-y-3" onSubmit={e=>void run(e)}>
      <div className="grid gap-3 sm:grid-cols-4">
        <label className="text-xs text-slate-300 sm:col-span-2">Product label<input required minLength={2} maxLength={100} className={field} value={product} onChange={e=>setProduct(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Forecast days<input type="number" min="1" max="14" className={field} value={horizon} onChange={e=>setHorizon(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Stock on hand (optional)<input type="number" min="0" max="1000000" className={field} value={onHand} onChange={e=>setOnHand(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Replenishment lead days<input type="number" min="1" max="14" className={field} value={lead} onChange={e=>setLead(e.target.value)}/></label>
      </div>
      <label className="block text-xs text-slate-300">Historical CSV: day,units_sold,reported_stockout (42–180 consecutive ascending dates)
        <textarea rows={6} maxLength={15000} className={`${field} font-mono`} value={csv} onChange={e=>{setCsv(e.target.value);setSynthetic(false);}}/>
      </label>
      <button type="button" className="rounded border border-slate-600 px-3 py-1.5 text-xs text-sky-300" onClick={()=>{setCsv(demoCSV());setSynthetic(true);setResult(null);}}>Reset labeled synthetic example</button>
      <label className="flex items-start gap-2 text-xs text-amber-200"><input className="mt-0.5" type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>I understand sales are not verified true demand, stock reports may be incomplete, and results are not purchasing advice.</label>
      <button type="submit" disabled={pending||!ack} className="inline-flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40"><RefreshCw size={15}/>{pending?"Forecasting…":"Compare forecasts"}</button>
    </form>
    {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
    {result && <div className="space-y-3" aria-live="polite">
      <p className="flex items-center gap-2 text-xs text-amber-200"><ShieldAlert size={15}/>{result.data_origin.replace(/_/g," ")} · SALES PROXY · NOT CALIBRATED · NO PURCHASE</p>
      <div className="rounded-lg border border-sky-500/25 bg-sky-500/5 p-3"><p className="text-sm font-semibold text-sky-200">Selected baseline: {result.selected_model.replace(/_/g," ")}</p><p className="text-xs text-slate-400">{result.training_observations} daily samples · 14 rolling backtest origins · {result.reported_stockout_days} reported stockout days</p></div>
      <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="text-slate-400"><th className="p-2">Model</th><th className="p-2">MAE units</th><th className="p-2">WAPE</th><th className="p-2">Bias</th></tr></thead><tbody>{result.model_comparison.map(m=><tr key={m.method} className="border-t border-slate-700"><td className="p-2">{m.method}</td><td className="p-2">{m.mae_units}</td><td className="p-2">{m.wape_pct===null?"n/a":`${m.wape_pct}%`}</td><td className="p-2">{m.mean_signed_error_units}</td></tr>)}</tbody></table></div>
      <div className="rounded-lg border border-slate-700 bg-[#080D17] p-3">
        <p className="text-xs text-slate-300 mb-2">Forecast units by day (heuristic limits shown in the table below)</p>
        <div className="flex h-32 items-end gap-2" role="img" aria-label="Projected sales by future day">
          {result.predictions.map(p=>{
            const peak = Math.max(1,...result.predictions.map(d=>d.upper_heuristic_80 ?? d.expected_units));
            return <div key={p.day} className="flex flex-1 min-w-0 flex-col items-center justify-end gap-1 h-full">
              <span className="text-[10px] text-sky-200">{p.expected_units}</span>
              <div className="w-full max-w-12 rounded-t bg-sky-400/80" style={{height:`${Math.max(2,85*p.expected_units/peak)}%`}} title={`${p.day}: ${p.expected_units} expected units`}/>
              <span className="text-[9px] text-slate-400 truncate">{p.day.slice(5)}</span>
            </div>;
          })}
        </div>
      </div>
      <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="text-slate-400"><th className="p-2">Date</th><th className="p-2">Expected sales</th><th className="p-2">Heuristic low</th><th className="p-2">Heuristic high</th></tr></thead><tbody>{result.predictions.map(p=><tr key={p.day} className="border-t border-slate-700"><td className="p-2">{p.day}</td><td className="p-2 font-medium">{p.expected_units}</td><td className="p-2">{p.lower_heuristic_80 ?? "n/a"}</td><td className="p-2">{p.upper_heuristic_80 ?? "n/a"}</td></tr>)}</tbody></table></div>
      {result.inventory_exposure_scenario && <p className="rounded-lg border border-amber-400/20 bg-amber-400/5 p-3 text-xs text-amber-100">Illustrative lead-time sales: {result.inventory_exposure_scenario.projected_sales_units_before_replenishment} units · reported stock: {result.inventory_exposure_scenario.reported_on_hand_units} · projected shortfall: {result.inventory_exposure_scenario.projected_shortfall_units}. Not a verified stockout probability.</p>}
      <details className="text-xs text-slate-400"><summary className="cursor-pointer text-sky-300">Methods and limitations</summary><ul className="mt-2 list-disc pl-4 space-y-2">{result.limitations.map((t,i)=><li key={i}>{t}</li>)}</ul></details>
    </div>}
  </section>;
}
