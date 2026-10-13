import { useEffect, useState, type FormEvent } from "react";

import { BarChart3, Download, FlaskConical, RefreshCw, X } from "lucide-react";

type BasketPolicy = "NEEDPROOF_ORTOOLS" | "CHEAPEST_FIRST" | "SINGLE_MERCHANT";

type EvidencePolicy = "EVSI_ONE_STEP" | "VERIFY_EVERYTHING" | "NO_VERIFICATION";

interface BasketMetrics {
  feasible_count: number;
  feasibility_rate_pct: number;
  average_cost_inr_on_feasible: number | null;
  paired_cases: number;
  mean_extra_cost_vs_needproof_inr: number | null;
  missed_feasible_cases: number;
}

interface EvidenceMetrics {
  average_realized_net_utility_inr: number;
  average_verification_cost_inr: number;
  average_checks: number;
  failed_selection_rate_pct: number;
}

interface BasketOutcome {
  feasible: boolean;
  total_minor: number | null;
  reason: string | null;
  solver_status?: string;
}

interface BasketTrial {
  trial_id: number;
  budget_inr: number;
  deadline_minutes: number;
  max_merchants: number;
  results: Record<BasketPolicy, BasketOutcome>;
}

interface EvidenceOutcome {
  selected: string;
  checks: number;
  verification_cost_inr: number;
  realized_net_utility_inr: number;
  failed_selection: boolean;
}

interface EvidenceTrial {
  trial_id: number;
  prior_a: number;
  prior_b: number;
  actual_a_success: boolean;
  actual_b_success: boolean;
  results: Record<EvidencePolicy, EvidenceOutcome>;
}

interface BenchmarkResult {
  mode: "SYNTHETIC_BENCHMARK";
  seed: number;
  basket_scenarios: number;
  evidence_trials: number;
  basket: {
    summary: Record<BasketPolicy, BasketMetrics>;
    trials: BasketTrial[];
  };
  evidence: {
    summary: Record<EvidencePolicy, EvidenceMetrics>;
    trials: EvidenceTrial[];
  };
  assumptions: Record<string, string>;
}

interface BenchmarkConfig {
  seed: number;
  basket_scenarios: number;
  evidence_trials: number;
}

const DEFAULT_CONFIG: BenchmarkConfig = {
  seed: 42,
  basket_scenarios: 30,
  evidence_trials: 500,
};

const BASKET_POLICIES: {
  id: BasketPolicy;
  label: string;
}[] = [
  { id: "NEEDPROOF_ORTOOLS", label: "NeedProof OR-Tools" },
  { id: "CHEAPEST_FIRST", label: "Cheapest First" },
  { id: "SINGLE_MERCHANT", label: "Single Merchant" },
];

const EVIDENCE_POLICIES: {
  id: EvidencePolicy;
  label: string;
}[] = [
  { id: "EVSI_ONE_STEP", label: "One-Step EVSI" },
  { id: "VERIFY_EVERYTHING", label: "Verify Everything" },
  { id: "NO_VERIFICATION", label: "No Verification" },
];

function money(value: number | null) {
  return value === null
    ? "N/A"
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2,
      }).format(value);
}

function csvCell(value: unknown): string {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

function downloadCsv(filename: string, rows: unknown[][]) {
  const csv = rows.map((row) => row.map(csvCell).join(",")).join("\r\n");

  const blob = new Blob([csv], {
    type: "text/csv;charset=utf-8",
  });

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");

  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  URL.revokeObjectURL(url);
}

export default function BenchmarkDashboardModal({
  onClose,
}: {
  onClose: () => void;
}) {
  const [inputs, setInputs] = useState<BenchmarkConfig>(DEFAULT_CONFIG);

  const [applied, setApplied] = useState<BenchmarkConfig>(DEFAULT_CONFIG);

  const [runId, setRunId] = useState(0);
  const [result, setResult] = useState<BenchmarkResult | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      setLoading(true);
      setError("");
      setResult(null);

      const params = new URLSearchParams({
        seed: String(applied.seed),
        basket_scenarios: String(applied.basket_scenarios),
        evidence_trials: String(applied.evidence_trials),
      });

      try {
        const response = await fetch(
          `/api/benchmarks/run?${params.toString()}`,
          {
            signal: controller.signal,
            cache: "no-store",
          },
        );

        const raw = await response.text();

        if (!response.ok) {
          throw new Error(
            `Benchmark API failed (HTTP ${response.status}): ` +
              raw.slice(0, 180),
          );
        }

        if (!raw.trim()) {
          throw new Error("The benchmark API returned an empty response.");
        }

        const data = JSON.parse(raw) as BenchmarkResult;

        if (data.mode !== "SYNTHETIC_BENCHMARK") {
          throw new Error("Unexpected benchmark response format.");
        }

        if (!controller.signal.aborted) {
          setResult(data);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error ? err.message : "Could not run benchmark.",
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => controller.abort();
  }, [applied, runId]);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    window.addEventListener("keydown", closeOnEscape);

    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  function runAgain(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setApplied({ ...inputs });
    setRunId((previous) => previous + 1);
  }

  function exportBasket() {
    if (!result) return;

    const rows: unknown[][] = [
      [
        "seed",
        "trial_id",
        "policy",
        "budget_inr",
        "deadline_minutes",
        "max_merchants",
        "feasible",
        "total_cost_inr",
        "reason",
      ],
    ];

    for (const trial of result.basket.trials) {
      for (const policy of BASKET_POLICIES) {
        const outcome = trial.results[policy.id];

        rows.push([
          result.seed,
          trial.trial_id,
          policy.id,
          trial.budget_inr,
          trial.deadline_minutes,
          trial.max_merchants,
          outcome.feasible,
          outcome.total_minor === null ? "" : outcome.total_minor / 100,
          outcome.reason ?? "",
        ]);
      }
    }

    downloadCsv(`needproof-basket-seed-${result.seed}.csv`, rows);
  }

  function exportEvidence() {
    if (!result) return;

    const rows: unknown[][] = [
      [
        "seed",
        "trial_id",
        "policy",
        "prior_a",
        "prior_b",
        "actual_a_success",
        "actual_b_success",
        "selected",
        "checks",
        "verification_cost_inr",
        "realized_net_utility_inr",
        "failed_selection",
      ],
    ];

    for (const trial of result.evidence.trials) {
      for (const policy of EVIDENCE_POLICIES) {
        const outcome = trial.results[policy.id];

        rows.push([
          result.seed,
          trial.trial_id,
          policy.id,
          trial.prior_a,
          trial.prior_b,
          trial.actual_a_success,
          trial.actual_b_success,
          outcome.selected,
          outcome.checks,
          outcome.verification_cost_inr,
          outcome.realized_net_utility_inr,
          outcome.failed_selection,
        ]);
      }
    }

    downloadCsv(`needproof-evidence-seed-${result.seed}.csv`, rows);
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/85 p-3 text-slate-100 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="benchmark-title"
        className="flex max-h-[92dvh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-700 bg-[#111827] shadow-2xl"
      >
        <header className="flex shrink-0 items-center justify-between border-b border-slate-800 px-5 py-4">
          <div className="flex items-center gap-3">
            <BarChart3 size={23} className="text-sky-400" />

            <div>
              <h2 id="benchmark-title" className="text-lg font-semibold">
                Benchmark Intelligence
              </h2>

              <p className="text-xs text-slate-400">
                Reproducible synthetic evaluation · OR-Tools + EVSI
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close Benchmark Intelligence"
            className="rounded-lg border border-slate-700 p-2"
          >
            <X size={18} />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <form
            onSubmit={runAgain}
            className="grid items-end gap-3 rounded-xl border border-slate-700 bg-[#0A101B] p-4 sm:grid-cols-4"
          >
            <label className="text-xs text-slate-400">
              Random seed
              <input
                type="number"
                min={0}
                max={999999}
                required
                value={inputs.seed}
                onChange={(event) =>
                  setInputs({
                    ...inputs,
                    seed: Number(event.target.value),
                  })
                }
                className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
              />
            </label>

            <label className="text-xs text-slate-400">
              Basket scenarios
              <input
                type="number"
                min={1}
                max={80}
                required
                value={inputs.basket_scenarios}
                onChange={(event) =>
                  setInputs({
                    ...inputs,
                    basket_scenarios: Number(event.target.value),
                  })
                }
                className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
              />
            </label>

            <label className="text-xs text-slate-400">
              Evidence trials
              <input
                type="number"
                min={10}
                max={2000}
                required
                value={inputs.evidence_trials}
                onChange={(event) =>
                  setInputs({
                    ...inputs,
                    evidence_trials: Number(event.target.value),
                  })
                }
                className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
              />
            </label>

            <button
              type="submit"
              disabled={loading}
              className="flex items-center justify-center gap-2 rounded-lg bg-sky-500 px-3 py-3 text-sm font-semibold text-slate-950 disabled:opacity-50"
            >
              {loading ? (
                <RefreshCw size={16} className="animate-spin" />
              ) : (
                <FlaskConical size={16} />
              )}
              {loading ? "Evaluating..." : "Run Benchmark"}
            </button>
          </form>

          {error && (
            <div
              role="alert"
              className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300"
            >
              {error}
            </div>
          )}

          {result && (
            <div className="mt-5 space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">Benchmark execution</p>

                  <p className="mt-1 text-xs text-slate-400">
                    Seed {result.seed} · {result.basket_scenarios} basket
                    scenarios · {result.evidence_trials} evidence trials
                    {loading ? " · Updating..." : ""}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={loading}
                    onClick={exportBasket}
                    className="flex items-center gap-2 rounded-lg border border-sky-500/30 px-3 py-2 text-xs text-sky-300 disabled:opacity-40"
                  >
                    <Download size={14} />
                    Basket CSV
                  </button>

                  <button
                    type="button"
                    disabled={loading}
                    onClick={exportEvidence}
                    className="flex items-center gap-2 rounded-lg border border-sky-500/30 px-3 py-2 text-xs text-sky-300 disabled:opacity-40"
                  >
                    <Download size={14} />
                    Evidence CSV
                  </button>
                </div>
              </div>

              {/* Basket benchmark */}
              <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                <h3 className="text-sm font-semibold">
                  1. Multi-Merchant Basket Optimization
                </h3>

                <p className="mt-1 text-xs leading-5 text-slate-400">
                  Same eligible offers and hard constraints. Costs are compared
                  only when both strategies produce feasible baskets.
                </p>

                <div className="mt-4 space-y-4">
                  {BASKET_POLICIES.map((policy) => {
                    const metrics = result.basket.summary[policy.id];

                    return (
                      <div key={policy.id}>
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs">
                          <span className="font-medium">{policy.label}</span>

                          <span className="text-slate-400">
                            {metrics.feasibility_rate_pct}% feasible
                          </span>
                        </div>

                        <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                          <div
                            className="h-full rounded-full bg-sky-400"
                            style={{
                              width: `${metrics.feasibility_rate_pct}%`,
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="mt-5 overflow-x-auto">
                  <table className="w-full min-w-[650px] text-left text-xs">
                    <thead className="text-slate-500">
                      <tr className="border-b border-slate-800">
                        <th className="pb-3 pr-3">Strategy</th>
                        <th className="pb-3 pr-3">Feasible</th>
                        <th className="pb-3 pr-3">Avg cost*</th>
                        <th className="pb-3 pr-3">Paired extra cost**</th>
                        <th className="pb-3">Missed cases</th>
                      </tr>
                    </thead>

                    <tbody>
                      {BASKET_POLICIES.map((policy) => {
                        const data = result.basket.summary[policy.id];

                        return (
                          <tr
                            key={policy.id}
                            className="border-b border-slate-800/70"
                          >
                            <td className="py-3 pr-3 font-medium">
                              {policy.label}
                            </td>

                            <td className="py-3 pr-3">
                              {data.feasible_count}/{result.basket_scenarios}
                            </td>

                            <td className="py-3 pr-3">
                              {money(data.average_cost_inr_on_feasible)}
                            </td>

                            <td className="py-3 pr-3">
                              {money(data.mean_extra_cost_vs_needproof_inr)}
                            </td>

                            <td className="py-3">
                              {data.missed_feasible_cases}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <p className="mt-3 text-[11px] leading-5 text-slate-500">
                  *Average cost includes only feasible cases within each
                  strategy; these sets may differ. **Paired extra cost is
                  calculated on the same scenarios where both NeedProof and the
                  baseline are feasible. Positive means the baseline costs more.
                  The number of paired cases is included in the CSV/JSON.
                </p>
              </div>

              {/* Evidence benchmark */}
              <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                <h3 className="text-sm font-semibold">
                  2. Active Evidence Verification
                </h3>

                <p className="mt-1 text-xs leading-5 text-slate-400">
                  A separate one-step EVSI policy simulation against two
                  uncertain offers and a safe fallback. Perfect verification is
                  a hypothetical testing assumption.
                </p>

                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  {EVIDENCE_POLICIES.map((policy) => {
                    const metrics = result.evidence.summary[policy.id];

                    return (
                      <div
                        key={policy.id}
                        className="rounded-xl border border-slate-800 p-4"
                      >
                        <p className="text-xs text-slate-400">{policy.label}</p>

                        <p className="mt-3 text-xl font-semibold text-sky-300">
                          {money(metrics.average_realized_net_utility_inr)}
                        </p>

                        <p className="mt-1 text-[11px] text-slate-500">
                          Avg realized net utility / trial
                        </p>

                        <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-800">
                          <div
                            className="h-full rounded-full bg-emerald-400"
                            style={{
                              width: `${Math.min(
                                100,
                                (metrics.average_checks / 2) * 100,
                              )}%`,
                            }}
                          />
                        </div>

                        <p className="mt-2 text-xs text-slate-400">
                          {metrics.average_checks} checks / trial
                        </p>

                        <p className="mt-2 text-xs text-amber-300">
                          Failed selection: {metrics.failed_selection_rate_pct}%
                        </p>

                        <p className="mt-1 text-xs text-slate-500">
                          Avg verification spend:{" "}
                          {money(metrics.average_verification_cost_inr)}
                        </p>
                      </div>
                    );
                  })}
                </div>

                <p className="mt-3 text-[11px] leading-5 text-slate-500">
                  Utility measures simulated decision value after verification
                  costs, not sales revenue. Failed selection rate counts
                  failures across all trials. Verification checks are assumed
                  perfect, with no real communication or merchant API costs.
                </p>
              </div>

              <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
                <h3 className="text-sm font-semibold text-amber-300">
                  Evaluation limitations
                </h3>

                <div className="mt-3 space-y-2">
                  {Object.entries(result.assumptions).map(
                    ([name, description]) => (
                      <p
                        key={name}
                        className="text-xs leading-5 text-slate-400"
                      >
                        <span className="font-medium text-slate-200">
                          {name.replaceAll("_", " ")}:
                        </span>{" "}
                        {description}
                      </p>
                    ),
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        <footer className="shrink-0 border-t border-slate-800 px-5 py-3 text-[11px] text-slate-500">
          NeedProof AI · Synthetic benchmarks · Seeded experiments · No real
          customer or merchant data
        </footer>
      </section>
    </div>
  );
}
