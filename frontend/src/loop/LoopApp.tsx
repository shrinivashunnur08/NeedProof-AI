import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api, photoToBase64,
  type Brief, type ChatResult, type City, type Insights, type LoopRequest, type Offer, type PhotoCheck,
  type Providers, type Shop,
} from "./api";

type Role = "shopper" | "shop" | "business";
type Turn = { role: "user" | "assistant"; text: string; result?: ChatResult };

const SAMPLE_PROMPTS: Record<string, string[]> = {
  singapore: [
    "I need a 65W USB-C PD charger for my laptop under S$60, my flight is tonight",
    "我需要一个65W USB-C PD笔记本充电器，60新币以内，今天要",
  ],
  "sao-paulo": ["Preciso de um carregador USB-C PD de 65W até R$ 250 hoje"],
  mumbai: ["मुझे आज ₹1000 के अंदर 65W USB-C PD लैपटॉप चार्जर चाहिए", "Need a 65W USB-C charger under ₹1,000 today"],
};
const PERSONA: Record<string, string> = { singapore: "Maya", "sao-paulo": "Lucas", mumbai: "Asha" };
const BRIEF_LANGS = [
  { id: "en", label: "English" }, { id: "zh", label: "中文" }, { id: "pt", label: "Português" }, { id: "hi", label: "हिन्दी" },
];

const STATUS_STYLE: Record<string, string> = {
  PHOTO_MATCHES_REQUEST: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/40",
  PHOTO_CONFLICTS_WITH_REQUEST: "bg-rose-500/15 text-rose-300 ring-rose-500/40",
  PHOTO_NEEDS_CLEARER_DETAIL: "bg-amber-500/15 text-amber-200 ring-amber-500/40",
  PHOTO_UNREADABLE: "bg-amber-500/15 text-amber-200 ring-amber-500/40",
  PHOTO_NOT_CHECKED: "bg-slate-600/30 text-slate-200 ring-slate-500/50",
};
const STATUS_TEXT: Record<string, string> = {
  PHOTO_MATCHES_REQUEST: "Photo matches the request",
  PHOTO_CONFLICTS_WITH_REQUEST: "Photo conflicts with the request",
  PHOTO_NEEDS_CLEARER_DETAIL: "Needs a clearer photo",
  PHOTO_UNREADABLE: "Photo not readable",
  PHOTO_NOT_CHECKED: "Not checked",
  NONE: "No photo yet",
};

function readParams() {
  const q = new URLSearchParams(window.location.search);
  const role = (q.get("role") as Role) || "shopper";
  return { role: ["shopper", "shop", "business"].includes(role) ? role : "shopper", city: q.get("city") || "singapore", shop: q.get("shop") || "" };
}

function writeParams(role: Role, city: string, shop?: string) {
  const q = new URLSearchParams({ role, city });
  if (shop) q.set("shop", shop);
  window.history.replaceState(null, "", `${window.location.pathname}?${q.toString()}`);
}

function Chip({ children, tone = "slate" }: { children: React.ReactNode; tone?: "slate" | "green" | "red" | "amber" | "teal" }) {
  const tones = {
    slate: "bg-slate-700/40 text-slate-300 ring-slate-600/50",
    green: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/40",
    red: "bg-rose-500/15 text-rose-300 ring-rose-500/40",
    amber: "bg-amber-500/15 text-amber-200 ring-amber-500/40",
    teal: "bg-teal-500/15 text-teal-200 ring-teal-500/40",
  };
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${tones[tone]}`}>{children}</span>;
}

function StatusChip({ status }: { status: string }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${STATUS_STYLE[status] ?? "bg-slate-700/40 text-slate-300 ring-slate-600/50"}`}>
      {STATUS_TEXT[status] ?? status}
    </span>
  );
}

function ErrorNote({ message }: { message: string }) {
  if (!message) return null;
  return <p role="alert" className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{message}</p>;
}

/* ------------------------------ Shopper ------------------------------ */

function OfferCard({ offer }: { offer: Offer }) {
  const verified = offer.photo_proof === "PHOTO_MATCHES_REQUEST";
  return (
    <li className="rounded-xl border border-slate-700/70 bg-slate-900/60 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold text-slate-100">{offer.shop} <span className="font-normal text-slate-400">· {offer.area}</span></p>
        <p className="font-mono text-sm text-slate-100">{offer.price}</p>
      </div>
      <p className="mt-0.5 text-sm text-slate-300">{offer.listing}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {verified ? <Chip tone="green">Photo-verified</Chip> : <Chip>Listing only (shop's claim)</Chip>}
        {offer.listed_stock > 0 ? <Chip tone="teal">Listed in stock: {offer.listed_stock}</Chip> : <Chip tone="red">Listed out of stock</Chip>}
        {offer.spec_check.issues.map((i) => <Chip key={i} tone="red">{i}</Chip>)}
        {offer.spec_check.matches.map((m) => <Chip key={m} tone="green">{m}</Chip>)}
        {offer.over_budget && <Chip tone="amber">Over budget</Chip>}
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Decision engine: <span className="text-slate-200">{offer.decision.state_text}</span>
        {offer.decision.next_best_proof ? <> · next proof: <span className="text-slate-200">{offer.decision.next_best_proof.replaceAll("_", " ").toLowerCase()}</span></> : null}
      </p>
    </li>
  );
}

function RequestTracker({ requestId }: { requestId: number }) {
  const [req, setReq] = useState<LoopRequest | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () => api.request(requestId).then((r) => { if (alive) setReq(r); }).catch(() => undefined);
    load();
    const t = window.setInterval(load, 3000);
    return () => { alive = false; window.clearInterval(t); };
  }, [requestId]);
  return (
    <div className="mt-3 rounded-xl border border-teal-500/30 bg-teal-500/5 p-3" aria-live="polite">
      <p className="text-sm font-semibold text-teal-200">Request #{requestId} sent to nearby shops · waiting for photo proof</p>
      {req && req.responses.length === 0 && <p className="mt-1 text-xs text-slate-400">No replies yet. Open the Shop tab in another window to reply as a shop.</p>}
      <ul className="mt-2 space-y-2">
        {req?.responses.map((r) => (
          <li key={r.id} className="rounded-lg bg-slate-900/70 p-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-slate-100">{r.shop_name}</span>
              {r.price != null && <span className="font-mono text-slate-300">{r.price}</span>}
              <StatusChip status={r.status} />
            </div>
            {r.check_result.issues.length > 0 && <p className="mt-1 text-xs text-rose-300">{r.check_result.issues.join(" · ")}</p>}
            {r.check_result.matches.length > 0 && <p className="mt-1 text-xs text-emerald-300">{r.check_result.matches.join(" · ")}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function AssistantTurn({ turn }: { turn: Turn }) {
  const r = turn.result;
  return (
    <div className="max-w-[46rem] rounded-2xl rounded-tl-sm border border-slate-700/60 bg-slate-800/60 p-4">
      <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-slate-100">{turn.text}</p>
      {r && r.offers.length > 0 && <ul className="mt-3 space-y-2">{r.offers.map((o) => <OfferCard key={o.shop_id + o.listing} offer={o} />)}</ul>}
      {r?.request && <RequestTracker requestId={r.request.id} />}
      {r && (
        <details className="mt-3 text-xs text-slate-400">
          <summary className="cursor-pointer select-none text-slate-300">How the agent worked ({r.trace.length} tool calls · {r.mode === "gemini" ? `Gemini ${r.model.latency_ms ?? "?"} ms` : r.mode})</summary>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            {r.trace.map((t, i) => (
              <li key={i}><span className="font-mono text-teal-200">{t.tool}</span>({Object.entries(t.args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")}) → {t.result}</li>
            ))}
          </ol>
          {r.model.error && <p className="mt-1 text-amber-300">Model fallback: {r.model.error}</p>}
          <p className="mt-1">Shop names, prices and decision states come from the store and the decision engine; Gemini chooses the tools and writes the explanation.</p>
        </details>
      )}
    </div>
  );
}

function ShopperView({ city }: { city: City }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    const next: Turn[] = [...turns, { role: "user", text: message }];
    setTurns(next); setDraft(""); setBusy(true); setError("");
    try {
      const result = await api.chat(city.id, next.map((t) => ({ role: t.role, text: t.text })));
      setTurns([...next, { role: "assistant", text: result.reply, result }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The assistant is unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Shopper assistant" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-slate-400">Shopping as <span className="font-semibold text-slate-200">{PERSONA[city.id] ?? "Demo shopper"} (demo)</span> in {city.name}. Write in any language.</p>
        {turns.length > 0 && <button type="button" onClick={() => setTurns([])} className="text-xs text-slate-400 underline hover:text-slate-200">New conversation</button>}
      </div>
      {turns.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {(SAMPLE_PROMPTS[city.id] ?? []).map((p) => (
            <button key={p} type="button" onClick={() => send(p)} className="rounded-full border border-slate-600 bg-slate-800/60 px-3 py-1.5 text-left text-sm text-slate-200 hover:border-teal-400 hover:text-white">{p}</button>
          ))}
        </div>
      )}
      <div className="flex flex-col gap-3">
        {turns.map((t, i) => t.role === "user"
          ? <div key={i} className="ml-auto max-w-[36rem] rounded-2xl rounded-tr-sm bg-teal-600/90 px-4 py-2.5 text-[15px] text-white">{t.text}</div>
          : <AssistantTurn key={i} turn={t} />)}
        {busy && <p role="status" className="text-sm text-slate-400">Gemini is checking nearby shops…</p>}
        <div ref={endRef} />
      </div>
      <ErrorNote message={error} />
      <form onSubmit={(e) => { e.preventDefault(); void send(draft); }} className="sticky bottom-3 flex gap-2 rounded-2xl border border-slate-700 bg-slate-900/95 p-2 backdrop-blur">
        <label htmlFor="shopper-input" className="sr-only">Describe what you need</label>
        <input id="shopper-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="What do you need today? Any language." className="min-w-0 flex-1 bg-transparent px-2 text-[15px] text-slate-100 placeholder:text-slate-500 focus:outline-none" />
        <button type="submit" disabled={busy || !draft.trim()} className="rounded-xl bg-teal-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">Ask</button>
      </form>
    </section>
  );
}

/* ------------------------------ Shop ------------------------------ */

function ClaimTable({ claim }: { claim: Record<string, unknown> }) {
  const rows = Object.entries(claim).filter(([, v]) => v !== null && v !== "" && !(Array.isArray(v) && v.length === 0));
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-slate-400">{k.replaceAll("_", " ")}</dt>
          <dd className="min-w-0 break-words text-slate-200">{Array.isArray(v) ? v.join(", ") : String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function ReplyForm({ req, shopId, onDone }: { req: LoopRequest; shopId: string; onDone: () => void }) {
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState("1");
  const [photo, setPhoto] = useState<{ data: string; mime: string; preview: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ claim: Record<string, unknown>; check: PhotoCheck; mode: string } | null>(null);

  async function onFile(file: File | undefined) {
    if (!file) return;
    try { setPhoto(await photoToBase64(file)); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Could not read photo"); }
  }

  async function submit() {
    setBusy(true); setError("");
    try {
      const r = await api.reply(req.id, {
        shop_id: shopId, price: price ? Number(price) : undefined, stock: stock ? Number(stock) : undefined,
        image_base64: photo?.data, image_mime: photo?.mime,
      });
      setResult(r); onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the reply");
    } finally { setBusy(false); }
  }

  const id = `req-${req.id}`;
  return (
    <div className="mt-3 grid gap-3 md:grid-cols-[1fr_1fr]">
      <div className="flex flex-col gap-2">
        <div className="flex gap-2">
          <label className="flex-1 text-xs text-slate-400" htmlFor={`${id}-price`}>Your price ({req.currency})
            <input id={`${id}-price`} inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-slate-100" />
          </label>
          <label className="w-24 text-xs text-slate-400" htmlFor={`${id}-stock`}>In stock
            <input id={`${id}-stock`} inputMode="numeric" value={stock} onChange={(e) => setStock(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-slate-100" />
          </label>
        </div>
        <label htmlFor={`${id}-photo`} className="flex cursor-pointer items-center justify-center rounded-lg border border-dashed border-slate-500 px-3 py-4 text-sm text-slate-300 hover:border-teal-400">
          {photo ? "Change photo" : "Send a shelfie: photo of the box or label"}
          <input id={`${id}-photo`} type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => void onFile(e.target.files?.[0])} />
        </label>
        {photo && <img src={photo.preview} alt="Photo to send" className="max-h-40 rounded-lg object-contain" />}
        <button type="button" onClick={() => void submit()} disabled={busy || !photo} className="rounded-lg bg-teal-500 px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">
          {busy ? "Gemini is reading the photo…" : photo ? "Send photo proof" : "Add a photo to send proof"}
        </button>
        <ErrorNote message={error} />
      </div>
      {result && (
        <div className="rounded-xl border border-slate-700 bg-slate-950/60 p-3" aria-live="polite">
          <div className="flex flex-wrap items-center gap-2"><StatusChip status={result.check.status} /><span className="text-xs text-slate-400">{result.mode === "gemini" ? "read by Gemini Vision" : "not read by a model"}</span></div>
          {result.check.matches.length > 0 && <p className="mt-2 text-xs text-emerald-300">✓ {result.check.matches.join(" · ")}</p>}
          {result.check.issues.length > 0 && <p className="mt-1 text-xs text-rose-300">✗ {result.check.issues.join(" · ")}</p>}
          {result.check.missing.length > 0 && <p className="mt-1 text-xs text-amber-200">? {result.check.missing.join(" · ")}</p>}
          <div className="mt-2"><ClaimTable claim={result.claim} /></div>
          <p className="mt-2 text-[11px] text-slate-500">AI-read shop evidence. Stronger than a listing, still not independent verification.</p>
        </div>
      )}
    </div>
  );
}

function ShopView({ city, shopId, setShopId }: { city: City; shopId: string; setShopId: (id: string) => void }) {
  const [shops, setShops] = useState<Shop[]>([]);
  const [requests, setRequests] = useState<LoopRequest[]>([]);
  const [open, setOpen] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.shops(city.id).then((s) => {
      setShops(s);
      if (!s.some((x) => x.id === shopId) && s[0]) setShopId(s[0].id);
    }).catch((e) => setError(e instanceof Error ? e.message : "Could not load shops"));
  }, [city.id, shopId, setShopId]);

  const load = useCallback(() => {
    api.cityRequests(city.id).then(setRequests).catch(() => undefined);
  }, [city.id]);
  useEffect(() => { load(); const t = window.setInterval(load, 3000); return () => window.clearInterval(t); }, [load]);

  const shop = shops.find((s) => s.id === shopId);
  return (
    <section aria-label="Shop inbox" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-slate-400">Continue as</span>
        {shops.map((s) => (
          <button key={s.id} type="button" onClick={() => setShopId(s.id)} aria-pressed={s.id === shopId}
            className={`rounded-full px-3 py-1 text-sm ring-1 ${s.id === shopId ? "bg-teal-500 text-slate-950 ring-teal-400" : "text-slate-300 ring-slate-600 hover:ring-teal-400"}`}>{s.name}</button>
        ))}
      </div>
      <ErrorNote message={error} />
      <p className="text-sm text-slate-300">Shopper requests near <span className="font-semibold">{shop?.name ?? "your shop"}</span> in {city.name}. Reply with a photo so Gemini can check it.</p>
      {requests.length === 0 && <p className="rounded-xl border border-slate-700 p-4 text-sm text-slate-400">No requests yet. Ask for something in the Shopper tab (or another window) and it appears here within seconds.</p>}
      <ul className="flex flex-col gap-3">
        {requests.map((r) => {
          const mine = r.responses.find((x) => x.shop_id === shopId);
          return (
            <li key={r.id} className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-slate-100">#{r.id} · {r.product}</p>
                <div className="flex gap-1.5">
                  {r.status === "ANSWERED" ? <Chip tone="green">Answered</Chip> : <Chip tone="amber">Open</Chip>}
                  {mine && <StatusChip status={mine.status} />}
                </div>
              </div>
              <p className="mt-1 text-sm text-slate-400">
                {Object.entries(r.specs).map(([k, v]) => `${k.replace("_w", "").replaceAll("_", " ")}: ${String(v)}`).join(" · ") || "No specific specs"}
                {r.budget ? ` · budget ${r.currency} ${r.budget}` : ""} · language {r.language}
              </p>
              {!mine && (open === r.id
                ? <ReplyForm req={r} shopId={shopId} onDone={load} />
                : <button type="button" onClick={() => setOpen(r.id)} className="mt-2 rounded-lg border border-teal-500/60 px-3 py-1.5 text-sm text-teal-200 hover:bg-teal-500/10">I have this: reply with photo</button>)}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/* ------------------------------ Business ------------------------------ */

function Sparkline({ values }: { values: number[] }) {
  const max = Math.max(1, ...values);
  const w = 112, h = 28;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - (v / max) * (h - 2) - 1}`).join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Requests per day, last 28 days">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.5" className="text-teal-300" />
    </svg>
  );
}

function BusinessView({ city }: { city: City }) {
  const [data, setData] = useState<Insights | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [lang, setLang] = useState("en");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [exportNote, setExportNote] = useState("");

  useEffect(() => {
    api.insights(city.id).then(setData).catch((e) => setError(e instanceof Error ? e.message : "Could not load insights"));
  }, [city.id]);

  async function makeBrief() {
    setBusy(true); setError("");
    try { setBrief(await api.brief(city.id, lang)); } catch (e) { setError(e instanceof Error ? e.message : "Brief failed"); } finally { setBusy(false); }
  }

  const maxUnmet = useMemo(() => Math.max(1, ...(data?.products.map((p) => p.unmet) ?? [1])), [data]);
  return (
    <section aria-label="Demand insights" className="flex flex-col gap-4">
      <p className="text-sm text-slate-300">What shoppers in {city.name} asked for in the last 28 days, and how much of it no shop confirmed.</p>
      <ErrorNote message={error} />
      <div className="overflow-x-auto rounded-xl border border-slate-700">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-slate-900 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr><th className="px-3 py-2">Product</th><th className="px-3 py-2">Asks</th><th className="px-3 py-2">Unmet</th><th className="px-3 py-2">Avg budget</th><th className="px-3 py-2">Week on week</th><th className="px-3 py-2">Next 7 days</th><th className="px-3 py-2">28-day trend</th></tr>
          </thead>
          <tbody>
            {data?.products.map((p) => (
              <tr key={p.product_key} className="border-t border-slate-800">
                <td className="px-3 py-2 text-slate-100">{p.product}{p.live_asks > 0 && <span className="ml-2"><Chip tone="teal">{p.live_asks} live</Chip></span>}</td>
                <td className="px-3 py-2 font-mono tabular-nums">{p.asks}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2"><span className="font-mono tabular-nums text-rose-200">{p.unmet}</span>
                    <span className="h-1.5 rounded bg-rose-400/70" style={{ width: `${(p.unmet / maxUnmet) * 80}px` }} /></div>
                </td>
                <td className="px-3 py-2 font-mono">{p.avg_budget ?? "–"}</td>
                <td className={`px-3 py-2 font-mono ${p.growth_pct >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{p.growth_pct >= 0 ? "+" : ""}{p.growth_pct}%</td>
                <td className="px-3 py-2 font-mono tabular-nums">{p.forecast_next_7_days}</td>
                <td className="px-3 py-2"><Sparkline values={p.daily_series} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && <p className="text-xs text-slate-500">{data.data_note} {data.method}</p>}
      <div className="flex flex-wrap items-end gap-2">
        <label htmlFor="brief-lang" className="text-xs text-slate-400">Brief language
          <select id="brief-lang" value={lang} onChange={(e) => setLang(e.target.value)} className="mt-1 block rounded-lg border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-slate-100">
            {BRIEF_LANGS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
        </label>
        <button type="button" onClick={() => void makeBrief()} disabled={busy} className="rounded-lg bg-teal-500 px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">{busy ? "Writing…" : "Write this week's brief with Gemini"}</button>
        <button type="button" onClick={() => api.exportBq().then((r) => setExportNote(`${r.rows} events exported. Load into BigQuery: ${r.next}`)).catch((e) => setError(String(e)))} className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200 hover:border-teal-400">Export for BigQuery</button>
      </div>
      {exportNote && <p className="break-all rounded-lg bg-slate-900 p-2 font-mono text-xs text-slate-300">{exportNote}</p>}
      {brief && (
        <article className="rounded-xl border border-teal-500/30 bg-teal-500/5 p-4">
          <p className="text-lg font-semibold text-slate-50">{brief.brief.headline}</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-200">{brief.brief.actions.map((a) => <li key={a}>{a}</li>)}</ul>
          <p className="mt-2 text-sm text-slate-300"><span className="text-slate-400">Biggest gap:</span> {brief.brief.biggest_gap}</p>
          <p className="mt-1 text-xs text-slate-500">{brief.brief.caution} · {brief.mode === "gemini" ? `Gemini, ${brief.model.latency_ms} ms` : brief.mode}</p>
        </article>
      )}
    </section>
  );
}

/* ------------------------------ Shell ------------------------------ */

export default function LoopApp() {
  const [initial] = useState(readParams);
  const [role, setRole] = useState<Role>(initial.role as Role);
  const [cityId, setCityId] = useState(initial.city);
  const [shopId, setShopId] = useState(initial.shop);
  const [cities, setCities] = useState<City[]>([]);
  const [providers, setProviders] = useState<Providers | null>(null);
  const [error, setError] = useState("");
  const [resetKey, setResetKey] = useState(0);

  useEffect(() => {
    api.status().then((s) => { setCities(s.cities); setProviders(s.providers); })
      .catch(() => setError("Backend not reachable. Start FastAPI on port 8000."));
  }, []);
  useEffect(() => { writeParams(role, cityId, role === "shop" ? shopId : undefined); }, [role, cityId, shopId]);

  const city = cities.find((c) => c.id === cityId) ?? cities[0];
  const tabs: { id: Role; label: string; hint: string }[] = [
    { id: "shopper", label: "Shopper", hint: "Ask in any language" },
    { id: "shop", label: "Shop", hint: "Reply with photo proof" },
    { id: "business", label: "Business", hint: "Unmet demand" },
  ];
  const otherWindow = `${window.location.pathname}?role=${role === "shop" ? "shopper" : "shop"}&city=${cityId}`;

  return (
    <div className="min-h-dvh bg-[#0a0f17] text-slate-100">
      <header className="border-b border-slate-800 bg-[#0b111b]">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-4">
          <div className="min-w-0">
            <p className="text-lg font-bold tracking-tight">NeedProof <span className="font-normal text-slate-400">· Know it's in stock before you go</span></p>
            <p className="text-xs text-slate-500">Gemini agent for shoppers · photo proof from shops · demand insights for business</p>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <label htmlFor="city" className="sr-only">City</label>
            <select id="city" value={cityId} onChange={(e) => setCityId(e.target.value)} className="rounded-lg border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm">
              {cities.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.symbol})</option>)}
            </select>
            {providers && (
              <span title={`${providers.gemini.model} · analytics: ${providers.analytics.label}`}>
                <Chip tone={providers.live_model ? "green" : "amber"}>{providers.gemini.label}{providers.live_model ? ` · ${providers.gemini.model}` : ""}</Chip>
              </span>
            )}
            <button type="button" onClick={() => api.reset().then(() => setResetKey((k) => k + 1))} className="text-xs text-slate-400 underline hover:text-slate-200">Reset demo</button>
          </div>
        </div>
        <nav aria-label="Role" className="mx-auto flex max-w-5xl gap-1 px-4">
          {tabs.map((t) => (
            <button key={t.id} type="button" onClick={() => setRole(t.id)} aria-current={role === t.id ? "page" : undefined}
              className={`border-b-2 px-3 pb-2 pt-1 text-sm ${role === t.id ? "border-teal-400 text-white" : "border-transparent text-slate-400 hover:text-slate-200"}`}>
              {t.label} <span className="hidden text-xs text-slate-500 sm:inline">· {t.hint}</span>
            </button>
          ))}
          <a href={otherWindow} target="_blank" rel="noreferrer" className="ml-auto self-center pb-2 text-xs text-teal-300 hover:underline">Open {role === "shop" ? "shopper" : "shop"} view in a new window ↗</a>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6" key={`${resetKey}-${cityId}`}>
        <ErrorNote message={error} />
        {city && role === "shopper" && <ShopperView city={city} />}
        {city && role === "shop" && <ShopView city={city} shopId={shopId} setShopId={setShopId} />}
        {city && role === "business" && <BusinessView city={city} />}
        <p className="mt-10 text-xs text-slate-500">All shops, listings and demand history are fictional demo data. The app never buys anything; listings are shop claims until a photo is checked.</p>
      </main>
    </div>
  );
}
