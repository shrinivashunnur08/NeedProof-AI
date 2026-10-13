import { useEffect, useMemo, useState } from "react";
import {
  BrainCircuit,
  History,
  Play,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";

import type {
  JourneyDiscovery,
  JourneyEvidence,
} from "../types/decisionJourney";

interface Props {
  discovery: JourneyDiscovery | null;
  evidenceByPlace: Record<string, JourneyEvidence>;
  budgetAmount: number | null;
  budgetCurrency: string | null;
  onDecisionChange?: (
    decision: DecisionResult | null,
    mode: "live" | "fictional",
  ) => void;
  demoLaunchId?: number;
}

interface Candidate {
  place_id: string;
  name: string;
  status: string;
  reported_subtotal_minor: number | null;
  reasons: string[];
  evidence_gaps: string[];
}

export interface DecisionResult {
  mode: "CLIENT_SNAPSHOT_REPLANNING";
  decision_status: string;
  selected: Candidate | null;
  candidates: Candidate[];
  evaluated_at: string;
  recommended_next_action: string;
  purchase_allowed: false;
  notice: string;
}

interface DecisionEvent {
  signature: string;
  time: string;
  leader: string | null;
  description: string;
}

function readable(value: string) {
  return value.replaceAll("_", " ");
}

function rupees(minor: number | null) {
  if (minor === null) return "Unknown";

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
  }).format(minor / 100);
}

const PRODUCT = "65W USB-C PD laptop charger";

function fictionalMerchant(
  id: string,
  price: number,
  stock: number,
  time: string,
) {
  return {
    place_id: id,
    name: id,
    evidence: {
      product_query: PRODUCT,
      status: "REPORTED_UNVERIFIED",
      submission: {
        product_name: "Synthetic 65W charger",
        stock_quantity: stock,
        price_minor: price * 100,
        currency: "INR",
        delivery_available: true,
        submitted_at: time,
      },
      assessment: {
        status: "REPORTED_UNVERIFIED",
        freshness: "RECENT_REPORT",
        eligible_for_commitment: false,
      },
    },
  };
}

export default function AdaptiveDecisionPanel({
  discovery,
  evidenceByPlace,
  budgetAmount,
  budgetCurrency,
  onDecisionChange,
  demoLaunchId = 0,
}: Props) {
  const [quantity, setQuantity] = useState(1);
  const [deliveryRequired, setDeliveryRequired] = useState(false);

  // null = genuine customer journey;
  // 0/1 = isolated, fictional demonstration.
  const [demoStep, setDemoStep] = useState<0 | 1 | null>(null);

  const [result, setResult] = useState<DecisionResult | null>(null);

  const [history, setHistory] = useState<DecisionEvent[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Recheck age-sensitive evidence every minute.
  const [timeRevision, setTimeRevision] = useState(0);

  useEffect(() => {
    if (demoLaunchId === 0) return;

    setDemoStep(0);
    setHistory([]);
    setResult(null);
    setError("");

    onDecisionChange?.(null, "fictional");
  }, [demoLaunchId, onDecisionChange]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setTimeRevision((value) => value + 1);
    }, 60_000);

    return () => window.clearInterval(timer);
  }, []);

  const payload = useMemo(() => {
    if (demoStep !== null) {
      const timestamp = new Date().toISOString();

      return {
        customer: {
          product_query: PRODUCT,
          budget_minor: 100000,
          required_quantity: quantity,
          delivery_required: deliveryRequired,
        },
        merchants: [
          fictionalMerchant(
            "TEST_STORE_A",
            899,
            demoStep === 0 ? 3 : 0,
            timestamp,
          ),
          fictionalMerchant("TEST_STORE_B", 950, 5, timestamp),
        ],
      };
    }

    if (!discovery) return null;

    const inr = /^(inr|₹|rs\.?|rupees?)$/i.test((budgetCurrency ?? "").trim());

    const budgetMinor =
      inr && budgetAmount !== null ? Math.round(budgetAmount * 100) : null;

    return {
      customer: {
        product_query: discovery.product_query,
        budget_minor: budgetMinor,
        required_quantity: quantity,
        delivery_required: deliveryRequired,
      },
      merchants: discovery.merchants.map((merchant) => {
        const evidence = evidenceByPlace[merchant.place_id];

        return {
          place_id: merchant.place_id,
          name: merchant.name,
          evidence: evidence
            ? {
                product_query: evidence.product_query,
                status: evidence.status,
                submission: evidence.submission,
                assessment: evidence.assessment
                  ? {
                      status: evidence.assessment.status,
                      freshness: evidence.assessment.freshness,
                      eligible_for_commitment:
                        evidence.assessment.eligible_for_commitment,
                    }
                  : null,
              }
            : null,
        };
      }),
    };
  }, [
    discovery,
    evidenceByPlace,
    budgetAmount,
    budgetCurrency,
    quantity,
    deliveryRequired,
    demoStep,
    timeRevision,
  ]);

  useEffect(() => {
    if (!payload) {
      setResult(null);
      setError("");
      onDecisionChange?.(null, "live");
      return;
    }
    const controller = new AbortController();
    const timeout = window.setTimeout(async () => {
      setLoading(true);
      setError("");

      try {
        const response = await fetch("/api/journey/replan", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          cache: "no-store",
          signal: controller.signal,
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(
            typeof body.detail === "string"
              ? body.detail
              : `Replanning failed (HTTP ${response.status})`,
          );
        }

        const next = (await response.json()) as DecisionResult;

        if (controller.signal.aborted) return;

        setResult(next);

        onDecisionChange?.(next, demoStep === null ? "live" : "fictional");

        // Ignore evaluated_at because reevaluating an unchanged
        // decision should not create a duplicate timeline event.
        const signature = JSON.stringify({
          status: next.decision_status,
          selected: next.selected?.place_id ?? null,
          candidates: next.candidates.map((candidate) => ({
            id: candidate.place_id,
            status: candidate.status,
            price: candidate.reported_subtotal_minor,
            reasons: candidate.reasons,
            gaps: candidate.evidence_gaps,
          })),
        });

        setHistory((previous) => {
          if (previous.length && previous[0].signature === signature) {
            return previous;
          }

          const last = previous[0];
          const leader = next.selected?.place_id ?? null;

          let description: string;

          if (!last) {
            description = leader
              ? `Initial provisional leader: ${leader}.`
              : "Initial assessment: no provisional offer.";
          } else if (last.leader !== leader) {
            const previousLeaderNow = next.candidates.find(
              (candidate) => candidate.place_id === last.leader,
            );

            const explanation = previousLeaderNow?.reasons.length
              ? ` Previous leader excluded: ${previousLeaderNow.reasons
                  .map(readable)
                  .join(", ")}.`
              : "";

            description =
              `Leader changed: ${last.leader ?? "none"} → ` +
              `${leader ?? "none"}.${explanation}`;
          } else {
            description =
              "Evidence or offer eligibility changed; decision reevaluated.";
          }

          return [
            {
              signature,
              time: next.evaluated_at,
              leader,
              description,
            },
            ...previous,
          ].slice(0, 12);
        });
      } catch (err) {
        if (controller.signal.aborted) return;

        setResult(null);
        onDecisionChange?.(null, demoStep === null ? "live" : "fictional");
        setError(
          err instanceof Error
            ? err.message
            : "Unable to evaluate merchant evidence.",
        );
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }, 200);

    return () => {
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [payload, demoStep, onDecisionChange]);

  function activateDemo(step: 0 | 1 | null) {
    setDemoStep(step);
    setHistory([]);
    setResult(null);
    setError("");

    onDecisionChange?.(null, step === null ? "live" : "fictional");
  }

  const isDemo = demoStep !== null;

  return (
    <section
      aria-label="Adaptive decision intelligence"
      className="min-w-0 rounded-2xl border border-[#30415B] bg-[#111827] p-4 lg:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <BrainCircuit size={19} className="text-sky-400" />
            <h2 className="text-sm font-semibold">
              Adaptive Decision Intelligence
            </h2>
          </div>

          <p className="mt-1 text-xs text-slate-400">
            Backend constraints · Freshness checks · Automatic replanning
          </p>
        </div>

        <span className="rounded-full border border-amber-500/25 px-3 py-1.5 text-[11px] text-amber-300">
          {isDemo ? "FICTIONAL SCENARIO" : "LIVE REPORT ADVISORY"}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Required quantity
          <input
            type="number"
            min={1}
            max={20}
            value={quantity}
            onChange={(event) => {
              const value = Number(event.target.value);

              if (Number.isInteger(value)) {
                setQuantity(Math.max(1, Math.min(20, value)));
              }
            }}
            className="mt-1 block w-28 rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
          />
        </label>

        <label className="flex items-center gap-2 pb-2 text-xs text-slate-300">
          <input
            type="checkbox"
            checked={deliveryRequired}
            onChange={(event) => setDeliveryRequired(event.target.checked)}
          />
          Delivery required
        </label>

        <button
          type="button"
          onClick={() => activateDemo(0)}
          className="rounded-lg border border-sky-500/30 px-3 py-2.5 text-xs text-sky-300 hover:bg-sky-500/10"
        >
          <Play size={13} className="mr-1 inline" />
          Run fictional example
        </button>

        {isDemo && (
          <>
            <button
              type="button"
              onClick={() => {
                setDemoStep(1);
                setResult(null);
                onDecisionChange?.(null, "fictional");
              }}
              disabled={demoStep === 1}
              className="rounded-lg bg-amber-500 px-3 py-2.5 text-xs font-semibold text-slate-950 disabled:opacity-40"
            >
              Simulate Store A stock-out
            </button>

            <button
              type="button"
              onClick={() => activateDemo(null)}
              className="rounded-lg border border-slate-700 px-3 py-2.5 text-xs"
            >
              Return to real evidence
            </button>
          </>
        )}
      </div>

      {isDemo && (
        <p className="mt-3 text-xs leading-5 text-amber-300">
          Fictional merchant records only. The stock-out is a simulated
          replacement snapshot, not an edit to a real merchant submission.
        </p>
      )}

      {loading && (
        <p className="mt-3 flex items-center gap-2 text-xs text-sky-300">
          <RefreshCw size={13} className="animate-spin" />
          Recalculating decision...
        </p>
      )}

      {error && (
        <p role="alert" className="mt-3 text-xs text-rose-300">
          {error}
        </p>
      )}

      {!payload && !isDemo && (
        <p className="mt-4 text-xs text-slate-400">
          Discover stores to begin evidence-aware replanning, or run the
          fictional example.
        </p>
      )}

      {result && (
        <div className="mt-4 grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)]">
          <div className="min-w-0 space-y-4">
            <div className="rounded-xl border border-sky-500/20 bg-[#0A101B] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-sky-400">
                Current provisional decision
              </p>

              {result.selected ? (
                <>
                  <p className="mt-3 break-words text-lg font-semibold">
                    {result.selected.name}
                  </p>

                  <p className="mt-2 text-2xl font-semibold">
                    {rupees(result.selected.reported_subtotal_minor)}
                  </p>

                  <p className="mt-2 text-xs text-slate-400">
                    Reported item subtotal · Quantity {quantity}
                  </p>
                </>
              ) : (
                <p className="mt-3 text-sm font-semibold text-amber-300">
                  No provisionally eligible offer
                </p>
              )}

              <p className="mt-3 text-xs text-slate-400">
                Next action: {readable(result.recommended_next_action)}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-[#0A101B] p-4">
              <h3 className="text-sm font-semibold">Merchant evaluations</h3>

              <div className="mt-3 space-y-3">
                {result.candidates.map((candidate) => (
                  <div
                    key={candidate.place_id}
                    className="rounded-lg border border-slate-800 p-3"
                  >
                    <div className="flex flex-wrap justify-between gap-2">
                      <p className="break-words text-xs font-semibold">
                        {candidate.name}
                      </p>

                      <span className="text-xs text-sky-300">
                        {readable(candidate.status)}
                      </span>
                    </div>

                    <p className="mt-2 text-xs text-slate-400">
                      Reported subtotal:{" "}
                      {rupees(candidate.reported_subtotal_minor)}
                    </p>

                    {candidate.reasons.length > 0 && (
                      <p className="mt-2 break-words text-xs leading-5 text-rose-300">
                        Excluded because:{" "}
                        {candidate.reasons.map(readable).join(" · ")}
                      </p>
                    )}

                    {candidate.evidence_gaps.length > 0 && (
                      <p className="mt-2 break-words text-xs leading-5 text-amber-300">
                        Evidence gaps:{" "}
                        {candidate.evidence_gaps.map(readable).join(" · ")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="min-w-0 space-y-4">
            <div className="rounded-xl border border-slate-800 bg-[#0A101B] p-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold">
                <History size={16} className="text-sky-400" />
                Decision timeline
              </h3>

              {history.length === 0 ? (
                <p className="mt-3 text-xs text-slate-500">
                  Awaiting first evaluation.
                </p>
              ) : (
                <div className="mt-3 space-y-3">
                  {history.map((item) => (
                    <div
                      key={item.time + item.signature}
                      className="border-l-2 border-sky-500/40 pl-3"
                    >
                      <p className="text-xs leading-5">{item.description}</p>

                      <p className="mt-1 text-[11px] text-slate-500">
                        {new Date(item.time).toLocaleString()}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-start gap-2 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
              <ShieldAlert
                size={17}
                className="mt-0.5 shrink-0 text-amber-300"
              />

              <div>
                <p className="text-xs font-semibold text-amber-300">
                  Not authorized for purchase
                </p>

                <p className="mt-2 text-xs leading-5 text-slate-400">
                  This decision evaluates reported claims and preliminary
                  constraints. Merchant ownership, compatibility, and final
                  delivery charges are not independently authenticated.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
