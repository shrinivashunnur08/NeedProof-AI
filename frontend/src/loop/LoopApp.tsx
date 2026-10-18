import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./google-theme.css";
import {
  api, photoToBase64, fileToBase64, type Draft, type InventoryItem, type InventoryUpload,
  type Brief, type ChatResult, type City, type Insights, type Intent, type LoopRequest, type NearbyShop, type Offer,
  type PhotoCheck, type ShopResponse, type ShopperLocation,
  type Providers, type Shop, type Analytics, type Profile, type BqForecast, type TrustReport, type ShopDashboard, type Basket, type ProofPlan,
  type EngineCatalog, type EngineRun,
} from "./api";

type Role = "shopper" | "shop" | "business" | "trust" | "engines";
type Turn = { role: "user" | "assistant"; text: string; result?: ChatResult };

const SAMPLE_PROMPTS: Record<string, string[]> = {
  singapore: [
    "I need a 65W USB-C PD charger for my laptop under S$60, my flight is tonight",
    "我需要一个65W USB-C PD笔记本充电器，60新币以内，今天要",
    "Travelling tomorrow: a 65W USB-C PD charger, a USB-C cable and a power bank, S$120 total",
  ],
  "sao-paulo": ["Preciso de um carregador USB-C PD de 65W até R$ 250 hoje", "Preciso de um carregador 65W, um cabo USB-C e um power bank até R$ 400"],
  mumbai: ["मुझे आज ₹1000 के अंदर 65W USB-C PD लैपटॉप चार्जर चाहिए", "Need a 65W USB-C charger, a USB-C cable and a power bank under ₹3,000"],
};
const PERSONA: Record<string, string> = { singapore: "Maya", "sao-paulo": "Lucas", mumbai: "Asha" };
const SAMPLE_PHOTOS = [
  { file: "1_charger_65w_correct.jpg", label: "65W charger" },
  { file: "2_charger_45w_wrong_wattage.jpg", label: "45W charger" },
  { file: "3_fake_brand_appel.jpg", label: "Fake brand" },
  { file: "4_mixer_grinder_wrong_item.jpg", label: "Mixer" },
  { file: "5_cable_not_charger.jpg", label: "Cable" },
];
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

/** Live updates for a city: Server-Sent Events push, plus refresh on focus and a slow safety poll. */
function useCityVersion(cityId: string): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const bump = () => setTick((t) => t + 1);
    let source: EventSource | null = null;
    try {
      source = new EventSource(`/api/v2/loop/cities/${cityId}/events`);
      source.addEventListener("change", bump);
    } catch { /* fall back to polling */ }
    const onVisible = () => { if (document.visibilityState === "visible") bump(); };
    window.addEventListener("focus", bump);
    document.addEventListener("visibilitychange", onVisible);
    const poll = window.setInterval(bump, 10000);
    return () => {
      source?.close();
      window.removeEventListener("focus", bump);
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(poll);
    };
  }, [cityId]);
  return tick;
}

function readParams() {
  const q = new URLSearchParams(window.location.search);
  const role = (q.get("role") as Role) || "shopper";
  return { role: ["shopper", "shop", "business", "trust", "engines"].includes(role) ? role : "shopper", city: q.get("city") || "singapore", shop: q.get("shop") || "" };
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


const LANG_NAMES: Record<string, string> = { en: "English", zh: "Chinese", pt: "Portuguese", hi: "Hindi", ta: "Tamil", ms: "Malay", es: "Spanish", mr: "Marathi" };

function IntentCard({ intent, mode, latency }: { intent: Intent; mode?: string; latency?: number }) {
  const fields: [string, string | null][] = [
    ["Item", intent.item],
    ["Wattage", intent.wattage_w ? `${intent.wattage_w}W` : null],
    ["Connector", intent.connector],
    ["USB PD", intent.usb_pd ? "required" : null],
    ["Device", intent.device_model],
    ["Budget", intent.budget_amount ? `${intent.budget_currency ?? ""} ${intent.budget_amount}`.trim() : null],
    ["Needed", intent.urgency],
    ["Place", intent.location_text],
    ["Language", LANG_NAMES[intent.language] ?? intent.language],
  ];
  return (
    <div className="mb-3 rounded-xl border border-indigo-400/30 bg-indigo-500/5 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-indigo-200">
        What I understood <span className="font-normal normal-case tracking-normal text-slate-400">· intent extracted by {mode === "gemini" ? `Gemini${latency ? `, ${latency} ms` : ""}` : mode}</span>
      </p>
      <dl className="mt-2 flex flex-wrap gap-1.5">
        {fields.filter(([, v]) => v).map(([k, v]) => (
          <div key={k} className="rounded-lg bg-slate-900/70 px-2 py-1 text-xs"><dt className="inline text-slate-400">{k}: </dt><dd className="inline text-slate-100">{v}</dd></div>
        ))}
        {intent.features.filter((f) => !/usb-?c|pd|power delivery|\d+\s*w/i.test(f)).slice(0, 4).map((f) => (
          <div key={f} className="rounded-lg bg-slate-900/70 px-2 py-1 text-xs text-slate-200">{f}</div>
        ))}
      </dl>
      {intent.missing_info.length > 0 && (
        <p className="mt-2 text-xs text-amber-200">Still needed: {intent.missing_info.join(", ")}</p>
      )}
    </div>
  );
}

/* Google Maps: Static API image with numbered pins (key restricted to this site) + Directions links. */
const mapsConfig = { key: "" };

function directionsUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;
}

function DirectionsLink({ lat, lng }: { lat?: number | null; lng?: number | null }) {
  if (lat == null || lng == null) return null;
  return <a href={directionsUrl(lat, lng)} target="_blank" rel="noreferrer" className="text-xs font-semibold text-teal-300 hover:underline">Directions ↗</a>;
}

type Pin = { id: string; name: string; lat: number; lng: number; verified: boolean };

function ShopMap({ origin, pins }: { origin?: { lat?: number | null; lng?: number | null; label?: string | null } | null; pins: Pin[] }) {
  const shown = pins.slice(0, 9);
  if (!mapsConfig.key || shown.length === 0) return null;
  const params = new URLSearchParams({ size: "640x280", scale: "2", maptype: "roadmap", key: mapsConfig.key });
  const parts: string[] = [];
  if (origin?.lat != null && origin?.lng != null) parts.push(`markers=${encodeURIComponent(`color:blue|label:Y|${origin.lat},${origin.lng}`)}`);
  shown.forEach((p, i) => parts.push(`markers=${encodeURIComponent(`color:${p.verified ? "green" : "red"}|label:${i + 1}|${p.lat},${p.lng}`)}`));
  const src = `https://maps.googleapis.com/maps/api/staticmap?${params.toString()}&${parts.join("&")}`;
  return (
    <figure className="mt-3 overflow-hidden rounded-xl border border-slate-700/70 bg-slate-900/40">
      <img src={src} alt={`Map of ${shown.length} shops near ${origin?.label ?? "you"}`} className="h-56 w-full object-cover" loading="lazy" />
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 p-3 text-xs text-slate-300">
        <span><span className="font-semibold text-sky-300">Y</span> you</span>
        {shown.map((p, i) => (
          <span key={p.id} className="flex items-center gap-1.5">
            <span className={`font-semibold ${p.verified ? "text-emerald-300" : "text-rose-300"}`}>{i + 1}</span>{p.name}
            <DirectionsLink lat={p.lat} lng={p.lng} />
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

function ProofPlanCard({ p }: { p: ProofPlan }) {
  if (!p.ranked.length) return null;
  return (
    <details className="mt-3 rounded-xl border border-slate-700/70 bg-slate-900/40 p-3" open>
      <summary className="cursor-pointer select-none text-sm font-semibold text-slate-100">Who is worth asking for proof first <span className="text-xs font-normal text-slate-400">· {p.advice}</span></summary>
      <table className="mt-2 w-full text-sm">
        <thead className="text-left text-xs text-slate-500"><tr><th className="py-1">Shop</th><th>Has it?</th><th>Replies</th><th title="Expected benefit of getting proof minus the cost of waiting (EVSI)">Value of asking</th><th /></tr></thead>
        <tbody>{p.ranked.map((r) => (
          <tr key={r.shop_id} className="border-t border-slate-800 text-slate-300">
            <td className="py-1 text-slate-100">{r.shop}<span className="block text-[11px] text-slate-500">{r.basis}</span></td>
            <td className="font-mono">{Math.round(r.p_has_it * 100)}%</td>
            <td className="font-mono">{Math.round(r.reply_chance * 100)}%<span className="ml-1 font-sans text-[10px] text-slate-500">{r.history}</span></td>
            <td className="font-mono">{r.net_value > 0 ? "+" : ""}{p.currency ?? ""} {r.net_value.toFixed(2)}</td>
            <td>{r.worth_asking ? <Chip tone="green">Worth asking</Chip> : <Chip>{r.skip_reason ? r.skip_reason.replaceAll("_", " ").toLowerCase() : "low value"}</Chip>}</td>
          </tr>))}</tbody>
      </table>
      <p className="mt-1 text-[11px] text-slate-500">{p.engine}. {p.assumptions}</p>
    </details>
  );
}

function BasketCard({ b }: { b: Basket }) {
  if (b.status !== "OPTIMAL" && b.status !== "FEASIBLE") {
    return (
      <div className="mt-3 rounded-xl border border-amber-400/40 bg-amber-500/5 p-3 text-sm text-amber-100">
        <p className="font-semibold">Could not plan all {b.items.length} items</p>
        <p className="mt-1">{b.missing?.length ? `No shop lists: ${b.missing.join(", ")}.` : b.reason}</p>
      </div>
    );
  }
  return (
    <div className="mt-3 rounded-xl border border-teal-500/40 bg-teal-500/5 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold text-slate-100">Best plan for {b.items.length} items · {b.shops.length} shop{b.shops.length !== 1 ? "s" : ""}</p>
        <p className="font-mono text-lg text-slate-50">{b.total}{b.budget && <span className="ml-1 text-xs text-slate-400">of {b.budget}</span>}</p>
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {b.shops.map((s) => (
          <div key={s.shop_id} className="rounded-lg border border-slate-700 bg-slate-900/60 p-2 text-sm">
            <p className="flex items-center justify-between gap-2 font-semibold text-slate-100">
              <span>{s.shop} <span className="font-normal text-slate-400">· {s.area}{s.distance_km != null ? ` · ${s.distance_km.toFixed(1)} km` : ""}</span></span>
              <DirectionsLink lat={s.lat} lng={s.lng} />
            </p>
            <ul className="mt-1 space-y-0.5 text-slate-300">
              {b.lines.filter((ln) => ln.shop_id === s.shop_id).map((ln) => (
                <li key={ln.listing} className="flex justify-between gap-2"><span>{ln.listing}</span>
                  <span className="flex items-center gap-1.5">{ln.proof === "PHOTO_MATCHES_REQUEST" ? <Chip tone="green">Photo-verified</Chip> : <Chip>Listed</Chip>}<span className="font-mono">{ln.price}</span></span></li>
              ))}
            </ul>
            <p className="mt-1 text-right text-xs text-slate-400">Subtotal <span className="font-mono">{s.subtotal}</span></p>
          </div>
        ))}
      </div>
      {b.baselines && (
        <p className="mt-2 text-xs text-slate-400">
          Compared with: cheapest item each time <span className="font-mono text-slate-200">{b.baselines.cheapest_item_first.total}</span> across {b.baselines.cheapest_item_first.shops} shops
          {!b.baselines.cheapest_item_first.fits_max_shops && <span className="text-amber-200"> (more shops than you want)</span>}
          {b.baselines.single_shop ? <> · everything at {b.baselines.single_shop.shop} <span className="font-mono text-slate-200">{b.baselines.single_shop.total}</span></> : <> · no single shop has everything</>}
        </p>
      )}
      <p className="mt-1 text-[11px] text-slate-500">{b.solver} · max {b.max_shops} shops · solved in {b.solve_ms} ms · {b.note}</p>
    </div>
  );
}

function NearbyList({ shops, live }: { shops: NearbyShop[]; live: Map<string, ShopResponse> }) {
  if (shops.length === 0) return null;
  return (
    <div className="mt-3 rounded-xl border border-slate-700/70 bg-slate-900/40 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Real shops nearby <span className="font-normal normal-case tracking-normal text-slate-500">· from {shops[0].source === "google_places" ? "Google Places" : "OpenStreetMap"} · no online stock info, asked for photo proof</span></p>
      <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
        {shops.slice(0, 10).map((n) => {
          const reply = live.get(n.shop_id);
          return (
            <li key={n.shop_id} className="flex min-w-0 items-center justify-between gap-2 rounded-lg bg-slate-900/70 px-2 py-1.5 text-sm">
              <span className="min-w-0 truncate text-slate-100">{n.shop}<span className="text-slate-500"> · {n.area}</span></span>
              <span className="flex shrink-0 items-center gap-1.5">
                {n.distance_km != null && <span className="font-mono text-xs text-slate-400">{n.distance_km.toFixed(1)} km</span>}
                <DirectionsLink lat={n.lat} lng={n.lng} />
                {reply && <StatusChip status={reply.status} />}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const ANALYSIS_STEPS = ["Identifying the item", "Reading ratings and labels", "Checking authenticity cues", "Comparing with the request"];

function AnalysingSteps() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setStep((x) => Math.min(x + 1, ANALYSIS_STEPS.length - 1)), 700);
    return () => window.clearInterval(t);
  }, []);
  return (
    <ol className="space-y-1 text-xs" aria-live="polite">
      {ANALYSIS_STEPS.map((label, i) => (
        <li key={label} className={i < step ? "text-emerald-300" : i === step ? "text-teal-200" : "text-slate-500"}>
          {i < step ? "✓" : i === step ? "◌" : "·"} {label}{i === step ? "…" : ""}
        </li>
      ))}
    </ol>
  );
}

function PhotoAnalysis({ claim, check, mode, latency }: { claim: Record<string, unknown>; check: PhotoCheck; mode: string; latency?: number }) {
  const c = claim as {
    product_category?: string; is_requested_item_type?: boolean | null; brand?: string; model_number?: string; product_name?: string;
    wattage_w?: number; connector?: string; usb_pd?: boolean | null; visible_price?: number; visible_currency?: string;
    authenticity_cues?: string[]; concerns?: string[]; confidence?: number; analysis_summary?: string;
  };
  const conf = Math.round((c.confidence ?? 0) * 100);
  const row = (label: string, value: React.ReactNode, tone: "ok" | "bad" | "plain" = "plain") => (
    <div className="grid grid-cols-[7.5rem_1fr] gap-2">
      <dt className="text-slate-400">{label}</dt>
      <dd className={`min-w-0 break-words ${tone === "ok" ? "text-emerald-300" : tone === "bad" ? "text-rose-300" : "text-slate-100"}`}>{value}</dd>
    </div>
  );
  return (
    <div className="rounded-xl border border-indigo-400/30 bg-slate-950/70 p-3" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-indigo-200">Gemini Vision analysis</p>
        <StatusChip status={check.status} />
      </div>
      {mode !== "gemini" ? (
        <p className="mt-2 text-xs text-slate-400">{check.issues[0] ?? "The photo was not read by a model."}</p>
      ) : (
        <>
          {c.analysis_summary && <p className="mt-2 text-sm text-slate-200">{c.analysis_summary}</p>}
          <dl className="mt-3 space-y-1.5 text-xs">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">1 · Identified</p>
            {row("Item type", `${c.product_category ?? "unknown"}${c.is_requested_item_type === false ? " (not what was asked)" : ""}`, c.is_requested_item_type === false ? "bad" : "plain")}
            {row("Brand / model", [c.brand, c.model_number].filter(Boolean).join(" · ") || "not visible")}
            <p className="pt-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">2 · Read from the label</p>
            {row("Wattage", c.wattage_w ? `${c.wattage_w}W` : "not visible")}
            {row("Connector", c.connector ?? "not visible")}
            {row("USB PD", c.usb_pd == null ? "not visible" : c.usb_pd ? "yes" : "no")}
            {c.visible_price != null && row("Price on tag", `${c.visible_currency ?? ""} ${c.visible_price}`)}
            <p className="pt-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">3 · Authenticity</p>
            {row("Cues seen", (c.authenticity_cues ?? []).join(", ") || "none visible", (c.authenticity_cues ?? []).length ? "ok" : "plain")}
            {row("Red flags", (c.concerns ?? []).join(", ") || "none", (c.concerns ?? []).length ? "bad" : "ok")}
            <p className="pt-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">4 · Against the request</p>
            {check.matches.length > 0 && row("Matches", check.matches.join(" · "), "ok")}
            {check.issues.length > 0 && row("Conflicts", check.issues.join(" · "), "bad")}
            {(check.cautions ?? []).length > 0 && row("Cautions", (check.cautions ?? []).join(" · "))}
          </dl>
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
            <span>Model confidence</span>
            <span className="h-1.5 w-28 overflow-hidden rounded bg-slate-800"><span className="block h-full bg-indigo-400" style={{ width: `${conf}%` }} /></span>
            <span className="font-mono">{conf}%</span>
            {latency != null && <span className="ml-auto font-mono">{latency} ms</span>}
          </div>
        </>
      )}
      <p className="mt-2 text-[11px] text-slate-500">AI-read shop evidence: stronger than a listing, still not independent verification. The verdict comes from code comparing these fields with the request.</p>
    </div>
  );
}

function LocationBar({ loc, busy, error, onDetect, onSearch, demo }: {
  loc: ShopperLocation | null; busy: boolean; error: string; demo: boolean;
  onDetect: () => void; onSearch: (q: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [q, setQ] = useState("");
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span aria-hidden="true">📍</span>
      {editing ? (
        <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) { onSearch(q.trim()); setEditing(false); } }}>
          <label htmlFor="place" className="sr-only">Area or address</label>
          <input id="place" autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Area, street or city" className="w-56 rounded-lg border border-slate-600 bg-slate-950 px-2 py-1 text-sm" />
          <button type="submit" className="rounded-lg bg-teal-500 px-2.5 py-1 text-xs font-semibold text-slate-950">Use</button>
          <button type="button" onClick={() => setEditing(false)} className="text-xs text-slate-400 underline">Cancel</button>
        </form>
      ) : (
        <>
          <span className="text-slate-100">{busy ? "Finding your location…" : loc ? loc.label : demo ? "City centre" : "Location not set"}</span>
          {loc && !busy && (
            <span className="text-xs text-slate-400">
              · {loc.detected ? "detected" : "chosen"} · {loc.shopsFound} real shops nearby{loc.shopsFound ? ` (${loc.source === "google_places" ? "Google Places" : "OpenStreetMap"})` : ""}
            </span>
          )}
          <button type="button" onClick={() => setEditing(true)} className="text-xs text-teal-300 underline">Change</button>
          <button type="button" onClick={onDetect} className="text-xs text-slate-400 underline">Detect</button>
        </>
      )}
      {error && <span className="text-xs text-amber-300">{error}</span>}
    </div>
  );
}


function EvidenceDrawer({ offer, live }: { offer: Offer; live?: ShopResponse }) {
  const status = live?.status ?? offer.photo_proof;
  const steps: { label: string; detail: string; state: "done" | "bad" | "todo" }[] = [
    { label: "Shop listing", detail: `${offer.listing}, ${offer.price}, ${offer.listed_stock > 0 ? `${offer.listed_stock} in stock` : "out of stock"} (the shop's own claim)`, state: "done" },
    {
      label: "Photo proof read by Gemini Vision",
      detail: status === "PHOTO_MATCHES_REQUEST" ? "Photo matches the request"
        : status && status !== "NONE" ? (STATUS_TEXT[status] ?? status) : "Not sent yet; the shop has been asked",
      state: status === "PHOTO_MATCHES_REQUEST" ? "done" : status && status !== "NONE" ? "bad" : "todo",
    },
    { label: "Independent verification", detail: "Not yet available (for example a marketplace audit or a store visit)", state: "todo" },
  ];
  const d = offer.decision;
  return (
    <div className="mt-3 space-y-3 rounded-lg border border-slate-700 bg-slate-950/60 p-3 text-xs">
      <div>
        <p className="font-semibold uppercase tracking-wide text-slate-400">Evidence ladder</p>
        <ol className="mt-1.5 space-y-1.5">
          {steps.map((st, i) => (
            <li key={st.label} className="flex gap-2">
              <span className={`mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${st.state === "done" ? "bg-emerald-500 text-slate-950" : st.state === "bad" ? "bg-rose-500 text-slate-950" : "bg-slate-700 text-slate-300"}`}>{i + 1}</span>
              <span><span className="text-slate-100">{st.label}</span> <span className="text-slate-400">· {st.detail}</span></span>
            </li>
          ))}
        </ol>
      </div>
      <div>
        <p className="font-semibold uppercase tracking-wide text-slate-400">Spec check against your need</p>
        <p className="mt-1 text-emerald-300">{offer.spec_check.matches.join(" · ") || "No matching specs confirmed"}</p>
        {offer.spec_check.issues.length > 0 && <p className="text-rose-300">{offer.spec_check.issues.join(" · ")}</p>}
      </div>
      <div>
        <p className="font-semibold uppercase tracking-wide text-slate-400">Decision engine (Evidence Passport + Next-Best-Proof)</p>
        <p className="mt-1 text-slate-200">{d.state_text}{d.trust_state ? ` · trust: ${d.trust_state.replaceAll("_", " ").toLowerCase()}` : ""}{d.conflicts ? ` · ${d.conflicts} conflicts` : ""}</p>
        {d.next_checks && d.next_checks.length > 0 && (
          <ol className="mt-1.5 list-decimal space-y-1 pl-4 text-slate-300">
            {d.next_checks.map((c) => <li key={c.label}><span className="text-slate-100">{c.label}</span> · {c.reason}</li>)}
          </ol>
        )}
        <p className="mt-1.5 text-slate-500">Purchase is never authorised by the app{d.snapshot_sha256 ? ` · snapshot ${d.snapshot_sha256.slice(0, 12)}` : ""}</p>
      </div>
    </div>
  );
}

function OfferCard({ offer, live }: { offer: Offer; live?: ShopResponse }) {
  const [open, setOpen] = useState(false);
  const status = live?.status ?? offer.photo_proof;
  const verified = status === "PHOTO_MATCHES_REQUEST";
  return (
    <li className="rounded-xl border border-slate-700/70 bg-slate-900/60 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold text-slate-100">{offer.shop} <span className="font-normal text-slate-400">· {offer.area}{offer.distance_km != null ? ` · ${offer.distance_km.toFixed(1)} km` : ""}</span></p>
        <p className="flex items-center gap-3"><DirectionsLink lat={offer.lat} lng={offer.lng} /><span className="font-mono text-sm text-slate-100">{offer.price}</span></p>
      </div>
      <p className="mt-0.5 text-sm text-slate-300">{offer.listing}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {verified ? <Chip tone="green">Photo-verified</Chip>
          : live ? <StatusChip status={live.status} /> : <Chip>Listing only (shop's claim)</Chip>}
        {offer.listed_stock > 0 ? <Chip tone="teal">Listed in stock: {offer.listed_stock}</Chip> : <Chip tone="red">Listed out of stock</Chip>}
        {offer.spec_check.issues.map((i) => <Chip key={i} tone="red">{i}</Chip>)}
        {offer.spec_check.matches.map((m) => <Chip key={m} tone="green">{m}</Chip>)}
        {offer.over_budget && <Chip tone="amber">Over budget</Chip>}
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Decision engine: <span className="text-slate-200">{offer.decision.state_text}</span>
        {offer.decision.next_best_proof ? <> · next proof: <span className="text-slate-200">{offer.decision.next_best_proof.replaceAll("_", " ").toLowerCase()}</span></> : null}
      </p>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="mt-2 text-xs font-semibold text-indigo-300 hover:underline">
        {open ? "Hide evidence" : "Why this answer? See the evidence"}
      </button>
      {open && <EvidenceDrawer offer={offer} live={live} />}
    </li>
  );
}

function RequestTracker({ requestId, req }: { requestId: number; req: LoopRequest | null }) {
  return (
    <div className="mt-3 rounded-xl border border-teal-500/30 bg-teal-500/5 p-3" aria-live="polite">
      <p className="text-sm font-semibold text-teal-200">Request #{requestId} sent to nearby shops · {req?.status === "ANSWERED" ? "photo proof received" : "waiting for photo proof"} <span className="ml-1 inline-block h-2 w-2 animate-pulse rounded-full bg-teal-300 align-middle" aria-hidden="true" /> <span className="text-xs font-normal text-slate-400">live</span></p>
      {req && req.responses.length === 0 && <p className="mt-1 text-xs text-slate-400">No replies yet. Open the Shop tab in another window to reply as a shop.</p>}
      <ul className="mt-2 space-y-2">
        {req?.responses.map((r) => (
          <li key={r.id} className="rounded-lg bg-slate-900/70 p-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-slate-100">{r.shop_name}</span>
              {r.price != null && <span className="font-mono text-slate-300">{r.price}</span>}
              <StatusChip status={r.status} />
              {r.evidence_class === "SHOP_CATALOG_PHOTO_READ_BY_AI" && <Chip tone="amber">Catalog photo</Chip>}
            </div>
            {r.message && <p className="mt-1 text-sm text-slate-200">“{r.message}”</p>}
            {typeof r.claim.analysis_summary === "string" && <p className="mt-1 text-xs text-slate-300"><span className="text-indigo-200">Gemini Vision:</span> {r.claim.analysis_summary}</p>}
            {r.check_result.issues.length > 0 && <p className="mt-1 text-xs text-rose-300">{r.check_result.issues.join(" · ")}</p>}
            {r.check_result.matches.length > 0 && <p className="mt-1 text-xs text-emerald-300">{r.check_result.matches.join(" · ")}</p>}
            {(r.check_result.cautions ?? []).length > 0 && <p className="mt-1 text-xs text-amber-200">{(r.check_result.cautions ?? []).join(" · ")}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function AssistantTurn({ turn, version }: { turn: Turn; version: number }) {
  const r = turn.result;
  const requestId = r?.request?.id;
  const [req, setReq] = useState<LoopRequest | null>(null);
  useEffect(() => {
    if (!requestId) return;
    let alive = true;
    api.request(requestId).then((x) => { if (alive) setReq(x); }).catch(() => undefined);
    return () => { alive = false; };
  }, [requestId, version]);
  const latestByShop = new Map<string, ShopResponse>();
  for (const x of req?.responses ?? []) latestByShop.set(x.shop_id, x);
  // A shop's reply is about one product: apply it only to that listing (or, for a plain photo reply,
  // to listings that meet the request), never to every card from the same shop.
  const liveFor = (o: Offer) => {
    const x = latestByShop.get(o.shop_id);
    if (!x) return undefined;
    return (x.inventory_product ? x.inventory_product === o.listing : o.spec_check.ok) ? x : undefined;
  };
  return (
    <div className="max-w-[46rem] rounded-2xl rounded-tl-sm border border-slate-700/60 bg-slate-800/60 p-4">
      {r?.intent && <IntentCard intent={r.intent} mode={r.intent_model?.mode} latency={r.intent_model?.latency_ms} />}
      {r?.remembered && r.remembered.length > 0 && (
        <p className="mb-2 flex flex-wrap items-center gap-1.5 text-xs text-violet-200">
          <Chip tone="teal">Remembered</Chip>{r.remembered.join(" · ")}<span className="text-slate-400">(say otherwise to change it)</span>
        </p>
      )}
      <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-slate-100">
        {turn.text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
          part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part.replace(/^\* /gm, "• "))}
      </p>
      {r?.basket && <BasketCard b={r.basket} />}
      {r && r.offers.length > 0 && <ul className="mt-3 space-y-2">{r.offers.map((o) => <OfferCard key={o.shop_id + o.listing} offer={o} live={liveFor(o)} />)}</ul>}
      {r?.proof_plan && r.offers.length > 0 && <ProofPlanCard p={r.proof_plan} />}
      {r?.nearby && <NearbyList shops={r.nearby} live={latestByShop} />}
      {r && (r.offers.length > 0 || (r.nearby ?? []).length > 0) && (
        <ShopMap origin={r.location?.lat != null ? r.location : r.location ? { lat: r.location.city.lat, lng: r.location.city.lng, label: r.location.city.name } : null} pins={[
          ...r.offers.filter((o, i, a) => o.lat != null && o.lng != null && a.findIndex((x) => x.shop_id === o.shop_id) === i)
            .map((o) => ({ id: o.shop_id, name: o.shop, lat: o.lat as number, lng: o.lng as number,
              verified: (latestByShop.get(o.shop_id)?.status ?? o.photo_proof) === "PHOTO_MATCHES_REQUEST" })),
          ...(r.nearby ?? []).filter((n) => n.lat != null && n.lng != null)
            .map((n) => ({ id: n.shop_id, name: n.shop, lat: n.lat as number, lng: n.lng as number,
              verified: latestByShop.get(n.shop_id)?.status === "PHOTO_MATCHES_REQUEST" })),
        ]} />
      )}
      {r?.request && <RequestTracker requestId={r.request.id} req={req} />}
      {r?.addon && (
        <p className="mt-3 rounded-lg border border-violet-400/30 bg-violet-500/10 px-3 py-2 text-sm text-violet-100">
          Tip for you: {r.addon.note}. Ask the shop if you need one too. <span className="text-xs text-slate-400">(basket analysis, 14B.2)</span>
        </p>
      )}
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

function ShopperView({ city, loc, onMoved }: { city: City; loc: ShopperLocation | null; onMoved: (c: City, lat?: number, lng?: number, label?: string) => void }) {
  const version = useCityVersion(city.id);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const persona = PERSONA[city.id] ?? "Shopper";
  const shopperId = `demo-${city.id}-${persona.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`.slice(0, 40);
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns]);
  useEffect(() => {
    let alive = true;
    api.profile(shopperId).then((x) => { if (alive) setProfile(x.profile); }).catch(() => undefined);
    return () => { alive = false; };
  }, [shopperId]);

  async function forget() {
    try { await api.forget(shopperId); setProfile(null); } catch (e) { setError(e instanceof Error ? e.message : "Could not forget profile"); }
  }

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    const next: Turn[] = [...turns, { role: "user", text: message }];
    setTurns(next); setDraft(""); setBusy(true); setError("");
    try {
      const result = await api.chat(city.id, next.map((t) => ({ role: t.role, text: t.text })), loc && loc.cityId === city.id ? loc : null,
        { id: shopperId, name: persona });
      setTurns([...next, { role: "assistant", text: result.reply, result }]);
      if (result.profile !== undefined) setProfile(result.profile);
      if (result.location && result.location.city.id !== city.id) {
        onMoved(result.location.city, result.location.lat, result.location.lng, result.location.label);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "The assistant is unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Shopper assistant" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-slate-400">Shopping as <span className="font-semibold text-slate-200">{persona}</span> in {city.name} ({city.symbol}). Write in any language.</p>
        {turns.length > 0 && <button type="button" onClick={() => setTurns([])} className="text-xs text-slate-400 underline hover:text-slate-200">New conversation</button>}
      </div>
      {profile && (profile.device || profile.needs.length > 0 || profile.budget) && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-violet-400/30 bg-violet-500/5 px-3 py-2 text-xs text-slate-300">
          <span className="font-semibold text-violet-200">What NeedProof remembers about {persona}:</span>
          {profile.device && <Chip>device {profile.device}</Chip>}
          {profile.budget && <Chip>usual budget {city.symbol}{profile.budget}</Chip>}
          {profile.language && <Chip>language {profile.language}</Chip>}
          {profile.needs.slice(-3).map((n, i) => <Chip key={i}>{n.item}{n.wattage_w ? ` ${n.wattage_w}W` : ""}{n.at ? ` · ${n.at}` : ""}</Chip>)}
          <button type="button" onClick={() => void forget()} className="ml-auto text-rose-200 underline hover:text-rose-100">Forget me</button>
        </div>
      )}
      {turns.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {(SAMPLE_PROMPTS[city.id] ?? ["I need a 65W USB-C PD charger for my laptop today", "I need a laptop charger", "USB-C cable for fast charging near me"]).map((p) => (
            <button key={p} type="button" onClick={() => send(p)} className="rounded-full border border-slate-600 bg-slate-800/60 px-3 py-1.5 text-left text-sm text-slate-200 hover:border-teal-400 hover:text-white">{p}</button>
          ))}
        </div>
      )}
      <div className="flex flex-col gap-3">
        {turns.map((t, i) => t.role === "user"
          ? <div key={i} className="ml-auto max-w-[36rem] rounded-2xl rounded-tr-sm bg-teal-600/90 px-4 py-2.5 text-[15px] text-white">{t.text}</div>
          : <AssistantTurn key={i} turn={t} version={version} />)}
        {busy && <p role="status" className="text-sm text-slate-400">Gemini is understanding your request and checking nearby shops…</p>}
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

function ReplyForm({ req, shopId, onDone }: { req: LoopRequest; shopId: string; onDone: () => void }) {
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState("1");
  const [photo, setPhoto] = useState<{ data: string; mime: string; preview: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ claim: Record<string, unknown>; check: PhotoCheck; mode: string; model: { latency_ms?: number } } | null>(null);

  async function onFile(file: File | undefined) {
    if (!file) return;
    try { setPhoto(await photoToBase64(file)); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Could not read photo"); }
  }

  async function loadSample(file: string) {
    try {
      const blob = await fetch(`/samples/${file}`).then((r) => r.blob());
      setPhoto(await photoToBase64(new File([blob], file, { type: blob.type || "image/jpeg" })));
      setError("");
    } catch { setError("Could not load the sample photo"); }
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
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-400">
          <span>Or try a sample:</span>
          {SAMPLE_PHOTOS.map((p) => (
            <button key={p.file} type="button" onClick={() => void loadSample(p.file)} className="rounded-full border border-slate-600 px-2 py-0.5 text-slate-200 hover:border-teal-400">{p.label}</button>
          ))}
        </div>
        {photo && <img src={photo.preview} alt="Photo to send" className="max-h-40 rounded-lg object-contain" />}
        <button type="button" onClick={() => void submit()} disabled={busy || !photo} className="rounded-lg bg-teal-500 px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">
          {busy ? "Gemini is reading the photo…" : photo ? "Send photo proof" : "Add a photo to send proof"}
        </button>
        <ErrorNote message={error} />
      </div>
      {busy && !result && (
        <div className="rounded-xl border border-indigo-400/30 bg-slate-950/70 p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-indigo-200">Gemini Vision is analysing the photo</p>
          <AnalysingSteps />
        </div>
      )}
      {result && <PhotoAnalysis claim={result.claim} check={result.check} mode={result.mode} latency={result.model?.latency_ms} />}
    </div>
  );
}

function InventoryPanel({ shopId, onChanged, hideTable = false }: { shopId: string; onChanged: () => void; hideTable?: boolean }) {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [sheet, setSheet] = useState<File | null>(null);
  const [photos, setPhotos] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<InventoryUpload | null>(null);
  const [reload, setReload] = useState(0);
  const [open, setOpen] = useState<boolean | null>(null);
  useEffect(() => {
    let alive = true;
    api.inventory(shopId).then((x) => {
      if (!alive) return;
      setItems(x);
      setOpen((prev) => prev ?? x.length === 0);  // start open only when there is nothing yet
    }).catch(() => undefined);
    return () => { alive = false; };
  }, [shopId, reload]);

  async function run(fn: () => Promise<InventoryUpload>) {
    setBusy(true); setError("");
    try { setSummary(await fn()); setReload((n) => n + 1); onChanged(); setSheet(null); setPhotos([]); }
    catch (e) { setError(e instanceof Error ? e.message : "Upload failed"); }
    finally { setBusy(false); }
  }
  async function upload() {
    if (!sheet) return;
    await run(async () => {
      const images = await Promise.all(photos.map(async (f) => {
        const p = await photoToBase64(f);
        return { name: f.name, data: p.data, mime: p.mime };
      }));
      return api.uploadInventory(shopId, { filename: sheet.name, sheet_base64: await fileToBase64(sheet), images });
    });
  }
  return (
    <details className="rounded-xl border border-slate-700 bg-slate-900/40 p-3" open={open ?? true}
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary className="cursor-pointer select-none text-sm font-semibold text-slate-100">
        Inventory · {items.length ? `${items.length} items, ${items.filter((i) => i.image_url).length} with photos` : "not uploaded yet"}
        <span className="ml-2 text-xs font-normal text-slate-400">AI drafts replies from it; you approve every reply</span>
      </summary>
      <div className="mt-3 flex flex-col gap-3">
        <div className="flex flex-wrap items-end gap-2 text-sm">
          <label className="text-xs text-slate-400">Sheet (.xlsx or .csv)
            <input type="file" accept=".xlsx,.csv" onChange={(e) => setSheet(e.target.files?.[0] ?? null)} className="mt-1 block text-xs text-slate-300 file:mr-2 file:rounded file:border-0 file:bg-slate-700 file:px-2 file:py-1 file:text-slate-100" />
          </label>
          <label className="text-xs text-slate-400">Product photos (named in the sheet)
            <input type="file" accept="image/*" multiple onChange={(e) => setPhotos(Array.from(e.target.files ?? []))} className="mt-1 block text-xs text-slate-300 file:mr-2 file:rounded file:border-0 file:bg-slate-700 file:px-2 file:py-1 file:text-slate-100" />
          </label>
          <button type="button" onClick={() => void upload()} disabled={busy || !sheet} className="rounded-lg bg-teal-500 px-3 py-1.5 font-semibold text-slate-950 disabled:opacity-40">{busy ? "Uploading…" : `Upload${photos.length ? ` + ${photos.length} photos` : ""}`}</button>
          <a href={api.templateUrl} className="rounded-lg border border-slate-600 px-3 py-1.5 text-slate-200 hover:border-teal-400">Download template</a>
          <button type="button" onClick={() => void run(() => api.sampleInventory(shopId))} disabled={busy} className="rounded-lg border border-slate-600 px-3 py-1.5 text-slate-200 hover:border-teal-400">Load sample inventory</button>
        </div>
        <ErrorNote message={error} />
        {summary && (
          <p className="text-xs text-slate-300">Imported {summary.items} items ({summary.with_photo} with photos). Columns read: {Object.entries(summary.columns).map(([k, v]) => `${k} ← "${v}"`).join(", ")}.
            {summary.problems.length > 0 && <span className="block text-amber-200">{summary.problems.join(" · ")}</span>}</p>
        )}
        {items.length > 0 && !hideTable && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-xs">
              <thead className="text-left text-slate-500"><tr><th className="py-1">Photo</th><th>Product</th><th>Specs</th><th>Price</th><th>Stock</th></tr></thead>
              <tbody>{items.map((i) => (
                <tr key={i.id} className="border-t border-slate-800 text-slate-300">
                  <td className="py-1">{i.image_url ? <img src={i.image_url} alt="" className="h-9 w-9 rounded object-cover" /> : <span className="text-slate-600">–</span>}</td>
                  <td className="text-slate-100">{i.brand ? `${i.brand} ` : ""}{i.product}</td>
                  <td>{Object.entries(i.specs).map(([k, v]) => `${k.replace("_w", "")}: ${String(v)}`).join(" · ")}</td>
                  <td className="font-mono">{i.currency} {i.price}</td><td className="font-mono">{i.stock}</td>
                </tr>))}</tbody>
            </table>
          </div>
        )}
      </div>
    </details>
  );
}

function DraftCard({ req, shopId, invVersion, onDone, onManual }: { req: LoopRequest; shopId: string; invVersion: number; onDone: () => void; onManual: () => void }) {
  const [d, setD] = useState<Draft | null>(null);
  const [pick, setPick] = useState<number | null>(null);
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ claim: Record<string, unknown>; check: PhotoCheck; mode: string; model: { latency_ms?: number } } | null>(null);
  useEffect(() => {
    let alive = true;
    api.draft(req.id, shopId).then((x) => {
      if (!alive) return;
      setD(x);
      if (x.draft) { setPick(x.draft.inventory_id); setPrice(String(x.draft.price)); setStock(String(x.draft.stock)); setMessage(x.draft.message); }
    }).catch(() => undefined);
    return () => { alive = false; };
  }, [req.id, shopId, invVersion]);

  if (!d) return <p className="mt-2 text-xs text-slate-500">Searching your inventory…</p>;
  if (!d.draft) {
    return (
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
        <span>{d.reason}</span>
        <button type="button" onClick={onManual} className="rounded-lg border border-teal-500/60 px-3 py-1.5 text-sm text-teal-200 hover:bg-teal-500/10">I have this: reply with photo</button>
      </div>
    );
  }
  const chosen = d.candidates.find((c) => c.inventory_id === pick) ?? d.candidates[0];
  async function approve() {
    setBusy(true); setError("");
    try {
      setResult(await api.reply(req.id, { shop_id: shopId, inventory_id: chosen.inventory_id, price: price ? Number(price) : undefined,
        stock: stock ? Number(stock) : undefined, message, approved_by_shopkeeper: true }));
      onDone();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not send"); } finally { setBusy(false); }
  }
  return (
    <div className="mt-3 rounded-xl border border-violet-400/40 bg-violet-500/5 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-violet-200">
        AI draft from your inventory · {d.retrieval === "vertex_ai_search" ? "Vertex AI Search" : "inventory search"}{d.mode === "gemini" ? ` + Gemini ${d.model?.latency_ms ?? "?"} ms` : ""} · waiting for your approval
      </p>
      <div className="mt-2 grid gap-3 md:grid-cols-[96px_1fr]">
        {chosen.image_url ? <img src={chosen.image_url} alt={chosen.product} className="h-24 w-24 rounded-lg object-cover" /> : <div className="flex h-24 w-24 items-center justify-center rounded-lg border border-dashed border-slate-600 text-[11px] text-slate-500">no photo</div>}
        <div className="flex flex-col gap-2 text-sm">
          <p className="text-slate-300">{d.reason}</p>
          {d.candidates.length > 1 && (
            <label className="text-xs text-slate-400">Item
              <select value={chosen.inventory_id} onChange={(e) => {
                const c = d.candidates.find((x) => x.inventory_id === Number(e.target.value));
                setPick(Number(e.target.value)); if (c) setStock(String(c.stock));
              }} className="ml-2 rounded border border-slate-600 bg-slate-950 px-2 py-1 text-sm text-slate-100">
                {d.candidates.map((c) => <option key={c.inventory_id} value={c.inventory_id}>{c.brand ? `${c.brand} ` : ""}{c.product} · {c.price_text} · {c.stock} in stock{c.spec_issues.length ? " ⚠" : ""}</option>)}
              </select>
            </label>
          )}
          <div className="flex gap-2">
            <label className="w-28 text-xs text-slate-400">Price ({req.currency})<input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-1 text-sm text-slate-100" /></label>
            <label className="w-20 text-xs text-slate-400">Stock<input value={stock} onChange={(e) => setStock(e.target.value)} inputMode="numeric" className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-1 text-sm text-slate-100" /></label>
          </div>
          <label className="text-xs text-slate-400">Message to shopper (edit before sending)
            <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={2} maxLength={500} className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-1 text-sm text-slate-100" />
          </label>
          {d.draft.caveats.length > 0 && <p className="text-xs text-amber-200">Check: {d.draft.caveats.join(" · ")}</p>}
          {!result && (
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => void approve()} disabled={busy} className="rounded-lg bg-teal-500 px-3 py-1.5 text-sm font-semibold text-slate-950 disabled:opacity-40">{busy ? "Gemini is checking the photo…" : "Approve & send"}</button>
              <button type="button" onClick={onManual} className="rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:border-teal-400">Send a fresh photo instead</button>
            </div>
          )}
          <ErrorNote message={error} />
        </div>
      </div>
      {busy && !result && <div className="mt-2"><AnalysingSteps /></div>}
      {result && <div className="mt-2"><PhotoAnalysis claim={result.claim} check={result.check} mode={result.mode} latency={result.model?.latency_ms} /></div>}
    </div>
  );
}

function SellButton({ shopId, inventoryId, requestId, onDone }: { shopId: string; inventoryId: number; requestId: number; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <p className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
      <button type="button" disabled={busy} onClick={() => { setBusy(true); api.sell(shopId, { inventory_id: inventoryId, request_id: requestId, qty: 1 })
        .then((x) => { setNote(`Sale recorded: ${x.product}, ${x.stock_left ?? "?"} left in stock`); onDone(); })
        .catch((e) => setNote(e instanceof Error ? e.message : "Could not record")).finally(() => setBusy(false)); }}
        className="rounded-full border border-slate-600 px-3 py-1 text-sm disabled:opacity-40">Shopper bought it: mark 1 sold</button>
      {note && <span>{note}</span>}
    </p>
  );
}

const OUTCOME: Record<string, { label: string; tone: string; help: string }> = {
  answered: { label: "Answered by you", tone: "bg-emerald-400", help: "You replied with proof" },
  missed: { label: "Missed", tone: "bg-amber-400", help: "You had it in stock within budget but did not reply" },
  out_of_stock: { label: "Out of stock", tone: "bg-rose-400", help: "You list it but had none left" },
  over_budget: { label: "Over budget", tone: "bg-violet-400", help: "Your price was above the shopper's budget" },
  not_stocked: { label: "Not stocked", tone: "bg-slate-500", help: "You have nothing that fits: a missed sale" },
};

function MyShopView({ shopId, version, invVersion, onInventoryChanged, onOpenBusiness }: {
  shopId: string; version: number; invVersion: number; onInventoryChanged: () => void; onOpenBusiness: () => void;
}) {
  const [d, setD] = useState<ShopDashboard | null>(null);
  const [error, setError] = useState("");
  const [edits, setEdits] = useState<Record<number, { price?: string; stock?: string }>>({});
  const [brief, setBrief] = useState<{ brief: { headline: string; actions: string[]; watch_out: string }; mode: string; model: { latency_ms?: number } } | null>(null);
  const [busy, setBusy] = useState(false);
  const [lang, setLang] = useState("en");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let alive = true;
    api.dashboard(shopId).then((x) => { if (alive) { setD(x); setError(""); } })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : "Could not load"); });
    return () => { alive = false; };
  }, [shopId, version, invVersion, reload]);
  async function save(id: number) {
    const e = edits[id];
    if (!e) return;
    try {
      await api.editItem(shopId, id, { price: e.price !== undefined && e.price !== "" ? Number(e.price) : undefined,
        stock: e.stock !== undefined && e.stock !== "" ? Number(e.stock) : undefined });
      setEdits((x) => { const n = { ...x }; delete n[id]; return n; });
      onInventoryChanged(); setReload((n) => n + 1);
    } catch (err) { setError(err instanceof Error ? err.message : "Save failed"); }
  }
  async function sell(id: number) {
    try { await api.sell(shopId, { inventory_id: id, qty: 1 }); onInventoryChanged(); setReload((n) => n + 1); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not record sale"); }
  }
  const total = d ? Object.values(d.outcomes).reduce((a, b) => a + b, 0) : 0;
  const card = "rounded-xl border border-slate-700 bg-slate-900/40 p-4";
  return (
    <section aria-label="My shop" className="flex flex-col gap-4">
      <ErrorNote message={error} />
      {d && (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold text-slate-50">{d.shop.name} <span className="text-sm font-normal text-slate-400">· {d.shop.area} · last {d.period_days} days</span></h2>
            <button type="button" onClick={onOpenBusiness} className="text-sm text-teal-300 hover:underline">Forecast, customer groups and bought-together for this shop →</button>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {[
              ["Requests near you", d.kpis.requests_reached, ""],
              ["Answered by you", d.kpis.answered, d.kpis.reply_rate_pct != null ? `${d.kpis.reply_rate_pct}% of those you could serve` : ""],
              ["Median reply time", d.kpis.median_reply_minutes != null ? `${d.kpis.median_reply_minutes} min` : "–", ""],
              ["Sold through NeedProof", d.kpis.units_sold, d.kpis.revenue ?? ""],
              ["Missed sales", d.kpis.missed_sales_requests, "asked for items you don't stock"],
            ].map(([label, value, sub]) => (
              <div key={String(label)} className={card}>
                <p className="text-xs text-slate-400">{label}</p>
                <p className="mt-1 text-2xl font-semibold text-slate-50">{value}</p>
                {sub && <p className="text-[11px] text-slate-500">{sub}</p>}
              </div>
            ))}
          </div>
          <div className={card}>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">What happened to each request</p>
            {total > 0 ? (
              <>
                <div className="mt-2 flex h-3 overflow-hidden rounded-full bg-slate-800">
                  {Object.entries(OUTCOME).map(([k, o]) => d.outcomes[k] ? <div key={k} className={o.tone} style={{ width: `${(100 * d.outcomes[k]) / total}%` }} title={`${o.label}: ${d.outcomes[k]}`} /> : null)}
                </div>
                <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                  {Object.entries(OUTCOME).map(([k, o]) => (
                    <li key={k} title={o.help} className="flex items-center gap-1.5"><span className={`h-2.5 w-2.5 rounded-full ${o.tone}`} />{o.label}: <span className="font-mono text-slate-200">{d.outcomes[k] ?? 0}</span></li>
                  ))}
                </ul>
              </>
            ) : <p className="mt-1 text-sm text-slate-400">No requests yet in this period.</p>}
          </div>

          <InventoryPanel shopId={shopId} hideTable onChanged={() => { onInventoryChanged(); setReload((n) => n + 1); }} />

          {d.inventory.length > 0 && (
            <div className={`${card} overflow-x-auto`}>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">My stock and how it sells</p>
              <table className="mt-2 w-full min-w-[720px] text-sm">
                <thead className="text-left text-xs text-slate-500">
                  <tr><th className="py-1">Item</th><th>Price</th><th>Stock</th><th>Asked</th><th>Sold</th><th>Budgets that fit</th><th /></tr>
                </thead>
                <tbody>
                  {d.inventory.map((i) => {
                    const e = edits[i.id] ?? {};
                    return (
                      <tr key={i.id} className="border-t border-slate-800 align-middle text-slate-300">
                        <td className="py-1.5">
                          <span className="flex items-center gap-2">
                            {i.image_url ? <img src={i.image_url} alt="" className="h-8 w-8 rounded object-cover" /> : <span className="h-8 w-8 rounded bg-slate-800" />}
                            <span className="text-slate-100">{i.brand ? `${i.brand} ` : ""}{i.product}</span>
                            {i.low_stock && <Chip tone="red">{i.stock === 0 ? "Out of stock" : "Low for demand"}</Chip>}
                          </span>
                        </td>
                        <td><input aria-label={`Price of ${i.product}`} value={e.price ?? String(i.price)} onChange={(ev) => setEdits((x) => ({ ...x, [i.id]: { ...x[i.id], price: ev.target.value } }))} className="w-20 rounded border border-slate-600 bg-slate-950 px-2 py-1 font-mono" inputMode="decimal" /></td>
                        <td><input aria-label={`Stock of ${i.product}`} value={e.stock ?? String(i.stock)} onChange={(ev) => setEdits((x) => ({ ...x, [i.id]: { ...x[i.id], stock: ev.target.value } }))} className="w-16 rounded border border-slate-600 bg-slate-950 px-2 py-1 font-mono" inputMode="numeric" /></td>
                        <td className="font-mono">{i.asks}</td>
                        <td className="font-mono">{i.sold}</td>
                        <td className="text-xs">{i.budget_fit_pct != null ? `${i.budget_fit_pct}% (median ${i.median_budget})` : "–"}</td>
                        <td className="whitespace-nowrap text-right">
                          {edits[i.id] ? <button type="button" onClick={() => void save(i.id)} className="rounded-full bg-teal-500 px-3 py-1 text-xs">Save</button>
                            : <button type="button" onClick={() => void sell(i.id)} disabled={i.stock === 0} className="rounded-full border border-slate-600 px-3 py-1 text-xs disabled:opacity-40">Sold 1</button>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="mt-1 text-[11px] text-slate-500">Price and stock changes update what shoppers see immediately. "Asked" counts requests this item could answer.</p>
            </div>
          )}

          <div className="grid gap-3 md:grid-cols-2">
            <div className={card}>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Missed sales: asked for, not stocked</p>
              {d.missed_sales.length ? (
                <ul className="mt-2 space-y-2 text-sm">{d.missed_sales.map((m) => (
                  <li key={m.product} className="border-t border-slate-800 pt-2">
                    <p className="text-slate-100">{m.product} <span className="font-mono text-xs text-rose-300">× {m.asks}</span></p>
                    <p className="text-xs text-slate-400">{m.suggestion}</p>
                  </li>))}</ul>
              ) : <p className="mt-1 text-sm text-slate-400">None: everything shoppers asked for, you stock.</p>}
            </div>
            <div className={card}>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Recent requests near you</p>
              <ul className="mt-2 space-y-1.5 text-sm">{d.requests.slice(0, 8).map((r) => (
                <li key={r.request_id} className="flex flex-wrap items-center gap-2 border-t border-slate-800 pt-1.5">
                  <span className={`h-2.5 w-2.5 rounded-full ${OUTCOME[r.state]?.tone ?? "bg-slate-500"}`} title={OUTCOME[r.state]?.help} />
                  <span className="text-slate-100">#{r.request_id} {r.product}</span>
                  {r.budget && <span className="font-mono text-xs text-slate-400">≤ {r.budget}</span>}
                  {r.returning_shopper && <Chip>Returning</Chip>}
                  <span className="ml-auto text-xs text-slate-500">{OUTCOME[r.state]?.label}{r.matched_item ? ` · your ${r.matched_item}` : ""}</span>
                </li>))}</ul>
              <p className="mt-2 text-xs text-slate-400">Customers who got your replies: <span className="font-mono text-slate-200">{d.customers.known}</span> · returning <span className="font-mono text-slate-200">{d.customers.returning}</span></p>
            </div>
          </div>

          <div className={card}>
            <div className="flex flex-wrap items-end gap-2">
              <p className="mr-auto text-xs font-semibold uppercase tracking-wide text-slate-300">This week's advice for {d.shop.name}</p>
              <select aria-label="Advice language" value={lang} onChange={(e) => setLang(e.target.value)} className="rounded-lg border border-slate-600 bg-slate-950 px-2 py-1 text-sm">
                {BRIEF_LANGS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
              </select>
              <button type="button" disabled={busy} onClick={() => { setBusy(true); api.shopBrief(shopId, lang).then(setBrief).catch((e) => setError(String(e))).finally(() => setBusy(false)); }}
                className="rounded-lg bg-teal-500 px-3 py-1.5 text-sm font-semibold text-slate-950 disabled:opacity-40">{busy ? "Writing…" : "Ask Gemini for my shop"}</button>
            </div>
            {brief && (
              <div className="mt-2">
                <p className="font-semibold text-slate-100">{brief.brief.headline}</p>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-200">{brief.brief.actions.map((a) => <li key={a}>{a}</li>)}</ul>
                <p className="mt-1 text-xs text-amber-200">{brief.brief.watch_out}</p>
                <p className="mt-1 text-[11px] text-slate-500">{brief.mode === "gemini" ? `Gemini · ${brief.model.latency_ms} ms` : brief.mode} · from this shop's live numbers only</p>
              </div>
            )}
          </div>
          {d.sales.length > 0 && (
            <p className="text-xs text-slate-400">Recent sales: {d.sales.map((s) => `${s.qty} × ${s.product}`).join(" · ")}</p>
          )}
          <p className="text-[11px] text-slate-500">{d.note}</p>
        </>
      )}
    </section>
  );
}

function ShopView({ city, shopId, setShopId, onOpenBusiness }: { city: City; shopId: string; setShopId: (id: string) => void; onOpenBusiness: () => void }) {
  const [shops, setShops] = useState<Shop[]>([]);
  const [requests, setRequests] = useState<LoopRequest[]>([]);
  const [open, setOpen] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [invVersion, setInvVersion] = useState(0);
  const [sub, setSub] = useState<"inbox" | "myshop">("inbox");
  const [invCount, setInvCount] = useState<number | null>(null);
  useEffect(() => {
    let alive = true;
    if (shopId) api.inventory(shopId).then((x) => { if (alive) setInvCount(x.length); }).catch(() => undefined);
    return () => { alive = false; };
  }, [shopId, invVersion]);

  useEffect(() => {
    api.shops(city.id).then((s) => {
      setShops(s);
      if (!s.some((x) => x.id === shopId) && s[0]) setShopId(s[0].id);
    }).catch((e) => setError(e instanceof Error ? e.message : "Could not load shops"));
  }, [city.id, shopId, setShopId]);

  const version = useCityVersion(city.id);
  const [seen, setSeen] = useState<Set<number> | null>(null);
  const load = useCallback(() => {
    api.cityRequests(city.id).then((list) => {
      setRequests(list);
      setSeen((prev) => prev ?? new Set(list.map((x) => x.id)));
    }).catch(() => undefined);
  }, [city.id]);
  useEffect(() => { load(); }, [load, version]);

  const shop = shops.find((s) => s.id === shopId);
  return (
    <section aria-label="Shop inbox" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="shop-select" className="text-sm text-slate-400">Continue as</label>
        <select id="shop-select" value={shopId} onChange={(e) => setShopId(e.target.value)} className="max-w-full rounded-lg border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm">
          {shops.some((s) => s.source === "demo") && <optgroup label="Onboarded shops">
            {shops.filter((s) => s.source === "demo").map((s) => <option key={s.id} value={s.id}>{s.name} · {s.area}</option>)}
          </optgroup>}
          {shops.some((s) => s.source !== "demo") && <optgroup label="Nearby shops from the map (reply on their behalf)">
            {shops.filter((s) => s.source !== "demo").map((s) => <option key={s.id} value={s.id}>{s.name}{s.area ? ` · ${s.area}` : ""}</option>)}
          </optgroup>}
        </select>
        {shops.find((s) => s.id === shopId)?.source && shops.find((s) => s.id === shopId)?.source !== "demo" && (
          <span className="text-xs text-amber-200">Real business from map data. You are simulating its reply; it is not contacted.</span>
        )}
      </div>
      <ErrorNote message={error} />
      <div role="tablist" aria-label="Shop views" className="flex w-fit gap-1 rounded-full border border-slate-700 p-1">
        {([["inbox", "Requests inbox"], ["myshop", "My shop: stock, demand, sales"]] as const).map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={sub === id} onClick={() => setSub(id)}
            className={`rounded-full px-3 py-1.5 text-sm ${sub === id ? "bg-teal-500/15 font-semibold text-teal-300" : "text-slate-400 hover:text-slate-200"}`}>{label}</button>
        ))}
      </div>
      {sub === "myshop" && shopId && <MyShopView key={shopId} shopId={shopId} version={version} invVersion={invVersion}
        onInventoryChanged={() => setInvVersion((n) => n + 1)} onOpenBusiness={onOpenBusiness} />}
      {sub === "inbox" && <>
      {invCount === 0 && <p className="rounded-xl border border-violet-400/40 bg-violet-500/5 p-3 text-sm text-slate-300">Upload your stock in <button type="button" onClick={() => setSub("myshop")} className="font-semibold text-teal-300 underline">My shop</button> and NeedProof will draft a reply to every matching request for you to approve.</p>}
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
                  {seen && !seen.has(r.id) && <Chip tone="teal">New</Chip>}
                  {(r.shopper_past_requests ?? 0) > 0 && <Chip tone="slate">Returning shopper · {r.shopper_past_requests} past</Chip>}
                  {r.status === "ANSWERED" ? <Chip tone="green">Answered</Chip> : <Chip tone="amber">Open</Chip>}
                  {mine && <StatusChip status={mine.status} />}
                </div>
              </div>
              <p className="mt-1 text-sm text-slate-400">
                {Object.entries(r.specs).map(([k, v]) => `${k.replace("_w", "").replaceAll("_", " ")}: ${String(v)}`).join(" · ") || "No specific specs"}
                {r.budget ? ` · budget ${r.currency} ${r.budget}` : ""} · language {r.language}
              </p>
              {mine && (
                <div className="mt-2">
                  {mine.inventory_id && <SellButton shopId={shopId} inventoryId={mine.inventory_id} requestId={r.id} onDone={() => setInvVersion((n) => n + 1)} />}
                  {mine.message && <p className="mb-1 text-sm text-slate-300">You sent: “{mine.message}”{mine.evidence_class === "SHOP_CATALOG_PHOTO_READ_BY_AI" ? " · with catalog photo" : ""}</p>}
                  <PhotoAnalysis claim={mine.claim} check={mine.check_result} mode={Object.keys(mine.claim).length ? "gemini" : "none"} />
                </div>
              )}
              {!mine && (open === r.id
                ? <ReplyForm req={r} shopId={shopId} onDone={load} />
                : <DraftCard req={r} shopId={shopId} invVersion={invVersion} onDone={load} onManual={() => setOpen(r.id)} />)}
            </li>
          );
        })}
      </ul>
      </>}
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

function Bands({ a }: { a: Analytics["forecast"] }) {
  const all = [...a.history, ...a.daily.map((d) => d.high)];
  const max = Math.max(1, ...all);
  const n = a.history.length + a.daily.length;
  const w = 560, h = 120;
  const x = (i: number) => (i / (n - 1)) * w;
  const y = (v: number) => h - (v / max) * (h - 8) - 4;
  const hist = a.history.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const off = a.history.length;
  const band = [...a.daily.map((d, i) => `${x(off + i)},${y(d.high)}`), ...[...a.daily].reverse().map((d, i) => `${x(off + a.daily.length - 1 - i)},${y(d.low)}`)].join(" ");
  const fc = [`${x(off - 1)},${y(a.history[off - 1] ?? 0)}`, ...a.daily.map((d, i) => `${x(off + i)},${y(d.units)}`)].join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-32 w-full" role="img" aria-label="Daily units sold, last 28 days, and 7-day forecast with an 80% band">
      <polygon points={band} className="fill-violet-400/20" />
      <polyline points={hist} fill="none" strokeWidth="1.5" className="stroke-teal-300" />
      <polyline points={fc} fill="none" strokeWidth="2" strokeDasharray="4 3" className="stroke-violet-300" />
      <line x1={x(off - 1)} x2={x(off - 1)} y1={0} y2={h} className="stroke-slate-600" strokeDasharray="2 3" />
    </svg>
  );
}

function ShopAnalytics({ city, initialShop }: { city: City; initialShop?: string }) {
  const [shops, setShops] = useState<Shop[]>([]);
  const [shopId, setShopId] = useState(initialShop ?? "");
  const [a, setA] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    api.shops(city.id).then((x) => { if (alive) setShops(x.filter((s) => s.source === "demo")); }).catch(() => undefined);
    return () => { alive = false; };
  }, [city.id]);
  useEffect(() => {
    let alive = true;
    api.analytics(city.id, shopId || undefined).then((x) => { if (alive) { setA(x); setError(""); } })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : "Analytics failed"); });
    return () => { alive = false; };
  }, [city.id, shopId]);
  const status = a?.inventory.status ?? "";
  return (
    <section aria-label="Shop analytics" className="flex flex-col gap-3 rounded-xl border border-slate-700 bg-slate-900/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-slate-100">Shop analytics{a ? `: ${a.shop.name}` : ""}</h2>
        {shops.length > 1 && (
          <label className="text-xs text-slate-400">Shop{" "}
            <select value={shopId || a?.shop.id || ""} onChange={(e) => setShopId(e.target.value)} className="rounded-lg border border-slate-600 bg-slate-950 px-2 py-1 text-sm text-slate-100">
              {shops.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
        )}
      </div>
      <ErrorNote message={error} />
      {a && (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-slate-700 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">Sales forecast · {a.forecast.product}</p>
              <p className="mt-1 text-2xl font-semibold text-slate-50">{a.forecast.next_7_days_units} units <span className="text-sm font-normal text-slate-400">next 7 days</span></p>
              <Bands a={a.forecast} />
              <table className="mt-1 w-full text-xs">
                <thead className="text-left text-slate-500"><tr><th>Model (backtested)</th><th>MAE</th><th>WAPE</th></tr></thead>
                <tbody>{a.forecast.models.map((m) => (
                  <tr key={m.model} className={m.model === a.forecast.selected_model ? "text-teal-200" : "text-slate-400"}>
                    <td>{m.model}{m.model === a.forecast.selected_model ? " ✓ selected" : ""}</td><td className="font-mono">{m.mae}</td><td className="font-mono">{m.wape_pct ?? "–"}%</td>
                  </tr>))}</tbody>
              </table>
              <p className="mt-1 text-[11px] text-slate-500">{a.forecast.method}</p>
            </div>
            <div className="rounded-lg border border-slate-700 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">Inventory risk · {a.inventory.sku}</p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="text-2xl font-semibold text-slate-50">{a.inventory.on_hand} on hand</span>
                <Chip tone={/REVIEW|SHORT|RISK/.test(status) ? "amber" : "green"}>{status.replaceAll("_", " ").toLowerCase() || "ok"}</Chip>
              </div>
              <ul className="mt-2 space-y-1 text-sm text-slate-300">
                <li>Stockout days (last 56): <span className="font-mono">{a.inventory.stockout_days_56}</span></li>
                {a.inventory.coverage_days != null && <li>Coverage at current sales: <span className="font-mono">{a.inventory.coverage_days}</span> days</li>}
                {a.inventory.shortfall_units != null && <li>Shortfall before the next delivery (5-day lead): <span className="font-mono text-rose-200">{a.inventory.shortfall_units}</span> units</li>}
                {a.inventory.review_signals != null && <li>Stock records to review: <span className="font-mono">{a.inventory.review_signals}</span></li>}
              </ul>
              <p className="mt-2 text-[11px] text-slate-500">{a.inventory.method}</p>
            </div>
            <div className="rounded-lg border border-slate-700 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">Customer segments</p>
              <ul className="mt-2 space-y-2">{a.segments.items.map((g) => (
                <li key={g.name + g.count} className="text-sm">
                  <div className="flex justify-between text-slate-200"><span>{g.name}</span><span className="font-mono">{g.share_pct}%</span></div>
                  <div className="h-1.5 rounded bg-slate-800"><div className="h-1.5 rounded bg-teal-400/70" style={{ width: `${g.share_pct}%` }} /></div>
                  <p className="text-xs text-slate-500">{g.count} customers · last visit ~{g.recency_days} d · {g.orders_90d} orders/90 d · {g.spend_90d}</p>
                </li>))}</ul>
              <p className="mt-2 text-[11px] text-slate-500">{a.segments.method}</p>
            </div>
            <div className="rounded-lg border border-slate-700 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">Basket analysis · bought together</p>
              <ul className="mt-2 space-y-1.5 text-sm">{a.baskets.rules.map((r) => (
                <li key={r.if_bought + r.also_bought} className="flex flex-wrap justify-between gap-2 text-slate-300">
                  <span>{r.if_bought} → <span className="text-slate-100">{r.also_bought}</span></span>
                  <span className="font-mono text-xs text-slate-400">{Math.round(r.confidence_pct)}% · lift {r.lift}</span>
                </li>))}</ul>
              <p className="mt-2 text-[11px] text-slate-500">{a.baskets.method} · {a.baskets.basket_count} baskets</p>
            </div>
          </div>
          {a.command_center && a.command_center.queue.length > 0 && (
            <div className="rounded-lg border border-slate-700 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">Review priorities</p>
              <ol className="mt-2 space-y-1.5 text-sm">{a.command_center.queue.map((q) => (
                <li key={q.title} className="flex gap-2"><span className="font-mono text-teal-300">{q.priority}.</span>
                  <span><span className="text-slate-100">{q.title}</span> <span className="text-xs text-slate-400">· {q.reason} ({q.source_module})</span></span></li>
              ))}</ol>
              <p className="mt-2 text-[11px] text-slate-500">{a.command_center.method}</p>
            </div>
          )}
          <p className="text-xs text-amber-200/80">{a.data_note}</p>
        </>
      )}
    </section>
  );
}

function BigQueryPanel({ city }: { city: City }) {
  const [fc, setFc] = useState<BqForecast | null>(null);
  const [brief, setBrief] = useState<{ bullets: string[]; engine: string; seconds: number } | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let alive = true;
    api.bqForecast(city.id).then((x) => { if (alive) { setFc(x); setError(""); } })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : "BigQuery unavailable"); });
    return () => { alive = false; };
  }, [city.id, reload]);
  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label); setError("");
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : `${label} failed`); } finally { setBusy(""); }
  }
  return (
    <section aria-label="BigQuery" className="flex flex-col gap-3 rounded-xl border border-sky-500/30 bg-sky-500/5 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-slate-100">Google Cloud: BigQuery ML forecast and BigQuery AI</h2>
        {fc && <a href={fc.console_url} target="_blank" rel="noreferrer" className="text-xs text-sky-300 underline">Open in BigQuery ↗</a>}
      </div>
      <ErrorNote message={error} />
      {fc && (
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-400"><tr><th className="py-1">Product</th><th>Requests next 7 days</th><th>90% interval</th></tr></thead>
          <tbody>{fc.rows.map((r) => (
            <tr key={r.product_key} className="border-t border-slate-800 text-slate-200">
              <td className="py-1">{r.product_key}</td><td className="font-mono">{r.next_7_days}</td><td className="font-mono text-slate-400">{r.low}–{r.high}</td>
            </tr>))}</tbody>
        </table>
      )}
      {fc && <p className="text-[11px] text-slate-500">{fc.engine} · model {fc.model}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="button" disabled={!!busy} onClick={() => void run("Brief", async () => { setBrief(await api.bqBrief(city.id)); })} className="rounded-lg bg-sky-500 px-3 py-1.5 text-sm font-semibold text-slate-950 disabled:opacity-40">{busy === "Brief" ? "Gemini is writing inside BigQuery…" : "Write brief with BigQuery AI"}</button>
        <button type="button" disabled={!!busy} onClick={() => void run("Sync", async () => { const r = await api.bqSync(); setNote(`Loaded ${r.rows} events to ${r.location} and retrained ARIMA_PLUS in ${r.seconds}s`); setReload((n) => n + 1); })} className="rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:border-sky-400 disabled:opacity-40">{busy === "Sync" ? "Syncing…" : "Sync live requests + retrain"}</button>
      </div>
      {note && <p className="text-xs text-slate-400">{note}</p>}
      {brief && (
        <div className="rounded-lg border border-sky-500/30 p-3">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">{brief.bullets.map((b) => <li key={b}>{b}</li>)}</ul>
          <p className="mt-1 text-xs text-slate-500">{brief.engine} · {brief.seconds}s · AI.GENERATE over the unmet_demand view</p>
        </div>
      )}
    </section>
  );
}

function BusinessView({ city, bigquery, shopId }: { city: City; bigquery?: boolean; shopId?: string }) {
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
      <ShopAnalytics city={city} initialShop={shopId} />
      {bigquery && <BigQueryPanel city={city} />}
      <p className="text-sm text-slate-300">City demand: what shoppers in {city.name} asked for in the last 28 days, and how much of it no shop confirmed.</p>
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

/* ------------------------------ Engine room ------------------------------ */

function ResultView({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value == null) return <span className="text-slate-500">–</span>;
  if (Array.isArray(value)) {
    return <ul className="list-disc space-y-0.5 pl-4">{value.map((v, i) => <li key={i}><ResultView value={v} depth={depth + 1} /></li>)}</ul>;
  }
  if (typeof value === "object") {
    return (
      <dl className={depth ? "pl-2" : ""}>
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k} className="grid grid-cols-[minmax(7rem,auto)_1fr] gap-2">
            <dt className="text-slate-400">{k.replaceAll("_", " ")}</dt><dd className="min-w-0 break-words text-slate-200"><ResultView value={v} depth={depth + 1} /></dd>
          </div>
        ))}
      </dl>
    );
  }
  return <span className="font-mono">{String(value)}</span>;
}

function EngineRoom() {
  const [cat, setCat] = useState<EngineCatalog | null>(null);
  const [runs, setRuns] = useState<Record<string, EngineRun | string>>({});
  const [busy, setBusy] = useState("");
  useEffect(() => {
    let alive = true;
    api.engines().then((x) => { if (alive) setCat(x); }).catch(() => undefined);
    return () => { alive = false; };
  }, []);
  async function run(id: string) {
    setBusy(id);
    try { const r = await api.runEngine(id); setRuns((x) => ({ ...x, [id]: r })); }
    catch (e) { setRuns((x) => ({ ...x, [id]: e instanceof Error ? e.message : "Failed" })); }
    finally { setBusy(""); }
  }
  if (!cat) return <p className="text-sm text-slate-400">Loading engines…</p>;
  return (
    <section aria-label="Engine room" className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold text-slate-50">Engines behind each screen</h2>
        <p className="mt-1 text-sm text-slate-400">The NeedProof engines, what each one decides, and where it runs in the Shopper, Shop and Business screens. <b>Run</b> executes the engine now on the app's live data.</p>
      </div>
      <ul className="grid gap-3 md:grid-cols-2">
        {cat.engines.map((e) => {
          const r = runs[e.id];
          return (
            <li key={e.id} className="rounded-xl border border-slate-700 bg-slate-900/40 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-slate-100"><span className="mr-2 rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[11px] text-slate-300">{e.chunk}</span>{e.name}</p>
                {e.status === "live" ? <Chip tone="green">Live in the app</Chip> : <Chip tone="amber">Available</Chip>}
              </div>
              <p className="mt-1 text-sm text-slate-300">{e.what}</p>
              <p className="mt-1 text-xs text-slate-400">Where: <span className="text-slate-200">{e.used_in}</span></p>
              <button type="button" disabled={busy === e.id} onClick={() => void run(e.id)} className="mt-2 rounded-lg bg-teal-500 px-3 py-1 text-sm font-semibold text-slate-950 disabled:opacity-40">{busy === e.id ? "Running…" : "Run"}</button>
              {typeof r === "string" && <ErrorNote message={r} />}
              {r && typeof r !== "string" && (
                <div className="mt-2 rounded-lg border border-slate-700 bg-slate-950 p-2 text-xs">
                  <p className="text-slate-400">Input: <span className="text-slate-200">{r.input}</span> · {r.ms} ms</p>
                  <div className="mt-1"><ResultView value={r.result} /></div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-4">
        <p className="text-sm font-semibold text-slate-100">Earlier showcase panels, now part of the app</p>
        <table className="mt-2 w-full text-sm">
          <tbody>{cat.retired.map((x) => (
            <tr key={x.name} className="border-t border-slate-800">
              <td className="py-1.5 pr-2 font-mono text-xs text-slate-400">{x.chunk}</td>
              <td className="pr-2 text-slate-200">{x.name}</td>
              <td className="text-slate-400">→ {x.replaced_by}</td>
            </tr>))}</tbody>
        </table>
      </div>
    </section>
  );
}

/* ------------------------------ Trust ------------------------------ */

const STRATEGY: Record<string, string> = {
  EVSI_ONE_STEP: "NeedProof: verify only when worth it", VERIFY_EVERYTHING: "Verify everything", NO_VERIFICATION: "Trust every listing",
  NEEDPROOF_ORTOOLS: "NeedProof optimiser (OR-Tools)", CHEAPEST_FIRST: "Cheapest item first", SINGLE_MERCHANT: "One shop only",
};

function TrustView({ focusEngines = false }: { focusEngines?: boolean }) {
  const enginesRef = useRef<HTMLDivElement>(null);
  const [t, setT] = useState<TrustReport | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    api.trust().then((x) => { if (alive) setT(x); }).catch((e) => { if (alive) setError(e instanceof Error ? e.message : "Could not load"); });
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    if (t && focusEngines) enginesRef.current?.scrollIntoView({ block: "start" });
  }, [t, focusEngines]);
  if (error) return <ErrorNote message={error} />;
  if (!t) return <p className="text-sm text-slate-400">Loading the trust report…</p>;
  const card = "rounded-xl border border-slate-700 bg-slate-900/40 p-4";
  return (
    <section aria-label="Trust report" className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-50">Why you can trust a NeedProof answer</h1>
        <p className="mt-1 text-sm text-slate-400">Gemini understands, reads and explains. Code and the NeedProof decision engine decide. Every number on this page is produced live by the running app or by its test scripts.</p>
      </div>

      <div className={card}>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">How an answer is made</h2>
        <ol className="mt-3 grid gap-2 md:grid-cols-3">
          {t.pipeline.map((p, i) => (
            <li key={p.step} className="rounded-lg border border-slate-700 p-3">
              <p className="text-sm font-semibold text-slate-100">{i + 1}. {p.step} <span className="ml-1 text-xs font-normal text-teal-300">{p.who}</span></p>
              <p className="mt-1 text-xs text-slate-400">{p.what}</p>
            </li>))}
        </ol>
      </div>

      <div className={card}>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Live model tests</h2>
        <p className="mt-1 text-xs text-slate-500">backend/scripts/eval_live.py runs real Gemini calls; code scores each answer against expectations written before the run.</p>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {t.evals.map((e) => (
            <div key={e.backend} className="rounded-lg border border-slate-700 p-3">
              <p className="text-sm font-semibold text-slate-100">{e.backend === "vertex" ? "Vertex AI" : "Gemini API (AI Studio)"} · <span className="font-mono text-xs text-slate-400">{e.model}</span></p>
              <table className="mt-2 w-full text-sm">
                <tbody>{e.tasks.map((x) => (
                  <tr key={x.task} className="border-t border-slate-800">
                    <td className="py-1 text-slate-300">{x.task}</td>
                    <td className={`font-mono ${x.passed === x.total ? "text-emerald-300" : "text-amber-300"}`}>{x.passed}/{x.total}</td>
                    <td className="font-mono text-xs text-slate-500">{x.median_ms} ms</td>
                  </tr>))}</tbody>
              </table>
              <p className="mt-1 text-[11px] text-slate-500">Run {e.run_at.replace("T", " ").replace("+00:00", " UTC")}</p>
            </div>))}
        </div>
        {t.evals[0] && (
          <ul className="mt-3 grid gap-2 md:grid-cols-5">
            {t.evals[0].photos.map((p) => (
              <li key={p.photo} className="rounded-lg border border-slate-700 p-2 text-xs">
                <img src={`/samples/${p.photo}`} alt={p.photo} className="mb-1 h-16 w-full rounded object-cover" />
                <StatusChip status={p.got} />
                <p className="mt-1 text-slate-400">{(p.summary ?? "").slice(0, 110)}</p>
              </li>))}
          </ul>
        )}
      </div>

      <div className={card}>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Safeguards and where they are tested</h2>
        <ul className="mt-2 space-y-1.5 text-sm">
          {t.safeguards.map((g) => (
            <li key={g.rule} className="flex flex-wrap gap-x-2 border-t border-slate-800 pt-1.5">
              <span className="text-emerald-300" aria-hidden="true">✓</span><span className="text-slate-200">{g.rule}</span>
              <span className="ml-auto font-mono text-[11px] text-slate-500">{g.tested}</span>
            </li>))}
        </ul>
      </div>

      {t.benchmarks.evidence && t.benchmarks.basket && (
        <div className={card}>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Decision engine benchmarks <span className="font-normal normal-case text-slate-500">· run live in {t.benchmarks.seconds}s, seeded simulation</span></h2>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500"><tr><th>When to ask for proof</th><th>Net value</th><th>Checks</th><th>Wrong pick</th></tr></thead>
              <tbody>{Object.entries(t.benchmarks.evidence).map(([k, v]) => (
                <tr key={k} className={`border-t border-slate-800 ${k === "EVSI_ONE_STEP" ? "text-teal-200" : "text-slate-300"}`}>
                  <td className="py-1">{STRATEGY[k] ?? k}</td><td className="font-mono">₹{v.average_realized_net_utility_inr}</td>
                  <td className="font-mono">{v.average_checks}</td><td className="font-mono">{v.failed_selection_rate_pct}%</td>
                </tr>))}</tbody>
            </table>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500"><tr><th>Building a basket</th><th>Feasible</th><th>Extra cost</th></tr></thead>
              <tbody>{Object.entries(t.benchmarks.basket).map(([k, v]) => (
                <tr key={k} className={`border-t border-slate-800 ${k === "NEEDPROOF_ORTOOLS" ? "text-teal-200" : "text-slate-300"}`}>
                  <td className="py-1">{STRATEGY[k] ?? k}</td><td className="font-mono">{v.feasibility_rate_pct}%</td>
                  <td className="font-mono">₹{v.mean_extra_cost_vs_needproof_inr}</td>
                </tr>))}</tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">{(t.benchmarks.notes ?? []).join(" ")}</p>
        </div>
      )}

      <div className={card}>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">This running app, right now</h2>
        <div className="mt-2 flex flex-wrap gap-4 text-sm text-slate-300">
          <span><span className="font-mono text-lg text-slate-50">{t.live.requests}</span> shopper requests</span>
          <span><span className="font-mono text-lg text-slate-50">{t.live.answered}</span> answered with a matching photo</span>
          <span><span className="font-mono text-lg text-slate-50">{t.live.drafts_approved}</span> AI drafts approved by shopkeepers</span>
          {Object.entries(t.live.replies_by_status).map(([k, v]) => <span key={k}><StatusChip status={k} /> <span className="font-mono">{v}</span></span>)}
        </div>
      </div>

      <div className="rounded-xl border border-amber-400/30 bg-amber-500/5 p-4 text-sm text-amber-100">
        <p className="font-semibold">Limits, stated plainly</p>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-amber-100/90">{t.limits.map((l) => <li key={l}>{l}</li>)}</ul>
      </div>

      <div ref={enginesRef} id="engines" className="scroll-mt-4 border-t border-slate-800 pt-5">
        <EngineRoom />
      </div>
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
  const [loc, setLoc] = useState<ShopperLocation | null>(null);
  const [locBusy, setLocBusy] = useState(false);
  const [locError, setLocError] = useState("");

  const applyLocation = useCallback((c: City, lat: number, lng: number, label: string, source: string, shopsFound: number, detected: boolean) => {
    setCities((prev) => (prev.some((x) => x.id === c.id) ? prev : [...prev, c]));
    setLoc({ lat, lng, label, cityId: c.id, source, shopsFound, detected });
    setCityId(c.id);
  }, []);

  const nearCity = cityId;
  const locateBy = useCallback(async (body: { lat?: number; lng?: number; query?: string }, detected: boolean) => {
    setLocBusy(true); setLocError("");
    try {
      const r = await api.locate({ ...body, near_city: nearCity });
      applyLocation(r.city, r.lat, r.lng, r.label, r.source, r.shops_found, detected);
    } catch (e) {
      setLocError(e instanceof Error ? e.message : "Location lookup failed");
    } finally { setLocBusy(false); }
  }, [applyLocation, nearCity]);

  const detect = useCallback(() => {
    if (!("geolocation" in navigator)) { setLocError("This browser cannot share location; type a place instead"); return; }
    setLocBusy(true); setLocError("");
    navigator.geolocation.getCurrentPosition(
      (pos) => { void locateBy({ lat: pos.coords.latitude, lng: pos.coords.longitude }, true); },
      () => { setLocBusy(false); setLocError("Location not shared; showing the city centre. Use Change to type a place."); },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
  }, [locateBy]);

  useEffect(() => {
    api.status().then((s) => { setCities((prev) => [...s.cities, ...prev.filter((p) => !s.cities.some((c) => c.id === p.id))]); setProviders(s.providers); mapsConfig.key = s.maps_key ?? ""; })
      .catch(() => setError("Backend not reachable. Start FastAPI on port 8000."));
  }, []);
  // Detect the shopper's location once, unless the link already names a city.
  const detectedOnce = useRef(false);
  useEffect(() => {
    if (detectedOnce.current || new URLSearchParams(window.location.search).has("city")) return;
    detectedOnce.current = true;
    detect();
  }, [detect]);
  useEffect(() => { writeParams(role, cityId, role === "shop" ? shopId : undefined); }, [role, cityId, shopId]);

  const city = cities.find((c) => c.id === cityId) ?? cities[0];
  const tabs: { id: Role; label: string; hint: string }[] = [
    { id: "shopper", label: "Shopper", hint: "Ask in any language" },
    { id: "shop", label: "Shop", hint: "Reply with photo proof" },
    { id: "business", label: "Business", hint: "Unmet demand" },
    { id: "trust", label: "Trust report", hint: "How it decides" },
  ];
  const otherWindow = `${window.location.pathname}?role=${role === "shop" ? "shopper" : "shop"}&city=${cityId}`;

  return (
    <div className="np-google min-h-dvh bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-4">
          <div className="min-w-0">
            <p className="text-lg font-bold tracking-tight">NeedProof <span className="font-normal text-slate-400">· Know it's in stock before you go</span></p>
            <p className="text-xs text-slate-500">Gemini agent for shoppers · photo proof from shops · demand insights for business</p>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <label htmlFor="city" className="sr-only">City</label>
            <select id="city" value={cityId} onChange={(e) => setCityId(e.target.value)} className="rounded-lg border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm">
              {cities.some((c) => !c.demo) && <optgroup label="Your location">
                {cities.filter((c) => !c.demo).map((c) => <option key={c.id} value={c.id}>{c.name} ({c.symbol.trim()})</option>)}
              </optgroup>}
              <optgroup label="Cities with onboarded shops">
                {cities.filter((c) => c.demo).map((c) => <option key={c.id} value={c.id}>{c.name} ({c.symbol})</option>)}
              </optgroup>
            </select>
            {providers && (
              <span title={`${providers.gemini.model} · analytics: ${providers.analytics.label}`}>
                <Chip tone={providers.live_model ? "green" : "amber"}>{providers.gemini.label}{providers.live_model ? ` · ${providers.gemini.model}` : ""}</Chip>
              </span>
            )}
            <button type="button" onClick={() => api.reset().then(() => setResetKey((k) => k + 1))} className="text-xs text-slate-400 underline hover:text-slate-200">Reset data</button>
          </div>
        </div>
        <div className="mx-auto max-w-5xl px-4 pb-2">
          <LocationBar loc={loc && loc.cityId === cityId ? loc : null} busy={locBusy} error={locError}
            demo={!!city?.demo} onDetect={detect} onSearch={(q) => void locateBy({ query: q }, false)} />
        </div>
        <nav aria-label="Role" className="mx-auto flex max-w-5xl flex-wrap gap-1 overflow-x-auto px-4">
          {tabs.map((t) => (
            <button key={t.id} type="button" onClick={() => setRole(t.id)} aria-current={(role === "engines" ? "trust" : role) === t.id ? "page" : undefined}
              className={`whitespace-nowrap border-b-2 px-3 pb-2 pt-1 text-sm ${(role === "engines" ? "trust" : role) === t.id ? "border-teal-400 font-semibold text-teal-300" : "border-transparent text-slate-400 hover:text-slate-200"}`}>
              {t.label} <span className="hidden text-xs text-slate-500 xl:inline">· {t.hint}</span>
            </button>
          ))}
          <a href={otherWindow} target="_blank" rel="noreferrer" className="ml-auto self-center pb-2 text-xs text-teal-300 hover:underline">Open {role === "shop" ? "shopper" : "shop"} view in a new window ↗</a>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6" key={`${resetKey}-${cityId}`}>
        <ErrorNote message={error} />
        {city && role === "shopper" && <ShopperView city={city} loc={loc && loc.cityId === city.id ? loc : null}
          onMoved={(c, lat, lng, label) => applyLocation(c, lat ?? c.lat ?? 0, lng ?? c.lng ?? 0, label ?? c.name, loc?.source ?? "openstreetmap", loc?.shopsFound ?? 0, false)} />}
        {city && role === "shop" && <ShopView city={city} shopId={shopId} setShopId={setShopId} onOpenBusiness={() => setRole("business")} />}
        {role === "trust" && <TrustView />}
        {role === "engines" && <TrustView focusEngines />}
        {city && role === "business" && <BusinessView city={city} shopId={shopId} bigquery={providers?.analytics?.backend === "bigquery"} />}
        <p className="mt-10 text-xs text-slate-500">Onboarded shops in Singapore, São Paulo and Mumbai are sample businesses with seeded history. Real shops come from public map data and are never contacted by NeedProof. The app never buys anything; listings are shop claims until a photo is checked.</p>
      </main>
    </div>
  );
}
