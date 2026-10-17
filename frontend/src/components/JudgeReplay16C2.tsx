import { useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, ShieldCheck, ShieldAlert, ClipboardList, Clock3, Layers3 } from "lucide-react";
import replayData from "../generated/needproof16cReplay.json";

type ScenarioKey = "reported_offer" | "stockout" | "document_conflict" | "no_merchants";
type Trace = { stage: string; state: string; status: string };
type Scenario = {
  title: string;
  fixture_origin: string;
  purchase_allowed: false;
  real_merchant_contact: false;
  stock_independently_verified: false;
  cloud_model_used: false;
  database_used: false;
  source_records_persisted: false;
  workflow: {
    workflow_state: string;
    reason: string;
    recommended_next_action: string;
    change_detection: { changed: boolean; changes: Array<{ event: string }> };
    workflow_trace: Trace[];
    purchase_allowed: false;
  };
  limitations: string[];
  separate_illustrative_business_context?: {
    metrics: Array<{ key: string; label: string; value: string | number; unit: string }>;
  } | null;
};
type Replay = { mode: string; source: string; synthetic: boolean; scenarios: Record<ScenarioKey, Scenario> };
const replay = replayData as unknown as Replay;
const scenarios: Array<{ id: ScenarioKey; label: string; description: string }> = [
  { id: "reported_offer", label: "Merchant claim", description: "One fictional store reports availability" },
  { id: "stockout", label: "Stock-out", description: "The same offer becomes unavailable" },
  { id: "document_conflict", label: "Conflicting sources", description: "Product excerpts disagree" },
  { id: "no_merchants", label: "No candidates", description: "Discovery is needed before deciding" },
];
const stageLabels = ["Merchant evidence", "Product research", "Verification value", "Basket constraints", "Policy boundary"] as const;
const explanation = [
  "A store's reported inventory is not an independent stock check or a reservation.",
  "Read supplied product excerpts, distinguishing supported claims from contradictions.",
  "The verification planner uses hypothetical assumptions, not calibrated reliability.",
  "Basket results use an independent fictional shopping scenario, not approved stock.",
  "The system never authorizes a purchase from unverified merchant evidence.",
];
function readable(value: unknown): string {
  return String(value ?? "not provided").replaceAll("_", " ").toLowerCase();
}
function verifiedFixture(data: Replay): boolean {
  if (data.mode !== "OFFLINE_ENGINE_REPLAY_16C" || data.source !== "ACTUAL_LOCAL_16A_EVALUATOR" || !data.synthetic) return false;
  return scenarios.every(({ id }) => {
    const s = data.scenarios[id];
    return !!s && s.fixture_origin === "SERVER_OWNED_SYNTHETIC_NOT_REAL_MERCHANTS" &&
      s.purchase_allowed === false && s.real_merchant_contact === false &&
      s.stock_independently_verified === false && s.cloud_model_used === false &&
      s.database_used === false && s.source_records_persisted === false &&
      s.workflow?.purchase_allowed === false && s.workflow.workflow_trace?.length === 5;
  });
}

/** Zero network requests: the replay is checked-in engine-derived JSON, not a live API result. */
export default function JudgeReplay16C2() {
  const [selected, setSelected] = useState<ScenarioKey>("reported_offer");
  const [step, setStep] = useState(0);
  const safe = useMemo(() => verifiedFixture(replay), []);
  if (!safe) return <section id="judge-replay-16c2" role="alert" className="rounded-xl border border-rose-500 p-5 text-rose-200">Demo fixture integrity check failed. Offline replay is unavailable.</section>;
  const item = replay.scenarios[selected];
  const trace = item.workflow.workflow_trace[step];
  const current = scenarios.find((s) => s.id === selected)!;
  function changeScenario(value: ScenarioKey) { setSelected(value); setStep(0); }

  return (
    <section id="judge-replay-16c2" aria-labelledby="judge-replay-title" className="scroll-mt-20 overflow-hidden rounded-2xl border border-emerald-700/40 bg-[#101c28] shadow-xl shadow-black/20">
      <div className="border-b border-[#2c4854] bg-gradient-to-r from-emerald-950/50 to-sky-950/30 p-4 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-300"><ShieldCheck size={15} /> Start here · 2-minute guided tour</span>
          <span className="rounded-full border border-amber-500/35 bg-amber-500/10 px-3 py-1 text-[11px] font-semibold text-amber-200">OFFLINE REPLAY · FICTIONAL DATA</span>
        </div>
        <h2 id="judge-replay-title" className="mt-3 text-xl font-semibold tracking-tight text-white sm:text-2xl">A recommendation is easy. <span className="text-emerald-300">Proof is harder.</span></h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">See how NeedProof changes its next action when evidence changes. These results were generated from our Python decision engine and embedded locally. This panel makes no Gemini, Firebase, Cloud Run, Places or Firestore requests.</p>
      </div>
      <div className="grid gap-4 p-4 sm:p-6 lg:grid-cols-[minmax(215px,0.75fr)_minmax(0,2fr)]">
        <div aria-label="Choose a fictional case" className="grid grid-cols-2 gap-2 lg:flex lg:flex-col">
          {scenarios.map((s, idx) => <button key={s.id} type="button" aria-pressed={selected === s.id} onClick={() => changeScenario(s.id)}
            className={`min-w-0 rounded-xl border p-3 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-300 ${selected === s.id ? "border-emerald-400/70 bg-emerald-900/20" : "border-slate-700 bg-[#0a1321] hover:border-slate-500"}`}>
            <span className="block text-[10px] font-semibold tracking-wide text-emerald-300">{String(idx+1).padStart(2, "0")} / 04</span>
            <span className="mt-1 block text-xs font-semibold text-white sm:text-sm">{s.label}</span>
            <span className="mt-1 hidden text-xs text-slate-400 sm:block">{s.description}</span>
          </button>)}
        </div>
        <div className="min-w-0 space-y-4">
          <div className="rounded-xl border border-[#304453] bg-[#0b1524] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-[11px] font-bold uppercase tracking-wide text-emerald-300">Decision outcome</span><span className="rounded-md border border-amber-500/30 px-2 py-1 text-[10px] text-amber-200">NO PURCHASE APPROVAL</span></div>
            <h3 className="mt-2 break-words text-lg font-semibold text-white">{current.label}: {readable(item.workflow.workflow_state)}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-300">{item.workflow.reason}</p>
            {selected === "reported_offer" && <button type="button" onClick={() => changeScenario("stockout")} className="mt-3 inline-flex items-center gap-2 rounded-lg bg-emerald-400 px-3 py-2 text-xs font-semibold text-emerald-950 hover:bg-emerald-300">Now remove reported stock <ArrowRight size={14}/></button>}
            {item.workflow.change_detection.changed && <p className="mt-3 text-xs text-amber-200">Evidence changed: {item.workflow.change_detection.changes.map((c) => readable(c.event)).join(", ")}</p>}
          </div>
          <div className="rounded-xl border border-[#304453] p-4">
            <div className="flex items-center justify-between gap-2"><p className="inline-flex items-center gap-2 text-xs font-semibold text-slate-200"><Layers3 size={15} className="text-emerald-300"/> Five-stage decision trace</p><span className="text-xs text-slate-400">{step + 1} / 5</span></div>
            <div className="mt-3 grid grid-cols-5 gap-1.5" aria-label="Select algorithm stage">{stageLabels.map((label, idx) => <button key={label} type="button" aria-current={step===idx?"step":undefined} aria-label={`Stage ${idx+1}: ${label}`} onClick={() => setStep(idx)} className={`min-h-12 rounded-lg border px-1 py-2 text-center text-[11px] font-semibold ${step===idx?"border-emerald-400 bg-emerald-900/30 text-emerald-200":"border-slate-700 bg-[#080e1a] text-slate-300 hover:border-slate-400"}`}>{idx+1}</button>)}</div>
            <div className="mt-3 min-h-36 rounded-lg border border-slate-700/70 bg-[#081322] p-4" aria-live="polite">
              <p className="text-xs font-semibold text-emerald-300">{stageLabels[step]} · {readable(trace.status)}</p>
              <h4 className="mt-2 break-words text-sm font-semibold text-white">{readable(trace.state)}</h4>
              <p className="mt-2 text-xs leading-5 text-slate-300">{explanation[step]}</p>
            </div>
            <div className="mt-3 flex justify-between gap-3"><button type="button" disabled={step===0} onClick={() => setStep((s)=>Math.max(0,s-1))} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-600 px-3 py-2 text-xs text-slate-200 disabled:opacity-30"><ArrowLeft size={14}/> Previous</button><button type="button" disabled={step===4} onClick={() => setStep((s)=>Math.min(4,s+1))} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-emerald-700 px-3 py-2 text-xs text-emerald-200 disabled:opacity-30">Next stage <ArrowRight size={14}/></button></div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-[#304453] bg-[#0b1524] p-4"><p className="flex items-center gap-2 text-xs font-semibold text-slate-300"><ClipboardList size={14} className="text-emerald-300"/> Next review action</p><p className="mt-2 break-words text-sm font-semibold text-emerald-200">{readable(item.workflow.recommended_next_action)}</p></div>
            <div className="rounded-lg border border-[#304453] bg-[#0b1524] p-4"><p className="flex items-center gap-2 text-xs font-semibold text-slate-300"><Clock3 size={14} className="text-emerald-300"/> Source status</p><p className="mt-2 text-sm leading-5 text-slate-200">Fictional merchant report · not verified or reserved</p></div>
          </div>
          <details className="rounded-lg border border-[#304453] p-3 text-xs text-slate-300"><summary className="cursor-pointer font-semibold text-emerald-300">Provenance, separate BI and limitations</summary><p className="mt-3">Recorded from the 16A Python evaluator, then bundled as static demo data. No model runs in this panel. BI figures are separately fictional and unrelated to this customer case.</p><div className="mt-3 grid gap-2 sm:grid-cols-3">{item.separate_illustrative_business_context?.metrics.slice(0,3).map((m) => <div key={m.key} className="rounded-lg bg-[#081322] p-2"><p className="text-[11px] text-slate-400">{m.label}</p><p className="mt-1 text-base text-white">{m.value} <span className="text-xs text-slate-400">{m.unit}</span></p></div>)}</div><ul className="mt-3 list-disc space-y-1 pl-4">{item.limitations.map((v,i)=><li key={i}>{v}</li>)}</ul></details>
          <p className="flex items-start gap-2 text-xs leading-5 text-amber-200"><ShieldAlert size={15} className="mt-0.5 shrink-0"/> No merchant contacted, stock independently verified, personal record saved, or purchase approved. Optional live intelligence tools below remain separately feature-gated.</p>
        </div>
      </div>
    </section>
  );
}
