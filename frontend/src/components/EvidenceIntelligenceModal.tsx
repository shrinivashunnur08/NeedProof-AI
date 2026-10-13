import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowRight,
  BarChart3,
  BrainCircuit,
  Clock3,
  RefreshCw,
  ShieldAlert,
  SlidersHorizontal,
  X,
} from "lucide-react";

interface Scenario {
  budget_inr: number;
  deadline_minutes: number;
  a_verification_cost_inr: number;
  a_prior: number;
  a_response_probability: number;
}

interface DecisionAction {
  action_id: string;
  merchant: string;
  sku: string;
  prior_feasible: number;
  response_probability: number;
  p_pass: number;
  p_fail: number;
  p_no_response: number;
  gross_evsi_inr: string;
  verification_cost_inr: string;
  delay_cost_inr: string;
  net_evsi_inr: string;
  skip_reason: string | null;
}

interface DecisionPlan {
  mode: "SYNTHETIC_RESEARCH_SCENARIO";
  baseline: {
    merchant: string;
    sku: string;
    price_inr: string;
  } | null;
  baseline_utility_inr: string;
  recommended_action_id: string | null;
  stopping_reason: string | null;
  actions: DecisionAction[];
  assumptions: string[];
}

interface Props {
  onClose: () => void;
}

const DEFAULT_SCENARIO: Scenario = {
  budget_inr: 1000,
  deadline_minutes: 15,
  a_verification_cost_inr: 8,
  a_prior: 0.65,
  a_response_probability: 0.8,
};

function currency(value: string | number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function readableReason(value: string) {
  return value.replaceAll("_", " ").toLowerCase();
}

function SliderField({
  label,
  value,
  min,
  max,
  step,
  display,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  display: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block">
      <div className="mb-2 flex items-center justify-between gap-3 text-xs">
        <span className="text-slate-400">{label}</span>
        <span className="font-semibold tabular-nums text-slate-100">
          {display}
        </span>
      </div>

      <input
        aria-label={label}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full cursor-pointer accent-sky-400"
      />

      <div className="mt-1 flex justify-between text-[10px] text-slate-600">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#2B3950] bg-[#080D17] p-3">
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export default function EvidenceIntelligenceModal({ onClose }: Props) {
  const [inputs, setInputs] = useState<Scenario>({
    ...DEFAULT_SCENARIO,
  });

  const [applied, setApplied] = useState<Scenario>({
    ...DEFAULT_SCENARIO,
  });

  const [plan, setPlan] = useState<DecisionPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function updateInput<K extends keyof Scenario>(key: K, value: Scenario[K]) {
    setInputs((previous) => ({
      ...previous,
      [key]: value,
    }));
  }

  function applyScenario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setApplied({ ...inputs });
  }

  function applyPreset(next: Scenario) {
    setInputs({ ...next });
    setApplied({ ...next });
  }

  const changesPending = JSON.stringify(inputs) !== JSON.stringify(applied);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    window.addEventListener("keydown", closeOnEscape);

    return () => {
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [onClose]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadDecisionPlan() {
      setLoading(true);
      setError("");
      setPlan(null);

      const params = new URLSearchParams({
        budget_inr: String(applied.budget_inr),
        deadline_minutes: String(applied.deadline_minutes),
        a_verification_cost_inr: String(applied.a_verification_cost_inr),
        a_prior: String(applied.a_prior),
        a_response_probability: String(applied.a_response_probability),
      });

      try {
        const response = await fetch(
          `/api/decisions/demo-plan?${params.toString()}`,
          {
            signal: controller.signal,
            cache: "no-store",
          },
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            typeof data.detail === "string"
              ? data.detail
              : `Decision API returned ${response.status}`,
          );
        }

        if (!controller.signal.aborted) {
          setPlan(data as DecisionPlan);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to calculate evidence value",
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadDecisionPlan();

    return () => controller.abort();
  }, [applied]);

  const recommended = plan?.actions.find(
    (action) => action.action_id === plan.recommended_action_id,
  );

  const highestPositiveNet = plan
    ? Math.max(0, ...plan.actions.map((action) => Number(action.net_evsi_inr)))
    : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-3 text-slate-100 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-modal-title"
        className="flex h-[91dvh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-[#304059] bg-[#111827] shadow-2xl"
      >
        {/* Header */}
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-[#273449] px-5 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="rounded-xl bg-sky-500/10 p-2.5 text-sky-400">
              <BrainCircuit size={22} />
            </div>

            <div className="min-w-0">
              <h2
                id="evidence-modal-title"
                className="truncate text-base font-semibold sm:text-lg"
              >
                Active Evidence Intelligence
              </h2>
              <p className="text-xs text-slate-400">
                Bayesian uncertainty · Expected Value of Information
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-3">
            <span className="hidden rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-[11px] text-amber-300 sm:block">
              Simulation Mode
            </span>

            <button
              type="button"
              onClick={onClose}
              aria-label="Close Evidence Intelligence"
              className="rounded-lg border border-slate-700 p-2 hover:bg-slate-800"
            >
              <X size={18} />
            </button>
          </div>
        </header>

        <div className="grid min-h-0 flex-1 overflow-y-auto lg:grid-cols-[310px_minmax(0,1fr)] lg:overflow-hidden">
          {/* Left: scenario inputs */}
          <form
            onSubmit={applyScenario}
            className="flex flex-col gap-5 border-b border-[#273449] bg-[#0D1522] p-5 lg:overflow-y-auto lg:border-b-0 lg:border-r"
          >
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={17} className="text-sky-400" />
              <h3 className="text-sm font-semibold">Scenario Parameters</h3>
            </div>

            <SliderField
              label="Customer budget"
              value={inputs.budget_inr}
              min={100}
              max={3000}
              step={50}
              display={`₹${inputs.budget_inr.toLocaleString("en-IN")}`}
              onChange={(value) => updateInput("budget_inr", value)}
            />

            <SliderField
              label="Time available for verification"
              value={inputs.deadline_minutes}
              min={0}
              max={45}
              step={1}
              display={`${inputs.deadline_minutes} minutes`}
              onChange={(value) => updateInput("deadline_minutes", value)}
            />

            <SliderField
              label="Harbor verification cost"
              value={inputs.a_verification_cost_inr}
              min={0}
              max={400}
              step={1}
              display={`₹${inputs.a_verification_cost_inr}`}
              onChange={(value) =>
                updateInput("a_verification_cost_inr", value)
              }
            />

            <SliderField
              label="Harbor prior feasibility"
              value={inputs.a_prior}
              min={0}
              max={1}
              step={0.05}
              display={`${Math.round(inputs.a_prior * 100)}%`}
              onChange={(value) => updateInput("a_prior", value)}
            />

            <SliderField
              label="Harbor response probability"
              value={inputs.a_response_probability}
              min={0}
              max={1}
              step={0.05}
              display={`${Math.round(inputs.a_response_probability * 100)}%`}
              onChange={(value) => updateInput("a_response_probability", value)}
            />

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-sky-500 px-4 py-3 text-sm font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-50"
            >
              {loading ? (
                <RefreshCw size={17} className="animate-spin" />
              ) : (
                <BarChart3 size={17} />
              )}
              {loading ? "Calculating..." : "Run Evidence Analysis"}
            </button>

            {changesPending && (
              <p className="text-xs text-amber-300">
                Parameters changed. Run analysis to apply them.
              </p>
            )}

            <div className="border-t border-slate-800 pt-4">
              <p className="mb-3 text-xs font-semibold text-slate-300">
                Quick experiments
              </p>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => applyPreset({ ...DEFAULT_SCENARIO })}
                  className="rounded-lg border border-slate-700 px-3 py-2 text-xs hover:bg-slate-800"
                >
                  Normal
                </button>

                <button
                  type="button"
                  onClick={() =>
                    applyPreset({
                      ...DEFAULT_SCENARIO,
                      a_verification_cost_inr: 300,
                    })
                  }
                  className="rounded-lg border border-slate-700 px-3 py-2 text-xs hover:bg-slate-800"
                >
                  Expensive check
                </button>

                <button
                  type="button"
                  onClick={() =>
                    applyPreset({
                      ...DEFAULT_SCENARIO,
                      deadline_minutes: 1,
                    })
                  }
                  className="rounded-lg border border-slate-700 px-3 py-2 text-xs hover:bg-slate-800"
                >
                  Urgent deadline
                </button>
              </div>
            </div>
          </form>

          {/* Right: results */}
          <div className="min-h-0 overflow-y-auto p-4 lg:p-6">
            {loading && (
              <div className="flex min-h-52 items-center justify-center gap-3 text-sm text-slate-400">
                <RefreshCw size={20} className="animate-spin text-sky-400" />
                Evaluating evidence actions...
              </div>
            )}

            {error && (
              <div
                role="alert"
                className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300"
              >
                {error}
              </div>
            )}

            {!loading && plan && (
              <div className="space-y-5">
                {/* Decision headline */}
                <div className="rounded-xl border border-sky-500/25 bg-sky-500/5 p-4">
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-sky-400">
                    Recommended next action
                  </p>

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="text-xl font-semibold">
                        {recommended
                          ? `Investigate ${recommended.merchant}`
                          : "Stop investigating"}
                      </h3>

                      <p className="mt-2 text-xs leading-5 text-slate-400">
                        {recommended
                          ? "Highest positive expected net value under the simulated assumptions."
                          : "No remaining action has positive feasible net verification value."}
                      </p>
                    </div>

                    <div className="text-left sm:text-right">
                      <p className="text-[11px] text-slate-500">
                        Expected net value
                      </p>
                      <p className="mt-1 text-2xl font-semibold tabular-nums text-emerald-400">
                        {recommended
                          ? currency(recommended.net_evsi_inr)
                          : currency(0)}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Current baseline */}
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <Clock3 size={16} className="text-sky-400" />
                    <h3 className="text-sm font-semibold">
                      Current decision baseline
                    </h3>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-3">
                    <Metric
                      label="Eligible baseline offer"
                      value={plan.baseline?.merchant ?? "None established"}
                    />

                    <Metric
                      label="Baseline offer price"
                      value={
                        plan.baseline
                          ? currency(plan.baseline.price_inr)
                          : "Not available"
                      }
                    />

                    <Metric
                      label="Synthetic baseline utility"
                      value={currency(plan.baseline_utility_inr)}
                    />
                  </div>
                </div>

                {/* Action comparisons */}
                <div>
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold">
                      Verification action comparison
                    </h3>

                    <span className="text-[11px] text-slate-500">
                      {plan.actions.length} candidate actions
                    </span>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    {plan.actions.map((action) => {
                      const selected =
                        action.action_id === plan.recommended_action_id;

                      const netValue = Number(action.net_evsi_inr);

                      const barWidth =
                        highestPositiveNet > 0
                          ? (Math.max(0, netValue) / highestPositiveNet) * 100
                          : 0;

                      return (
                        <article
                          key={action.action_id}
                          className={`rounded-xl border p-4 ${
                            selected
                              ? "border-sky-500/40 bg-sky-500/5"
                              : "border-[#304058] bg-[#0A101B]"
                          }`}
                        >
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div>
                              <h4 className="text-sm font-semibold">
                                {action.merchant}
                              </h4>
                              <p className="mt-1 text-[11px] text-slate-500">
                                {action.action_id} · {action.sku}
                              </p>
                            </div>

                            <span
                              className={`rounded-full px-2 py-1 text-[10px] font-semibold ${
                                selected
                                  ? "bg-sky-500/15 text-sky-300"
                                  : "bg-slate-800 text-slate-400"
                              }`}
                            >
                              {selected
                                ? "RECOMMENDED"
                                : action.skip_reason
                                  ? "INFEASIBLE"
                                  : netValue > 0
                                    ? "ALTERNATIVE"
                                    : "NOT WORTH CHECKING"}
                            </span>
                          </div>

                          <div className="mt-4 grid grid-cols-3 gap-2">
                            <div>
                              <p className="text-[10px] text-slate-500">Pass</p>
                              <p className="mt-1 text-sm font-semibold">
                                {(action.p_pass * 100).toFixed(1)}%
                              </p>
                            </div>

                            <div>
                              <p className="text-[10px] text-slate-500">Fail</p>
                              <p className="mt-1 text-sm font-semibold">
                                {(action.p_fail * 100).toFixed(1)}%
                              </p>
                            </div>

                            <div>
                              <p className="text-[10px] text-slate-500">
                                No response
                              </p>
                              <p className="mt-1 text-sm font-semibold">
                                {(action.p_no_response * 100).toFixed(1)}%
                              </p>
                            </div>
                          </div>

                          <div className="mt-4 space-y-2 border-t border-slate-800 pt-3 text-xs">
                            <div className="flex justify-between gap-2">
                              <span className="text-slate-500">
                                Gross expected benefit
                              </span>
                              <span>{currency(action.gross_evsi_inr)}</span>
                            </div>

                            <div className="flex justify-between gap-2">
                              <span className="text-slate-500">
                                Verification cost
                              </span>
                              <span>
                                {currency(action.verification_cost_inr)}
                              </span>
                            </div>

                            <div className="flex justify-between gap-2">
                              <span className="text-slate-500">Delay cost</span>
                              <span>{currency(action.delay_cost_inr)}</span>
                            </div>

                            <div className="flex justify-between gap-2 border-t border-slate-800 pt-2 font-semibold">
                              <span>Net EVSI</span>
                              <span
                                className={
                                  netValue > 0
                                    ? "text-emerald-400"
                                    : "text-slate-400"
                                }
                              >
                                {currency(action.net_evsi_inr)}
                              </span>
                            </div>
                          </div>

                          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-800">
                            <div
                              className="h-full rounded-full bg-sky-400"
                              style={{
                                width: `${barWidth}%`,
                              }}
                            />
                          </div>

                          {action.skip_reason && (
                            <p className="mt-3 text-xs text-amber-300">
                              Skipped: {readableReason(action.skip_reason)}
                            </p>
                          )}
                        </article>
                      );
                    })}
                  </div>

                  <p className="mt-2 text-[11px] text-slate-500">
                    Bars show relative positive net value, not probabilities or
                    guaranteed savings.
                  </p>
                </div>

                {/* Model transparency */}
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
                  <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-amber-300">
                    <ShieldAlert size={15} />
                    Evidence limitations
                  </div>

                  <p className="text-xs leading-5 text-slate-400">
                    These probabilities and financial values are synthetic
                    research assumptions. They are not derived from Google
                    Places, real store prices, or the merchant submissions
                    collected in Chunk 4B. This analysis recommends an
                    investigation; it does not execute one.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        <footer className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-[#273449] px-5 py-3 text-[11px] text-slate-500">
          <span>NeedProof AI · Synthetic Decision Research</span>

          <span className="flex items-center gap-1.5">
            <ArrowRight size={12} />
            Evaluate evidence before committing
          </span>
        </footer>
      </section>
    </div>
  );
}
