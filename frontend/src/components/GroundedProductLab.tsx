import { useState, type FormEvent } from "react";
import { BookOpen, ShieldAlert } from "lucide-react";
import { reviewGroundedProduct, type GroundingResult13C1, type SourceFact13C1 } from "../lib/productGrounding13c1";

type Props = { requestedProduct: string | null; onEvent: (kind: string, message: string, source: "CLOUD_RUN" | "USER") => void };

/** Manual document-evidence review, not a web search or product certification. */
export default function GroundedProductLab({ requestedProduct, onEvent }: Props) {
  const [product, setProduct] = useState("65W USB-C PD charger");
  const [device, setDevice] = useState("");
  const [watts, setWatts] = useState("65");
  const [volts, setVolts] = useState("20");
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [pdQuote, setPdQuote] = useState("");
  const [profileQuote, setProfileQuote] = useState("");
  const [profile, setProfile] = useState("");
  const [cableQuote, setCableQuote] = useState("");
  const [cable, setCable] = useState<"3A" | "5A" | "">("");
  const [pd, setPd] = useState<"true" | "false" | "">("");
  const [devicePd, setDevicePd] = useState<"true" | "false" | "">("");
  const [result, setResult] = useState<GroundingResult13C1 | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function evaluate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true); setResult(null); setError("");
    const facts: SourceFact13C1[] = [];
    if (pd && pdQuote.trim()) facts.push({ kind: "USB_PD_SUPPORT", value: pd, quote: pdQuote.trim() });
    if (profile && profileQuote.trim()) facts.push({ kind: "OUTPUT_PROFILE", value: profile.trim(), quote: profileQuote.trim() });
    if (cable && cableQuote.trim()) facts.push({ kind: "CABLE_CURRENT_RATING", value: cable, quote: cableQuote.trim() });
    try {
      const review = await reviewGroundedProduct({
        product_label: product.trim(), device_model: device.trim(),
        device_supports_usb_pd: devicePd ? devicePd === "true" : null,
        required_power_w: Number(watts), required_voltage_v: Number(volts),
        sources: excerpt.trim() && title.trim() ? [{ source_id: "source_1", title: title.trim(),
          url: url.trim() || null, captured_at: new Date().toISOString(), excerpt: excerpt.trim(), facts }] : [],
      });
      setResult(review);
      onEvent("PRODUCT_GROUNDING", "Reviewed user-supplied quoted specification evidence; no independent document verification.", "CLOUD_RUN");
    } catch (e) { setError(e instanceof Error ? e.message : "Grounded review failed."); }
    finally { setPending(false); }
  }

  return <section id="product-grounding" className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#111827] p-5">
    <div className="flex items-center gap-2"><BookOpen size={19} className="text-sky-400"/><h2 className="font-semibold">Product specification evidence review</h2></div>
    <p className="mt-2 text-xs leading-6 text-slate-400">Paste an actual product document excerpt and the exact quoted statements that support specifications. The backend checks quote alignment, contradictions and electrical constraints; it never fetches URLs or independently authenticates documents.</p>
    <button type="button" className="mt-3 rounded border border-slate-600 px-3 py-2 text-xs text-sky-300 disabled:opacity-40" disabled={!requestedProduct} onClick={() => { if (requestedProduct) { setProduct(requestedProduct); setResult(null); } }}>Use Gemini product description</button>
    <form className="mt-4 space-y-3" onSubmit={(e) => void evaluate(e)}>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-slate-300">Product label<input required maxLength={150} value={product} onChange={e=>setProduct(e.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"/></label>
        <label className="text-xs text-slate-300">Laptop/device model<input required maxLength={120} value={device} onChange={e=>setDevice(e.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"/></label>
        <label className="text-xs text-slate-300">Required watts<input type="number" min={1} max={240} required value={watts} onChange={e=>setWatts(e.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"/></label>
        <label className="text-xs text-slate-300">Required voltage (V)<input type="number" min={5} max={48} required value={volts} onChange={e=>setVolts(e.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"/></label>
        <label className="text-xs text-slate-300">Device supports USB PD<select value={devicePd} onChange={e=>setDevicePd(e.target.value as typeof devicePd)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"><option value="">Unknown</option><option value="true">Yes, user-reported</option><option value="false">No, user-reported</option></select></label>
        <label className="text-xs text-slate-300">Document title<input maxLength={160} value={title} onChange={e=>setTitle(e.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"/></label>
      </div>
      <label className="block text-xs text-slate-300">Document source URL (optional, not fetched)<input type="url" value={url} onChange={e=>setUrl(e.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"/></label>
      <label className="block text-xs text-slate-300">Original excerpt<textarea maxLength={2000} rows={3} value={excerpt} onChange={e=>setExcerpt(e.target.value)} placeholder="Paste the specification passage, including the exact claims cited below" className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"/></label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-slate-300">Charger USB PD support<select value={pd} onChange={e=>setPd(e.target.value as typeof pd)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"><option value="">Unknown</option><option value="true">Claimed yes</option><option value="false">Claimed no</option></select></label>
        <label className="text-xs text-slate-300">Exact USB PD quote<input maxLength={400} value={pdQuote} onChange={e=>setPdQuote(e.target.value)} placeholder="USB PD supported" className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"/></label>
        <label className="text-xs text-slate-300">Output profile claimed (e.g. 20V/3250mA)<input maxLength={40} value={profile} onChange={e=>setProfile(e.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"/></label>
        <label className="text-xs text-slate-300">Exact output profile quote<input maxLength={400} value={profileQuote} onChange={e=>setProfileQuote(e.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"/></label>
        <label className="text-xs text-slate-300">Cable rating claim<select value={cable} onChange={e=>setCable(e.target.value as typeof cable)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"><option value="">Unknown</option><option value="3A">3A</option><option value="5A">5A</option></select></label>
        <label className="text-xs text-slate-300">Exact cable rating quote<input maxLength={400} value={cableQuote} onChange={e=>setCableQuote(e.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2"/></label>
      </div>
      <button type="submit" disabled={pending || !device.trim()} className="rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-semibold text-slate-950 disabled:opacity-40">{pending ? "Reviewing..." : "Review cited specifications"}</button>
    </form>
    {error && <p role="alert" className="mt-4 text-sm text-rose-300">{error}</p>}
    {result && <div className="mt-4 space-y-2 rounded-xl border border-slate-700 p-4" aria-live="polite">
      <div className="flex items-center gap-2 text-sm font-semibold"><ShieldAlert size={16} className="text-amber-400"/>{result.status.replace(/_/g, " ")}</div>
      <p className="text-xs text-amber-200">{result.notice}</p>
      <p className="text-xs text-slate-300">Next: {result.compatibility.recommended_next_action}</p>
      {result.evidence_gaps.map(g => <p key={g.kind} className="text-xs text-rose-300">{g.kind}: {g.reason.replace(/_/g, " ")}</p>)}
      {result.cited_facts.map((c,i) => <div key={`${c.source_id}-${c.kind}-${i}`} className="rounded border border-slate-700 p-2 text-xs"><span className="font-semibold">[{c.source_id}] {c.kind}</span><p className="mt-1 text-slate-300">“{c.quote}”</p>{c.url && <a className="mt-1 inline-block text-sky-300 underline" href={c.url} target="_blank" rel="noopener noreferrer">User-provided source link</a>}</div>)}
    </div>}
  </section>;
}
