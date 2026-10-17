import { useState } from "react";
import benchmark from "../generated/benchmark17fReview.json";

/** Audited 17F fixture summary, never a live retail metric. */
export default function JuryEvidence17G({ freshEnabled }: { freshEnabled: boolean }) {
  const [open, setOpen] = useState(false);
  const max = benchmark.dataset_size;
  return (
    <section id="judge-evidence-17g" aria-labelledby="judge-evidence-17g-heading"
      className="rounded-2xl border border-sky-500/25 bg-[#0c1626] p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Evidence-led retail decisions · Judge journey</p>
          <h2 id="judge-evidence-17g-heading" className="mt-1 text-lg font-semibold text-white">One request. A reasoned next step. An honest comparison.</h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-300">
            Watch a synthetic shopping decision change when stock or product evidence changes, then inspect the claim sources and recommended verification.
          </p>
        </div>
        <span className="rounded-full border border-amber-500/30 px-3 py-1 text-xs text-amber-200">Offline / fictional evidence</span>
      </div>
      <ol className="mt-4 grid gap-2 md:grid-cols-3">
        <li className="rounded-lg border border-slate-700/80 p-3 text-sm text-slate-200"><strong className="text-cyan-300">01 · Shopping need</strong><p className="mt-1 text-xs text-slate-400">A user requests a compatible charger, budget and location.</p></li>
        <li className="rounded-lg border border-slate-700/80 p-3 text-sm text-slate-200"><strong className="text-cyan-300">02 · What changed?</strong><p className="mt-1 text-xs text-slate-400">A fictional merchant stock-out or conflicting document triggers recomputation.</p></li>
        <li className="rounded-lg border border-slate-700/80 p-3 text-sm text-slate-200"><strong className="text-cyan-300">03 · Next best proof</strong><p className="mt-1 text-xs text-slate-400">A source-aware verification queue explains what needs checking.</p></li>
      </ol>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <a href="#judge-replay-16c" className="rounded-lg border border-slate-600 px-3 py-2 text-xs font-medium text-slate-100 hover:border-cyan-400">View prerecorded engine replay</a>
        {freshEnabled ? <a href="#fresh-decision-17c" className="rounded-lg bg-cyan-600 px-3 py-2 text-xs font-semibold text-white hover:bg-cyan-500">Try fresh local Python decision</a> : <span className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-amber-200">Fresh Python controls are disabled here</span>}
        <button type="button" aria-controls="benchmark-17g-details" aria-expanded={open} onClick={() => setOpen(!open)}
          className="rounded-lg border border-slate-600 px-3 py-2 text-xs font-medium text-slate-100 hover:border-cyan-400">
          {open ? "Hide" : "Inspect"} measured synthetic comparison
        </button>
      </div>
      <p className="mt-3 text-xs text-amber-200" role="note">
        Benchmark finding: NeedProof 40/{max} ties a strong structured-rules baseline 40/{max}; no validated customer savings or live-model superiority.
      </p>
      {open && <div id="benchmark-17g-details" className="mt-4 space-y-3 rounded-xl border border-slate-700 p-4" role="region" aria-label="Synthetic benchmark evidence">
        <p className="text-xs text-amber-200">Fixed, builder-authored fictional cases and policy labels; neither live Gemini nor real merchants were tested.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {benchmark.policies.map((policy) => <div key={policy.id} className="rounded-lg border border-slate-700 bg-[#090f1c] p-3">
            <div className="flex justify-between gap-2 text-xs text-slate-100"><strong>{policy.label}</strong><span className="tabular-nums">{policy.correct}/{max} correct</span></div>
            <div role="img" aria-label={`${policy.label}: ${policy.correct} out of ${max} correct decisions`} className="mt-2 h-2 overflow-hidden rounded-full bg-slate-700">
              <div className="h-full rounded-full bg-cyan-400" style={{width: `${100*policy.correct/max}%`}} />
            </div>
            <p className="mt-2 text-xs text-slate-400">Next checks: {policy.first_checks_correct}/{max} · Unsafe provisional picks: {policy.unsafe_provisional}</p>
          </div>)}
        </div>
        <p className="text-xs text-slate-400">This is a comparison of decision states under identical structured inputs, not a comparison against a live LLM or actual retail outcomes.</p>
        <details className="text-xs text-slate-400"><summary className="cursor-pointer text-cyan-300">Reproduction metadata</summary>
          <p className="mt-1 break-all">Dataset SHA-256: {benchmark.dataset_sha256}</p>
          <p className="mt-1 break-all">Semantic results SHA-256: {benchmark.semantic_results_sha256}</p>
          <p className="mt-1">Source commit: {benchmark.source_commit}</p></details>
      </div>}
    </section>
  );
}
