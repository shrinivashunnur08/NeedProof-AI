import {
  ArrowRight,
  BrainCircuit,
  MapPin,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import type {
  JourneyDiscovery,
  JourneyEvidence,
} from "../types/decisionJourney";
import type { DecisionResult } from "./AdaptiveDecisionPanel";
type DecisionMode = "live" | "fictional";
interface Props {
  hasIntent: boolean;
  isCurrent: boolean;
  discovery: JourneyDiscovery | null;
  evidenceByPlace: Record<string, JourneyEvidence>;
  decision: DecisionResult | null;
  decisionMode: DecisionMode;
  onStart: () => void;
  onDiscover: () => void;
  onReviewDecision: () => void;
  onLaunchDemo: () => void;
  // Optional, browser-only Firebase showcase adaptation.
  showcaseMode?: boolean;
  showcaseDemoStarted?: boolean;
  showcaseDemoReplanned?: boolean;
}
const STAGES = ["Understand", "Discover", "Investigate", "Decide"];
function normalized(text: string) {
  return text.trim().toLowerCase().replace(/\s+/g, " ");
}
function currency(minor: number | null) {
  if (minor === null) return "Price unavailable";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
  }).format(minor / 100);
}
function actionLabel(code: string) {
  const labels: Record<string, string> = {
    DISCOVER_MERCHANTS: "Discover nearby stores",
    REQUEST_MERCHANT_RESPONSES: "Collect stock and price evidence",
    REVIEW_MISSING_EVIDENCE: "Review missing merchant evidence",
    FIND_OR_REFRESH_ALTERNATIVE_OFFERS: "Find or refresh alternative offers",
    VERIFY_IDENTITY_COMPATIBILITY_AND_DELIVERY:
      "Verify identity, compatibility and fulfillment",
  };
  return labels[code] ?? code.replaceAll("_", " ").toLowerCase();
}
export default function DecisionSpotlight({
  hasIntent,
  isCurrent,
  discovery,
  evidenceByPlace,
  decision,
  decisionMode,
  onStart,
  onDiscover,
  onReviewDecision,
  onLaunchDemo,
  showcaseMode = false,
  showcaseDemoStarted = false,
  showcaseDemoReplanned = false,
}: Props) {
  const ready = hasIntent && isCurrent;
  const fictional = ready && decisionMode === "fictional" && decision !== null;
  const merchants = discovery?.merchants ?? [];
  const reportCount = merchants.filter((merchant) => {
    const evidence = evidenceByPlace[merchant.place_id];
    return (
      evidence?.submission !== null &&
      evidence?.submission !== undefined &&
      normalized(evidence.product_query) ===
        normalized(discovery?.product_query ?? "")
    );
  }).length;
  const completedStages = showcaseMode
    ? [
        ready,
        ready && showcaseDemoStarted,
        ready && showcaseDemoStarted && decision !== null,
        ready && showcaseDemoReplanned,
      ]
    : [
        ready,
        ready && discovery !== null,
        ready && reportCount > 0,
        ready && decision !== null && decisionMode === "live",
      ];

  const stageLabels = showcaseMode
    ? ["Understand", "Simulate", "Evaluate", "Replan"]
    : STAGES;
  const selected = ready ? (decision?.selected ?? null) : null;
  let headline = "Start with the customer's need";
  let description =
    "Describe what the customer wants. Gemini will extract the requirements before NeedProof investigates merchants.";
  let primaryLabel = "Go to customer request";
  let primaryAction = onStart;
  if (hasIntent && !isCurrent) {
    headline = "Your customer request has changed";
    description =
      "Run Gemini extraction again. Previous decisions should not be used for this updated request.";
  } else if (ready && fictional) {
    headline = selected
      ? `Fictional leader: ${selected.name}`
      : "No provisional offer in this fictional test";
    description = selected
      ? `${currency(selected.reported_subtotal_minor)} reported item subtotal in an isolated simulation.`
      : "The test scenario currently has no eligible merchant.";
    primaryLabel = "Inspect simulated decision";
    primaryAction = onReviewDecision;
  } else if (ready && selected) {
    headline = `Provisional offer: ${selected.name}`;
    description =
      `${currency(selected.reported_subtotal_minor)} reported item subtotal. ` +
      "Merchant identity, compatibility and fulfillment still require independent checks.";
    primaryLabel = "Inspect decision reasoning";
    primaryAction = onReviewDecision;
  } else if (ready && showcaseMode) {
    headline = "Gemini understood the request. Explore a fictional decision.";
    description =
      "The Firebase showcase has no live merchant feed. " +
      "Explore an explicitly fictional example of evidence-aware reprioritization.";
    primaryLabel = "Launch fictional scenario";
    primaryAction = onLaunchDemo;
  } else if (ready && discovery) {
    headline =
      reportCount > 0
        ? "Evidence received. More checks are needed."
        : `${merchants.length} candidate stores discovered`;
    description = decision
      ? actionLabel(decision.recommended_next_action)
      : "Review the discovered businesses and request reliable stock, price and compatibility evidence.";
    primaryLabel = "Open discovery & evidence";
    primaryAction = onDiscover;
  } else if (ready) {
    headline = "Find stores that could fulfill this request";
    description =
      "Gemini has interpreted the customer need. Discover nearby merchants to begin investigating real evidence.";
    primaryLabel = "Discover real stores";
    primaryAction = onDiscover;
  }
  return (
    <section
      aria-label="NeedProof decision spotlight"
      className="relative min-w-0 overflow-hidden rounded-2xl border border-sky-500/25 bg-[#101A2A] p-4 shadow-[0_12px_45px_-30px_rgba(14,165,233,0.5)] sm:p-5 lg:p-6"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-20 -top-28 h-64 w-64 rounded-full bg-sky-500/[0.07] blur-3xl"
      />
      <div className="relative grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,0.9fr)] xl:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Sparkles size={15} className="text-sky-400" aria-hidden="true" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-300">
              NeedProof decision room
            </p>
            {fictional && (
              <span className="rounded-full border border-amber-500/30 px-2 py-1 text-[10px] font-semibold text-amber-300">
                FICTIONAL DEMO
              </span>
            )}
          </div>
          <div aria-live="polite" aria-atomic="true">
            <h2 className="mt-3 break-words text-xl font-semibold leading-tight tracking-tight text-white sm:text-2xl">
              {headline}
            </h2>
            <p className="mt-2 max-w-2xl text-xs leading-6 text-slate-400 sm:text-sm">
              {description}
            </p>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={primaryAction}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-sky-500 px-4 py-2.5 text-xs font-semibold text-slate-950 transition-colors hover:bg-sky-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300"
            >
              {primaryLabel}
              <ArrowRight size={15} aria-hidden="true" />
            </button>
            {ready && !showcaseMode && (
              <button
                type="button"
                onClick={onLaunchDemo}
                className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-700 bg-[#111827] px-4 py-2.5 text-xs font-semibold text-slate-200 transition-colors hover:border-sky-500/40 hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-sky-400"
              >
                Launch decision demo
              </button>
            )}
            {ready && discovery && !fictional && (
              <span className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-400">
                {merchants.length} discovered · {reportCount} reports
              </span>
            )}
          </div>
          <div className="mt-4 flex items-start gap-2 text-[11px] leading-5 text-amber-200/85">
            <ShieldAlert
              size={15}
              className="mt-0.5 shrink-0"
              aria-hidden="true"
            />
            <span>
              {fictional
                ? "Simulated evidence only. No real merchant is represented."
                : "Reported evidence is not independent verification. No purchase is authorized."}
            </span>
          </div>
        </div>
        <div className="min-w-0 rounded-xl border border-[#304058] bg-[#080F1B]/75 p-3 sm:p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="text-xs font-semibold text-slate-200">
              Decision progress
            </p>
            <BrainCircuit
              size={17}
              className="text-sky-400"
              aria-hidden="true"
            />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-2">
            {stageLabels.map((stage, index) => {
              const complete = completedStages[index];
              return (
                <div
                  key={stage}
                  className={
                    "min-w-0 rounded-lg border p-2.5 " +
                    (complete
                      ? "border-sky-500/30 bg-sky-500/10"
                      : "border-slate-800 bg-[#0A101B]")
                  }
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={
                        "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold " +
                        (complete
                          ? "bg-sky-400 text-slate-950"
                          : "bg-slate-800 text-slate-400")
                      }
                    >
                      {complete ? "✓" : index + 1}
                    </span>
                    <span className="min-w-0 break-words text-[11px] font-medium text-slate-200">
                      {stage}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-400">
            <MapPin size={13} aria-hidden="true" />
            <span className="break-words">
              {showcaseMode
                ? "Hosted showcase · No real merchant discovery"
                : discovery && ready
                  ? `${discovery.area} · ${discovery.category}`
                  : "Location and merchants pending"}
            </span>
          </div>
          <p className="mt-2 text-[10px] leading-4 text-slate-500">
            Stages indicate workflow progress, not a merchant trust or
            verification score.
          </p>
        </div>
      </div>
    </section>
  );
}
