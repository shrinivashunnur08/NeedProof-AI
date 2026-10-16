import { useState, type FormEvent } from "react";
import { BookText, SearchCheck, ShieldAlert } from "lucide-react";
import { researchDocuments13C2, explainEvidenceWithGemini13C2, optionalGemini13c2Enabled,
  type ResearchResult13C2 } from "../lib/productRetrieval13c2";

type Props = { requestedProduct: string | null; onEvent: (kind: string, message: string, source: "CLOUD_RUN" | "USER") => void };

export default function ProductResearch13C2({ requestedProduct, onEvent }: Props) {
  const [product, setProduct] = useState("65W USB-C PD charger");
  const [device, setDevice] = useState("");
  const [query, setQuery] = useState("65W USB PD output profile and compatible cable");
  const [watts, setWatts] = useState("65");
  const [voltage, setVoltage] = useState("20");
  const [devicePd, setDevicePd] = useState<"true" | "false" | "">("");
  const [title, setTitle] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [extraTitle, setExtraTitle] = useState("");
  const [extraExcerpt, setExtraExcerpt] = useState("");
  const [result, setResult] = useState<ResearchResult13C2 | null>(null);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const textInput = "mt-1 w-full rounded border border-slate-700 bg-[#080D17] p-2 text-sm text-slate-100";

  async function research(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    setPending(true); setError(""); setResult(null); setAnswer("");
    try {
      const capturedAt = new Date().toISOString();
      const sources = [{ source_id: "source_1", title: title.trim(), excerpt: excerpt.trim(), captured_at: capturedAt, url: null, facts: [] }];
      if (extraTitle.trim() && extraExcerpt.trim()) {
        sources.push({ source_id: "source_2", title: extraTitle.trim(), excerpt: extraExcerpt.trim(), captured_at: capturedAt, url: null, facts: [] });
      }
      const output = await researchDocuments13C2({ query: query.trim(), review: {
        product_label: product.trim(), device_model: device.trim(),
        device_supports_usb_pd: devicePd === "" ? null : devicePd === "true",
        required_power_w: Number(watts), required_voltage_v: Number(voltage), sources,
      }});
      setResult(output);
      onEvent("PRODUCT_RETRIEVAL", "Retrieved quoted passages and evaluated explicit supplied specifications without external document verification.", "CLOUD_RUN");
    } catch (e) { setError(e instanceof Error ? e.message : "Research failed."); }
    finally { setPending(false); }
  }

  async function explain() {
    if (!result || explaining) return;
    setExplaining(true); setError(""); setAnswer("");
    try {
      setAnswer(await explainEvidenceWithGemini13C2(result));
      onEvent("GEMINI_CITED_EXPLANATION", "An optional Gemini explanation was checked for citation IDs. Source authenticity remains unverified.", "CLOUD_RUN");
    } catch (e) { setError(e instanceof Error ? e.message : "Gemini explanation unavailable."); }
    finally { setExplaining(false); }
  }

  return <section id="document-research" className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#111827] p-5">
    <div className="flex items-center gap-2"><BookText size={18} className="text-sky-400"/><h2 className="font-semibold">Document-grounded product research</h2></div>
    <p className="mt-2 text-xs leading-6 text-slate-400">Paste actual source excerpts. Local hybrid keyword/character retrieval identifies cited passages and conservatively extracts explicit USB PD, output and cable specifications. Sources are user-supplied and not independently verified. No URL fetching.</p>
    <button type="button" disabled={!requestedProduct} onClick={()=>requestedProduct && setProduct(requestedProduct)} className="mt-3 rounded border border-slate-600 px-3 py-2 text-xs text-sky-300 disabled:opacity-40">Use current requested product</button>
    <form className="mt-4 space-y-3" onSubmit={e=>void research(e)}>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-slate-300">Product label<input required maxLength={150} className={textInput} value={product} onChange={e=>setProduct(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Device model<input required maxLength={120} className={textInput} value={device} onChange={e=>setDevice(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Required power W<input required min={1} max={240} type="number" className={textInput} value={watts} onChange={e=>setWatts(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Required voltage V<input required min={5} max={48} type="number" className={textInput} value={voltage} onChange={e=>setVoltage(e.target.value)}/></label>
        <label className="text-xs text-slate-300">Device USB PD support<select className={textInput} value={devicePd} onChange={e=>setDevicePd(e.target.value as typeof devicePd)}><option value="">Unknown</option><option value="true">Yes (reported)</option><option value="false">No (reported)</option></select></label>
        <label className="text-xs text-slate-300">Research question<input required minLength={5} maxLength={180} className={textInput} value={query} onChange={e=>setQuery(e.target.value)}/></label>
      </div>
      <label className="block text-xs text-slate-300">Source 1 title<input required minLength={3} maxLength={160} className={textInput} value={title} onChange={e=>setTitle(e.target.value)} placeholder="Manufacturer manual, PDF extract, product sheet"/></label>
      <label className="block text-xs text-slate-300">Source 1 original excerpt<textarea required minLength={10} maxLength={2000} rows={3} className={textInput} value={excerpt} onChange={e=>setExcerpt(e.target.value)} placeholder="Paste actual specification paragraphs"/></label>
      <label className="block text-xs text-slate-300">Source 2 title (optional)<input maxLength={160} className={textInput} value={extraTitle} onChange={e=>setExtraTitle(e.target.value)}/></label>
      <label className="block text-xs text-slate-300">Source 2 excerpt (optional)<textarea maxLength={2000} rows={2} className={textInput} value={extraExcerpt} onChange={e=>setExtraExcerpt(e.target.value)}/></label>
      <button disabled={pending} type="submit" className="rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-semibold text-slate-950 disabled:opacity-40">{pending ? "Researching..." : "Retrieve & evaluate source evidence"}</button>
    </form>
    {error && <p role="alert" className="mt-3 text-sm text-rose-300">{error}</p>}
    {result && <div aria-live="polite" className="mt-4 space-y-3 rounded-xl border border-slate-700 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold"><SearchCheck size={16} className="text-sky-300"/> {result.review.status.replace(/_/g," ")}</div>
      <p className="text-xs text-amber-200">{result.notice}</p>
      <p className="text-xs text-slate-300">Retrieved {result.passages.length} excerpts using local lexical/character retrieval. No external search or embeddings.</p>
      {result.stale_source_ids.length > 0 && <p className="text-xs text-amber-300">Older evidence: {result.stale_source_ids.join(", ")}</p>}
      {result.review.evidence_gaps.map((g,i)=><p key={i} className="text-xs text-rose-300">{g.kind}: {g.reason}</p>)}
      {result.passages.map(p=><div key={p.citation_id} className="rounded border border-slate-700 p-2 text-xs"><div className="font-semibold text-sky-300">[{p.citation_id}] {p.title}</div><blockquote className="mt-1 text-slate-300">{p.quote}</blockquote><p className="mt-1 text-slate-500">SHA256: {p.source_sha256.slice(0,12)}… · offset {p.start}–{p.end}</p></div>)}
      {optionalGemini13c2Enabled && <button type="button" disabled={explaining} onClick={()=>void explain()} className="rounded border border-sky-500 px-3 py-2 text-xs text-sky-300 disabled:opacity-40">{explaining ? "Checking Gemini output..." : "Ask Gemini for an optional cited explanation (may use quota)"}</button>}
      {answer && <div className="rounded border border-slate-700 p-3 text-xs"><div className="flex gap-2 items-center"><ShieldAlert size={14}/> Gemini summary (not independent verification)</div><p className="mt-1 text-slate-200">{answer}</p></div>}
    </div>}
  </section>;
}
