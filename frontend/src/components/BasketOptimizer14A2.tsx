import { useState, type FormEvent } from "react";
import { ShoppingBasket, ShieldAlert } from "lucide-react";
import { requestBasket14a2, type BasketResult14A2 } from "../lib/basketOptimizer14a2";

type Props = { onEvent: (kind: string, message: string, source: "CLOUD_RUN" | "USER") => void };
const field = "mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] px-3 py-2 text-sm text-slate-100";
const rupees = (minor: number) => `₹${(minor / 100).toLocaleString("en-IN", {maximumFractionDigits: 2})}`;

export default function BasketOptimizer14A2({ onEvent }: Props) {
  const [budget, setBudget] = useState("750");
  const [deadline, setDeadline] = useState("60");
  const [maxMerchants, setMaxMerchants] = useState("2");
  const [ack, setAck] = useState(false);
  const [includeReported, setIncludeReported] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<BasketResult14A2 | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setResult(null); setLoading(true);
    try {
      const minor = Math.round(Number(budget) * 100);
      const duration = Number(deadline);
      const merchantLimit = Number(maxMerchants);
      if (!Number.isSafeInteger(minor) || minor < 1 || minor > 100_000_000 ||
          !Number.isInteger(duration) || duration < 0 || duration > 1440 ||
          !Number.isInteger(merchantLimit) || merchantLimit < 1 || merchantLimit > 2) {
        throw new Error("Check the INR budget, deadline and merchant limit.");
      }
      const items = [{item_id: "charger", name: "65W USB-C charger", quantity: 1},
                     {item_id: "cable", name: "USB-C cable", quantity: 2}];
      const merchants = [{merchant_id: "a", name: "Illustrative A", fulfillment_fee_minor: 5000},
                         {merchant_id: "b", name: "Illustrative B", fulfillment_fee_minor: 0}];
      const verified = (sku:string, item_id:string, merchant_id:string, unit_price_minor:number, delivery_eta_minutes:number) => ({
        sku, item_id, merchant_id, product_name:item_id, unit_price_minor, stock_on_hand:2, delivery_eta_minutes,
        merchant_verified:true, stock_verified:true, compatibility_verified:true, delivery_verified:true,
        evidence_source:"SIMULATION_VERIFIED" as const,
      });
      const offers: Array<ReturnType<typeof verified> | (Omit<ReturnType<typeof verified>, "evidence_source"> & {evidence_source: "MERCHANT_REPORTED_UNVERIFIED"})> = [verified("a-chg", "charger", "a", 30000, 10),
        verified("b-chg", "charger", "b", 35000, 15),
        verified("a-cbl", "cable", "a", 5000, 10),
        verified("b-cbl", "cable", "b", 8000, 15)];
      if (includeReported) offers.push({ ...verified("cheap-merchant-report", "charger", "a", 10000, 2),
        evidence_source: "MERCHANT_REPORTED_UNVERIFIED" as const });
      const output = await requestBasket14a2({items, merchants, offers,
        budget_minor: minor, deadline_minutes: duration, max_merchants: merchantLimit,
        hypothetical_scenario_acknowledged: true});
      setResult(output);
      onEvent("BASKET_SCENARIO_14A2", "Compared synthetic basket constraints and excluded unverified merchant claims.", "CLOUD_RUN");
    } catch (exc) { setError(exc instanceof Error ? exc.message : "Basket planning failed."); }
    finally { setLoading(false); }
  }
  return <section id="basket-optimizer-14a2" className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#111827] p-4 sm:p-5 space-y-3">
    <div className="flex items-center gap-2"><ShoppingBasket size={18} className="text-sky-400"/><h2 className="font-semibold">Multi-Constraint Basket Planner</h2></div>
    <p className="text-xs leading-6 text-slate-300">Compare two products across illustrative merchants. Mathematical stock and verification flags apply <strong>only to synthetic fixtures</strong>. Unverified real-world claims are excluded and sent to a verification backlog.</p>
    <form className="space-y-3" onSubmit={e=>void submit(e)}>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-xs text-slate-300">Total budget (₹)<input className={field} type="number" min={1} max={1000000} value={budget} onChange={e=>setBudget(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Delivery deadline (minutes)<input className={field} type="number" min={0} max={1440} value={deadline} onChange={e=>setDeadline(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Maximum merchants<select className={field} value={maxMerchants} onChange={e=>setMaxMerchants(e.target.value)}><option value="1">1 merchant</option><option value="2">2 merchants</option></select></label>
      </div>
      <label className="flex gap-2 text-xs text-slate-300"><input type="checkbox" checked={includeReported} onChange={e=>setIncludeReported(e.target.checked)}/>Include a cheaper unverified merchant-report example (must be excluded)</label>
      <label className="flex gap-2 items-start text-xs text-amber-200"><input className="mt-0.5" type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>I understand all selected offers are synthetic scenario fixtures, not live inventory or purchase opportunities.</label>
      <button type="submit" disabled={!ack || loading} className="rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-semibold text-slate-950 disabled:opacity-40">{loading ? "Optimizing…" : "Optimize hypothetical basket"}</button>
    </form>
    {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
    {result && <div className="space-y-3" aria-live="polite">
      <div className="flex items-center gap-2 text-amber-200 text-xs"><ShieldAlert size={15}/>SIMULATED BASKET · NO VERIFIED STOCK · NO PURCHASE ALLOWED</div>
      <p className="text-sm font-semibold">{result.scenario_status} · {result.solver_engine.replace(/_/g," ")}</p>
      {result.synthetic_optimum.totals && <p className="text-sm text-sky-200">Scenario total: {rupees(result.synthetic_optimum.totals.total_minor)} including {rupees(result.synthetic_optimum.totals.fulfillment_fees_minor)} in merchant fees.</p>}
      <div className="grid gap-2 sm:grid-cols-2">{result.synthetic_optimum.selected_offers.map(o=><article key={o.sku} className="rounded border border-slate-700 bg-[#080D17] p-3 text-xs"><p className="font-semibold">{o.item_name} · {o.quantity}x</p><p className="text-slate-400">{o.merchant} · {rupees(o.line_total_minor)}</p></article>)}</div>
      {result.synthetic_optimum.blocked_items.length > 0 && <p className="text-xs text-amber-300">Blocked items: {result.synthetic_optimum.blocked_items.join(", ")}</p>}
      {result.verification_backlog.length > 0 && <details className="text-xs text-slate-300"><summary className="cursor-pointer text-sky-300">Verification backlog ({result.verification_backlog.length})</summary><ul className="mt-2 list-disc pl-5 space-y-1">{result.verification_backlog.map(v=><li key={v.sku}>{v.sku}: {v.required_checks.join(", ").replace(/_/g," ")}</li>)}</ul></details>}
      <p className="text-xs leading-5 text-slate-400">{result.disclosure}</p>
    </div>}
  </section>;
}
