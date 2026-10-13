import {
  ClipboardList,
  MapPin,
  RefreshCw,
  ShieldAlert,
  Store,
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
  onOpenDiscovery: () => void;
}

function money(minor: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
  }).format(minor / 100);
}

function normalize(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

function humanStatus(status: string) {
  return status.replaceAll("_", " ");
}

export default function CustomerDecisionPanel({
  discovery,
  evidenceByPlace,
  budgetAmount,
  budgetCurrency,
  onOpenDiscovery,
}: Props) {
  const merchants = discovery?.merchants ?? [];

  const reports = merchants
    .map((merchant) => ({
      merchant,
      evidence: evidenceByPlace[merchant.place_id],
    }))
    .filter(({ evidence }) => {
      return (
        Boolean(discovery) &&
        Boolean(evidence?.submission) &&
        normalize(evidence.product_query) ===
          normalize(discovery?.product_query ?? "")
      );
    });

  const hasInrBudget =
    budgetAmount !== null &&
    /^(inr|₹|rs\.?|rupees?)$/i.test((budgetCurrency ?? "").trim());

  const budgetMinor =
    hasInrBudget && budgetAmount !== null
      ? Math.round(budgetAmount * 100)
      : null;

  // Provisional comparison of merchant-submitted claims.
  // Not independent verification or an OR-Tools recommendation.
  const comparable = reports
    .filter(({ evidence }) => {
      const submission = evidence.submission;

      const isKnownStale = (evidence.assessment?.freshness ?? "")
        .toUpperCase()
        .includes("STALE");

      return (
        submission !== null &&
        submission !== undefined &&
        evidence.status !== "EXPIRED" &&
        !isKnownStale &&
        submission.currency === "INR" &&
        submission.stock_quantity > 0 &&
        submission.price_minor !== null &&
        submission.price_minor > 0 &&
        (budgetMinor === null || submission.price_minor <= budgetMinor)
      );
    })
    .sort(
      (a, b) =>
        (a.evidence.submission!.price_minor ?? Infinity) -
          (b.evidence.submission!.price_minor ?? Infinity) ||
        a.merchant.place_id.localeCompare(b.merchant.place_id),
    );

  const cheapest = comparable[0] ?? null;

  const nextAction = cheapest
    ? (cheapest.evidence.assessment?.recommended_next_action.label ??
      "Review identity, compatibility and delivery evidence.")
    : reports.length > 0
      ? "Investigate missing or insufficient merchant offers."
      : "Request fresh stock and price information from merchants.";

  return (
    <section
      aria-label="Connected merchant decision workspace"
      className="rounded-2xl border border-[#30415B] bg-[#111827] p-4 lg:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Store size={18} className="text-sky-400" />
            <h2 className="text-sm font-semibold">
              Connected Merchant Intelligence
            </h2>
          </div>

          <p className="mt-1.5 text-xs text-slate-400">
            Google Places discovery + merchant-reported evidence
          </p>
        </div>

        <button
          type="button"
          onClick={onOpenDiscovery}
          className="inline-flex items-center gap-2 rounded-lg border border-sky-500/30 px-3 py-2 text-xs font-semibold text-sky-300 hover:bg-sky-500/10"
        >
          <RefreshCw size={14} />
          Open discovery and refresh evidence
        </button>
      </div>

      {!discovery ? (
        <div className="mt-4 rounded-xl border border-dashed border-slate-700 bg-[#0A101B] p-5 text-center">
          <MapPin size={27} className="mx-auto text-slate-500" />

          <h3 className="mt-3 text-sm font-semibold">
            Ready to discover merchants
          </h3>

          <p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-slate-400">
            Use the customer journey above to find stores. Real business
            listings and reported merchant evidence will appear together here.
          </p>
        </div>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[
              {
                label: "Stores discovered",
                value: merchants.length,
              },
              {
                label: "Merchant reports",
                value: reports.length,
              },
              {
                label: "Comparable prices",
                value: comparable.length,
              },
              {
                label: "Purchase-ready",
                value: 0,
              },
            ].map((metric) => (
              <div
                key={metric.label}
                className="rounded-lg border border-slate-800 bg-[#0A101B] p-3"
              >
                <p className="text-[11px] text-slate-500">{metric.label}</p>

                <p className="mt-2 text-xl font-semibold">{metric.value}</p>
              </div>
            ))}
          </div>

          <p className="mt-3 text-xs text-slate-400">
            Search: {discovery.product_query} · {discovery.area} ·{" "}
            {discovery.category}
          </p>

          <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.75fr)]">
            <div className="rounded-xl border border-slate-800 bg-[#0A101B] p-4">
              <h3 className="text-sm font-semibold">Live merchant evidence</h3>

              {merchants.length === 0 ? (
                <p className="mt-3 text-xs text-slate-400">
                  No businesses were returned for this search.
                </p>
              ) : (
                <div className="mt-3 max-h-[min(60dvh,520px)] space-y-2 overflow-y-auto overscroll-contain pr-1">
                  {merchants.slice(0, 8).map((merchant) => {
                    const evidence = evidenceByPlace[merchant.place_id];

                    const submission =
                      evidence &&
                      normalize(evidence.product_query) ===
                        normalize(discovery.product_query)
                        ? evidence.submission
                        : null;

                    const assessment =
                      evidence &&
                      normalize(evidence.product_query) ===
                        normalize(discovery.product_query)
                        ? evidence.assessment
                        : null;

                    const displayStatus = submission
                      ? "MERCHANT REPORTED"
                      : evidence
                        ? "AWAITING / OTHER REQUEST"
                        : "NOT INVESTIGATED";

                    return (
                      <div
                        key={merchant.place_id}
                        className="rounded-lg border border-slate-800 p-3"
                      >
                        <div className="flex flex-wrap justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-xs font-semibold">
                              {merchant.name}
                            </p>

                            <p className="mt-1 text-[11px] text-slate-500">
                              {humanStatus(displayStatus)}
                            </p>
                          </div>

                          <span className="text-sm font-semibold text-sky-300">
                            {submission?.price_minor != null
                              ? money(submission.price_minor)
                              : "Price unknown"}
                          </span>
                        </div>

                        <p className="mt-2 text-[11px] text-slate-400">
                          Stock:{" "}
                          {submission
                            ? `${submission.stock_quantity} reported`
                            : "Unknown"}
                          {" · "}
                          Compatibility: not independently verified
                        </p>

                        {assessment && (
                          <p className="mt-1 text-[11px] text-amber-300">
                            Next: {assessment.recommended_next_action.label}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {merchants.length > 8 && (
                <p className="mt-2 text-[11px] text-slate-500">
                  Showing 8 of {merchants.length} listings. Open discovery for
                  the full list.
                </p>
              )}
            </div>

            <div className="space-y-3">
              <div className="rounded-xl border border-sky-500/20 bg-sky-500/5 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-sky-400">
                  Reported price preview — not decision validated
                </p>

                {cheapest?.evidence.submission?.price_minor != null ? (
                  <>
                    <p className="mt-3 text-xl font-semibold">
                      {money(cheapest.evidence.submission.price_minor)}
                    </p>

                    <p className="mt-1 text-xs font-medium">
                      {cheapest.merchant.name}
                    </p>

                    <p className="mt-2 text-xs leading-5 text-slate-400">
                      Raw merchant-reported unit price preview. It is not the
                      final advisory result. The backend Adaptive Decision
                      Intelligence panel below evaluates budget, quantity,
                      stock, freshness and evidence gaps.
                    </p>

                    {budgetMinor !== null && (
                      <p className="mt-2 text-xs text-amber-300">
                        {cheapest.evidence.submission.price_minor > budgetMinor
                          ? "Reported item price exceeds the stated budget."
                          : "Reported item price fits the budget before unknown fees."}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="mt-3 text-xs leading-5 text-slate-400">
                    No comparable reported price yet. Google Places does not
                    establish inventory or selling prices.
                  </p>
                )}
              </div>

              <div className="rounded-xl border border-slate-800 bg-[#0A101B] p-4">
                <h3 className="flex items-center gap-2 text-xs font-semibold">
                  <ClipboardList size={15} className="text-sky-400" />
                  Decision trace
                </h3>

                <ol className="mt-3 space-y-2 text-xs leading-5 text-slate-400">
                  <li>
                    1. Google Places returned {merchants.length} store
                    listing(s).
                  </li>
                  <li>
                    2. {reports.length} matching merchant response(s) are
                    currently available.
                  </li>
                  <li>
                    3. {comparable.length} offer(s) have a reported INR price
                    and positive stock.
                  </li>
                  <li>
                    4. Merchant identity, compatibility, final charges and
                    fulfillment still require independent checks.
                  </li>
                </ol>

                <p className="mt-3 text-xs font-medium text-sky-300">
                  Next action: {nextAction}
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
            <ShieldAlert size={16} className="mt-0.5 shrink-0 text-amber-400" />

            <p className="text-xs leading-5 text-amber-200">
              All merchant prices and stock are respondent-provided, not
              independently authenticated. No offer is purchase-ready. Final
              delivery charges and device compatibility remain unconfirmed.
            </p>
          </div>
        </>
      )}
    </section>
  );
}
