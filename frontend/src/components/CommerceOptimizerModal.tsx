import { useEffect, useState, type FormEvent } from "react";
import {
  CheckCircle2,
  PackageCheck,
  RefreshCw,
  ShieldAlert,
  ShoppingCart,
  X,
} from "lucide-react";

interface Scenario {
  budget_inr: number;
  deadline_minutes: number;
  max_merchants: number;
}

interface SelectedOffer {
  sku: string;
  item_id: string;
  item_name: string;
  merchant: string;
  quantity: number;
  unit_price_minor: number;
  line_total_minor: number;
  delivery_eta_minutes: number;
  evidence_source: string;
}

interface OptimizationResult {
  mode: "SYNTHETIC_OPTIMIZATION";
  status: string;
  reason: string | null;
  blocked_items: string[];
  selected_offers: SelectedOffer[];
  used_merchants: {
    name: string;
    fulfillment_fee_minor: number;
  }[];
  totals: {
    subtotal_minor: number;
    fulfillment_fees_minor: number;
    total_minor: number;
    budget_minor: number;
    remaining_minor: number;
  } | null;
  excluded_offers: {
    sku: string;
    item_id: string;
    merchant: string;
    reasons: string[];
  }[];
  eligible_offer_count: number;
  notice: string;
}

interface Props {
  onClose: () => void;
}

const NORMAL: Scenario = {
  budget_inr: 1800,
  deadline_minutes: 60,
  max_merchants: 2,
};

function rupees(paise: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(paise / 100);
}

function readable(text: string) {
  return text.replaceAll("_", " ");
}

export default function CommerceOptimizerModal({ onClose }: Props) {
  const [inputs, setInputs] = useState<Scenario>(NORMAL);
  const [applied, setApplied] = useState<Scenario>(NORMAL);

  const [result, setResult] = useState<OptimizationResult | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    function onEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    window.addEventListener("keydown", onEscape);

    return () => window.removeEventListener("keydown", onEscape);
  }, [onClose]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadOptimization() {
      setLoading(true);
      setError("");
      setResult(null);

      const params = new URLSearchParams({
        budget_inr: String(applied.budget_inr),
        deadline_minutes: String(applied.deadline_minutes),
        max_merchants: String(applied.max_merchants),
      });

      try {
        const response = await fetch(`/api/optimization/demo-plan?${params}`, {
          signal: controller.signal,
          cache: "no-store",
        });

        const raw = await response.text();

        if (!response.ok) {
          throw new Error(
            `Optimizer API failed (HTTP ${response.status}): ` +
              raw.slice(0, 160),
          );
        }

        if (!raw.trim()) {
          throw new Error("Optimizer API returned an empty response.");
        }

        const data = JSON.parse(raw) as OptimizationResult;

        if (
          data.mode !== "SYNTHETIC_OPTIMIZATION" ||
          !Array.isArray(data.selected_offers)
        ) {
          throw new Error("Unexpected optimization response.");
        }

        if (!controller.signal.aborted) {
          setResult(data);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Optimization failed");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void loadOptimization();

    return () => controller.abort();
  }, [applied]);

  function runScenario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setApplied({ ...inputs });
  }

  function preset(next: Scenario) {
    setInputs({ ...next });
    setApplied({ ...next });
  }

  const pending = JSON.stringify(inputs) !== JSON.stringify(applied);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-3 text-slate-100 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="optimizer-title"
        className="flex h-[91dvh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-[#304059] bg-[#111827] shadow-2xl"
      >
        <header className="flex shrink-0 items-center justify-between border-b border-slate-800 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-sky-500/10 p-2.5 text-sky-400">
              <ShoppingCart size={23} />
            </div>

            <div>
              <h2 id="optimizer-title" className="text-lg font-semibold">
                Multi-Merchant Commerce Optimizer
              </h2>
              <p className="text-xs text-slate-400">
                OR-Tools · Constraint-based basket planning
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-300 sm:block">
              Simulation
            </span>

            <button
              type="button"
              onClick={onClose}
              aria-label="Close optimizer"
              className="rounded-lg border border-slate-700 p-2 hover:bg-slate-800"
            >
              <X size={18} />
            </button>
          </div>
        </header>

        <div className="grid min-h-0 flex-1 overflow-y-auto lg:grid-cols-[300px_minmax(0,1fr)] lg:overflow-hidden">
          {/* Scenario controls */}
          <form
            onSubmit={runScenario}
            className="flex flex-col gap-5 border-b border-slate-800 bg-[#0D1522] p-5 lg:overflow-y-auto lg:border-b-0 lg:border-r"
          >
            <div>
              <h3 className="text-sm font-semibold">
                Optimization constraints
              </h3>

              <p className="mt-1 text-xs leading-5 text-slate-500">
                Three required items. Prices and merchant availability are
                simulated.
              </p>
            </div>

            <label className="block">
              <div className="mb-2 flex justify-between text-xs">
                <span className="text-slate-400">Total budget</span>
                <span className="font-semibold">
                  ₹{inputs.budget_inr.toLocaleString("en-IN")}
                </span>
              </div>

              <input
                aria-label="Total budget"
                type="range"
                min="1500"
                max="2500"
                step="1"
                value={inputs.budget_inr}
                onChange={(event) =>
                  setInputs({
                    ...inputs,
                    budget_inr: Number(event.target.value),
                  })
                }
                className="w-full accent-sky-400"
              />
            </label>

            <label className="block">
              <div className="mb-2 flex justify-between text-xs">
                <span className="text-slate-400">Delivery deadline</span>

                <span className="font-semibold">
                  {inputs.deadline_minutes} min
                </span>
              </div>

              <input
                aria-label="Delivery deadline"
                type="range"
                min="0"
                max="90"
                step="1"
                value={inputs.deadline_minutes}
                onChange={(event) =>
                  setInputs({
                    ...inputs,
                    deadline_minutes: Number(event.target.value),
                  })
                }
                className="w-full accent-sky-400"
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-xs text-slate-400">
                Maximum merchants
              </span>

              <select
                value={inputs.max_merchants}
                onChange={(event) =>
                  setInputs({
                    ...inputs,
                    max_merchants: Number(event.target.value),
                  })
                }
                className="w-full rounded-lg border border-slate-700 bg-[#080D17] px-3 py-2.5 text-sm"
              >
                <option value={1}>1 merchant</option>
                <option value={2}>2 merchants</option>
                <option value={3}>3 merchants</option>
              </select>
            </label>

            <button
              type="submit"
              disabled={loading}
              className="flex items-center justify-center gap-2 rounded-xl bg-sky-500 p-3 text-sm font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-40"
            >
              {loading ? (
                <RefreshCw size={17} className="animate-spin" />
              ) : (
                <ShoppingCart size={17} />
              )}

              {loading ? "Optimizing..." : "Optimize Basket"}
            </button>

            {pending && (
              <p className="text-xs text-amber-300">
                Click Optimize Basket to apply your changes.
              </p>
            )}

            <div className="border-t border-slate-800 pt-4">
              <p className="mb-3 text-xs font-semibold">Quick experiments</p>

              <div className="grid grid-cols-2 gap-2">
                {[
                  {
                    label: "Normal",
                    value: NORMAL,
                  },
                  {
                    label: "One merchant",
                    value: {
                      ...NORMAL,
                      max_merchants: 1,
                    },
                  },
                  {
                    label: "Low budget",
                    value: {
                      ...NORMAL,
                      budget_inr: 1559,
                    },
                  },
                  {
                    label: "Urgent",
                    value: {
                      ...NORMAL,
                      deadline_minutes: 10,
                    },
                  },
                ].map((experiment) => (
                  <button
                    key={experiment.label}
                    type="button"
                    onClick={() => preset(experiment.value)}
                    className="rounded-lg border border-slate-700 px-2 py-2 text-xs text-slate-300 hover:bg-slate-800"
                  >
                    {experiment.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-auto rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
              <p className="flex items-center gap-2 text-xs font-semibold text-amber-300">
                <ShieldAlert size={15} />
                Strict evidence policy
              </p>

              <p className="mt-2 text-xs leading-5 text-slate-400">
                Unverified merchant reports cannot enter this purchase-eligible
                simulation.
              </p>
            </div>
          </form>

          {/* Optimization output */}
          <div className="min-h-0 space-y-5 overflow-y-auto p-5">
            {loading && (
              <div className="flex items-center justify-center gap-3 py-20 text-sm text-slate-400">
                <RefreshCw size={19} className="animate-spin text-sky-400" />
                Solving the basket constraints...
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

            {!loading && result && (
              <>
                <div
                  className={`rounded-xl border p-4 ${
                    result.status === "OPTIMAL"
                      ? "border-emerald-500/25 bg-emerald-500/5"
                      : "border-amber-500/25 bg-amber-500/5"
                  }`}
                >
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    Optimization result
                  </p>

                  <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="text-xl font-semibold">
                        {result.status === "OPTIMAL"
                          ? "Optimal basket found"
                          : result.status === "FEASIBLE"
                            ? "Feasible basket found"
                            : result.status === "INFEASIBLE"
                              ? "No feasible basket"
                              : "Solver could not complete"}
                      </h3>

                      <p className="mt-2 text-xs text-slate-400">
                        {result.reason
                          ? readable(result.reason)
                          : "All configured hard constraints satisfied."}
                      </p>
                    </div>

                    <div className="text-right">
                      <p className="text-xs text-slate-400">
                        Total basket cost
                      </p>

                      <p className="mt-1 text-2xl font-semibold text-emerald-400">
                        {result.totals
                          ? rupees(result.totals.total_minor)
                          : "—"}
                      </p>
                    </div>
                  </div>
                </div>

                {result.totals && (
                  <>
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                      {[
                        {
                          label: "Item subtotal",
                          value: rupees(result.totals.subtotal_minor),
                        },
                        {
                          label: "Merchant fees",
                          value: rupees(result.totals.fulfillment_fees_minor),
                        },
                        {
                          label: "Budget remaining",
                          value: rupees(result.totals.remaining_minor),
                        },
                        {
                          label: "Merchants used",
                          value: String(result.used_merchants.length),
                        },
                      ].map((metric) => (
                        <div
                          key={metric.label}
                          className="rounded-xl border border-slate-700 bg-[#080D17] p-3"
                        >
                          <p className="text-[11px] text-slate-500">
                            {metric.label}
                          </p>
                          <p className="mt-2 text-sm font-semibold">
                            {metric.value}
                          </p>
                        </div>
                      ))}
                    </div>

                    <div>
                      <h3 className="mb-3 text-sm font-semibold">
                        Selected offers
                      </h3>

                      <div className="grid gap-3 md:grid-cols-3">
                        {result.selected_offers.map((offer) => (
                          <article
                            key={offer.sku}
                            className="rounded-xl border border-sky-500/25 bg-[#080D17] p-4"
                          >
                            <div className="flex items-start gap-2">
                              <PackageCheck
                                size={17}
                                className="shrink-0 text-sky-400"
                              />

                              <div>
                                <p className="text-sm font-semibold">
                                  {offer.item_name}
                                </p>
                                <p className="mt-1 text-xs text-sky-400">
                                  {offer.merchant}
                                </p>
                              </div>
                            </div>

                            <p className="mt-4 text-lg font-semibold">
                              {rupees(offer.line_total_minor)}
                            </p>

                            <p className="mt-2 text-xs text-slate-400">
                              Qty {offer.quantity} · ETA{" "}
                              {offer.delivery_eta_minutes} min
                            </p>

                            <p className="mt-3 flex items-center gap-1 text-[11px] text-emerald-400">
                              <CheckCircle2 size={13} />
                              Verified within simulation
                            </p>
                          </article>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-xl border border-slate-700 bg-[#080D17] p-4">
                      <h3 className="text-sm font-semibold">
                        Fulfillment breakdown
                      </h3>

                      <div className="mt-3 space-y-2">
                        {result.used_merchants.map((merchant) => (
                          <div
                            key={merchant.name}
                            className="flex justify-between gap-3 text-xs"
                          >
                            <span className="text-slate-400">
                              {merchant.name}
                            </span>

                            <span>
                              {rupees(merchant.fulfillment_fee_minor)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}

                <div className="rounded-xl border border-slate-700 bg-[#080D17] p-4">
                  <h3 className="text-sm font-semibold">Rejected offers</h3>

                  <p className="mt-1 text-xs text-slate-500">
                    Ineligible offers are excluded before optimization.
                  </p>

                  <div className="mt-3 space-y-3">
                    {result.excluded_offers.length === 0 && (
                      <p className="text-xs text-slate-500">
                        No offers rejected by preflight checks.
                      </p>
                    )}

                    {result.excluded_offers.map((offer) => (
                      <div
                        key={offer.sku}
                        className="rounded-lg border border-amber-500/15 bg-amber-500/5 p-3"
                      >
                        <p className="text-xs font-semibold">
                          {offer.sku} · {offer.merchant}
                        </p>

                        <p className="mt-1 text-[11px] leading-5 text-amber-300">
                          {offer.reasons.map(readable).join(", ")}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                <p className="text-xs leading-5 text-slate-500">
                  {result.notice}
                </p>
              </>
            )}
          </div>
        </div>

        <footer className="shrink-0 border-t border-slate-800 px-5 py-3 text-[11px] text-slate-500">
          NeedProof AI · Synthetic constrained optimization · No payment or
          reservation executed
        </footer>
      </section>
    </div>
  );
}
