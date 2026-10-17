import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import CatalogModal from "./components/CatalogModal";
import LiveMerchantsModal from "./components/LiveMerchantsModal";
import EvidenceIntelligenceModal from "./components/EvidenceIntelligenceModal";
import CommerceOptimizerModal from "./components/CommerceOptimizerModal";
import AssuranceDeskModal from "./components/AssuranceDeskModal";
import MerchantOnboardingModal from "./components/MerchantOnboardingModal";
import TransactionSafetyModal from "./components/TransactionSafetyModal";
import BenchmarkDashboardModal from "./components/BenchmarkDashboardModal";
// import DecisionJourneyCard from "./components/DecisionJourneyCard";
import CustomerDecisionPanel from "./components/CustomerDecisionPanel";
import AdaptiveDecisionPanel from "./components/AdaptiveDecisionPanel";
import DecisionSpotlight from "./components/DecisionSpotlight";
import type { DecisionResult } from "./components/AdaptiveDecisionPanel";
import { makeJourneyPrefill } from "./types/decisionJourney";

import type {
  JourneyDiscovery,
  JourneyEvidence,
} from "./types/decisionJourney";
import {
  AlertCircle,
  ArrowRight,
  BadgeCheck,
  BrainCircuit,
  Clock3,
  MapPin,
  RefreshCw,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Wallet,
  X,
} from "lucide-react";

type Health = "checking" | "online" | "offline";

type Intent = {
  language: string;
  product_category: string | null;
  requested_product: string;
  budget_amount: number | null;
  budget_currency: string | null;
  delivery_deadline_text: string | null;
  delivery_location: string | null;
  required_specifications: string[];
  preferred_specifications: string[];
  missing_information: string[];
  clarification_questions: string[];
  compatibility_needs_verification: boolean;
};

type IntentResponse = {
  source: "vertex_ai";
  model: string;
  status: "extracted_unverified";
  intent: Intent;
  processing_ms: number;
  usage: { input_tokens: number | null; output_tokens: number | null } | null;
};

const sample =
  "I need a genuine 65W USB-C PD laptop charger near Thane, under ₹1000, available today before 6 PM. Please check stock, laptop compatibility and delivery.";

const navigation = [
  "Demand Studio",
  "Evidence Intelligence",
  "Commerce Optimizer",
  "Merchant Catalog",
  "Scenario Lab",
  "Business Intelligence",
];

function DetailBox({
  icon,
  title,
  value,
}: {
  icon: ReactNode;
  title: string;
  value: string;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-[#263247] bg-[#0A101B] px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-xs text-slate-400">
        {icon}
        {title}
      </div>
      <div
        className="mt-1 break-words [overflow-wrap:anywhere] text-sm font-semibold leading-5 text-slate-100"
        title={value}
      >
        {value}
      </div>
    </div>
  );
}

function SummaryList({
  heading,
  items,
  empty,
  tone = "normal",
  limit = 4,
}: {
  heading: string;
  items: string[];
  empty: string;
  tone?: "normal" | "warning";
  limit?: number;
}) {
  const visible = items.slice(0, limit);
  return (
    <div className="min-w-0">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold text-slate-300">{heading}</h4>
        <span className="text-[11px] tabular-nums text-slate-500">
          {items.length}
        </span>
      </div>
      {visible.length ? (
        <div className="flex flex-wrap gap-1.5">
          {visible.map((item, i) => (
            <span
              key={`${item}-${i}`}
              title={item}
              className={`max-w-full min-w-0 whitespace-normal break-words [overflow-wrap:anywhere] rounded-lg border px-2.5 py-1.5 text-xs leading-5 ${
                tone === "warning"
                  ? "border-amber-500/25 bg-amber-500/10 text-amber-200"
                  : "border-[#2A3850] bg-[#111B2A] text-slate-200"
              }`}
            >
              {item}
            </span>
          ))}
          {items.length > limit && (
            <span className="rounded-lg border border-slate-700 px-2 py-1.5 text-xs text-slate-400">
              +{items.length - limit} more
            </span>
          )}
        </div>
      ) : (
        <p className="text-xs leading-5 text-slate-500">{empty}</p>
      )}
    </div>
  );
}

function AllDetails({
  result,
  onClose,
}: {
  result: IntentResponse;
  onClose: () => void;
}) {
  const intent = result.intent;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="details-title"
        className="max-h-[calc(100dvh-1rem)] w-full max-w-2xl overflow-y-auto overscroll-contain rounded-2xl border border-[#33445E] bg-[#111827] p-4 shadow-2xl sm:max-h-[90dvh] md:p-7"
      >
        <div className="sticky top-0 z-10 mb-5 flex items-center justify-between gap-3 border-b border-slate-800 bg-[#111827] pb-3">
          <div>
            <h2 id="details-title" className="text-lg font-semibold">
              Full extracted intent
            </h2>
            <p className="mt-1 text-xs text-amber-300">
              AI extraction — not independently verified
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close details"
            className="rounded-lg border border-slate-700 p-2 hover:bg-slate-800"
          >
            <X size={18} />
          </button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <DetailBox
            icon={<ShoppingBag size={14} />}
            title="Product"
            value={intent.requested_product}
          />
          <DetailBox
            icon={<BrainCircuit size={14} />}
            title="Category"
            value={intent.product_category ?? "Not specified"}
          />
          <DetailBox
            icon={<Wallet size={14} />}
            title="Budget"
            value={
              intent.budget_amount === null
                ? "Not specified"
                : `${intent.budget_currency ?? ""} ${intent.budget_amount.toLocaleString("en-IN")}`
            }
          />
          <DetailBox
            icon={<Clock3 size={14} />}
            title="Deadline"
            value={intent.delivery_deadline_text ?? "Not specified"}
          />
          <DetailBox
            icon={<MapPin size={14} />}
            title="Location"
            value={intent.delivery_location ?? "Not specified"}
          />
          <DetailBox
            icon={<BrainCircuit size={14} />}
            title="Language"
            value={intent.language}
          />
        </div>
        <div className="mt-5 space-y-5">
          {[
            ["Mandatory requirements", intent.required_specifications],
            ["Preferences", intent.preferred_specifications],
            ["Missing information", intent.missing_information],
            ["Clarification questions", intent.clarification_questions],
          ].map(([name, values]) => (
            <div key={name as string}>
              <h3 className="mb-2 text-sm font-semibold">{name as string}</h3>
              {(values as string[]).length ? (
                <ul className="space-y-1.5 text-sm text-slate-300">
                  {(values as string[]).map((value, i) => (
                    <li
                      key={i}
                      className="rounded-lg border border-slate-800 bg-[#0A101B] px-3 py-2"
                    >
                      {value}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">None</p>
              )}
            </div>
          ))}
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-sm text-amber-200">
            Compatibility needs verification:{" "}
            {intent.compatibility_needs_verification
              ? "Yes"
              : "Not flagged by extraction"}
          </div>
        </div>
      </section>
    </div>
  );
}

export default function NeedProofWorkspace() {
  const [health, setHealth] = useState<Health>("checking");
  const [request, setRequest] = useState(sample);
  const [result, setResult] = useState<IntentResponse | null>(null);
  const [analyzedRequest, setAnalyzedRequest] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [liveMerchantsOpen, setLiveMerchantsOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [commerceOpen, setCommerceOpen] = useState(false);
  const [assuranceOpen, setAssuranceOpen] = useState(false);
  const [merchantPortalOpen, setMerchantPortalOpen] = useState(false);
  const [transactionOpen, setTransactionOpen] = useState(false);
  const [benchmarkOpen, setBenchmarkOpen] = useState(false);
  const analysisSequence = useRef(0);

  const [analysisId, setAnalysisId] = useState(0);

  const [discovery, setDiscovery] = useState<JourneyDiscovery | null>(null);

  const [decisionView, setDecisionView] = useState<{
    result: DecisionResult;
    mode: "live" | "fictional";
  } | null>(null);
  const [demoLaunchId, setDemoLaunchId] = useState(0);
  const handleDecisionChange = useCallback(
    (next: DecisionResult | null, mode: "live" | "fictional") => {
      setDecisionView(next ? { result: next, mode } : null);
    },
    [],
  );

  const [evidenceByPlace, setEvidenceByPlace] = useState<
    Record<string, JourneyEvidence>
  >({});
  async function checkHealth() {
    setHealth("checking");
    try {
      const response = await fetch("/api/health", { cache: "no-store" });
      if (!response.ok) throw new Error("Backend unavailable");
      const data: { status?: string } = await response.json();
      setHealth(data.status === "ok" ? "online" : "offline");
    } catch {
      setHealth("offline");
    }
  }

  useEffect(() => {
    void checkHealth();
  }, []);

  useEffect(() => {
    if (!showAll) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setShowAll(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [showAll]);

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const submittedText = request.trim();
    const currentRun = ++analysisSequence.current;

    setLoading(true);
    setResult(null);
    setError("");

    //
    // Start a completely new customer decision journey.
    //
    setDiscovery(null);
    setEvidenceByPlace({});
    setDecisionView(null);
    setDemoLaunchId(0);
    setAnalyzedRequest("");
    setLiveMerchantsOpen(false);

    try {
      const response = await fetch("/api/intent/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: submittedText }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : `Request failed (${response.status})`,
        );
      }
      if (currentRun !== analysisSequence.current) {
        return;
      }

      setResult(data as IntentResponse);
      setAnalyzedRequest(submittedText);
      setAnalysisId(currentRun);
    } catch (err) {
      if (currentRun !== analysisSequence.current) {
        return;
      }
      setError(
        err instanceof Error
          ? err.message
          : "Could not extract customer intent",
      );
    } finally {
      if (currentRun === analysisSequence.current) {
        setLoading(false);
      }
    }
  }

  const intent = result?.intent;

  return (
    <div className="np-app flex min-h-dvh min-w-0 flex-col bg-[#080B12] text-slate-100 lg:flex-row lg:items-start">
      <aside className="hidden w-[240px] shrink-0 flex-col overflow-y-auto overscroll-contain border-r border-[#263247] bg-[#0D121C] px-4 py-5 lg:sticky lg:top-0 lg:flex lg:h-dvh lg:self-start">
        <div className="flex items-center gap-2.5 px-2">
          <div className="rounded-xl bg-sky-400/10 p-2 text-sky-400">
            <ShieldCheck size={22} />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight">
              NeedProof <span className="text-sky-400">AI</span>
            </h1>
            <p className="text-[10px] tracking-widest text-slate-500">
              COMMERCE INTELLIGENCE
            </p>
          </div>
        </div>
        <p className="mb-2 mt-9 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Workspace
        </p>

        <nav className="space-y-1">
          {navigation.map((item, i) =>
            item === "Evidence Intelligence" ? (
              <button
                key={item}
                type="button"
                onClick={() => setEvidenceOpen(true)}
                className="flex w-full items-center justify-between rounded-lg border border-sky-500/20 bg-sky-500/5 px-3 py-2.5 text-left text-xs font-medium text-sky-300 transition hover:bg-sky-500/15"
              >
                <span>{item}</span>
                <span className="text-[10px] text-emerald-400">LAB</span>
              </button>
            ) : item === "Commerce Optimizer" ? (
              <button
                key={item}
                type="button"
                onClick={() => setCommerceOpen(true)}
                className="flex w-full items-center justify-between rounded-lg border border-sky-500/20 bg-sky-500/5 px-3 py-2.5 text-left text-xs font-medium text-sky-300 transition hover:bg-sky-500/15"
              >
                <span>{item}</span>
                <span className="text-[10px] text-emerald-400">LAB</span>
              </button>
            ) : item === "Business Intelligence" ? (
              <button
                key={item}
                type="button"
                onClick={() => setBenchmarkOpen(true)}
                className="flex w-full items-center justify-between rounded-lg border border-sky-500/20 bg-sky-500/5 px-3 py-2.5 text-left text-xs font-medium text-sky-300 transition hover:bg-sky-500/15"
              >
                <span>{item}</span>
                <span className="text-[10px] text-emerald-400">LIVE</span>
              </button>
            ) : item === "Merchant Catalog" ? (
              <button
                key={item}
                type="button"
                onClick={() => setCatalogOpen(true)}
                className="flex w-full items-center justify-between rounded-lg border border-sky-500/25 bg-sky-500/10 px-3 py-2.5 text-left text-xs font-semibold text-sky-300 transition hover:bg-sky-500/20"
              >
                <span>{item}</span>
                <span className="text-[10px] font-medium text-emerald-400">
                  Demo
                </span>
              </button>
            ) : (
              <div
                key={item}
                className={`flex items-center justify-between rounded-lg px-3 py-2.5 text-xs ${
                  i === 0
                    ? "border border-sky-500/25 bg-sky-500/10 font-semibold text-sky-300"
                    : "text-slate-500"
                }`}
              >
                <span>{item}</span>
                {i > 0 && <span className="text-[10px] opacity-70">Soon</span>}
              </div>
            ),
          )}
        </nav>

        <button
          type="button"
          onClick={() => setLiveMerchantsOpen(true)}
          className="mt-2 flex w-full items-center justify-between rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2.5 text-left text-xs font-semibold text-emerald-300 transition hover:bg-emerald-500/15"
        >
          <span>Discover Real Stores</span>
          <span className="text-[10px]">LIVE</span>
        </button>

        <button
          type="button"
          onClick={() => setAssuranceOpen(true)}
          className="mt-2 flex w-full items-center justify-between rounded-lg border border-sky-500/25 bg-sky-500/10 px-3 py-2.5 text-left text-xs font-semibold text-sky-300 hover:bg-sky-500/20"
        >
          <span>Assurance Desk</span>
          <span className="text-[10px] text-amber-300">LOCAL</span>
        </button>
        <button
          type="button"
          onClick={() => setTransactionOpen(true)}
          className="mt-2 flex w-full items-center justify-between rounded-lg border border-sky-500/25 bg-sky-500/10 px-3 py-2.5 text-left text-xs font-semibold text-sky-300 hover:bg-sky-500/20"
        >
          <span>Transaction Safety Lab</span>
          <span className="text-[10px] text-amber-300">SIM</span>
        </button>
        <div className="mt-auto rounded-xl border border-[#273449] bg-[#101829] p-3">
          <button
            type="button"
            onClick={() => setMerchantPortalOpen(true)}
            className="mt-2 flex w-full items-center justify-between rounded-lg border border-sky-500/25 bg-sky-500/10 px-3 py-2.5 text-left text-xs font-semibold text-sky-300 hover:bg-sky-500/20"
          >
            <span>Merchant Portal</span>
            <span className="text-[10px] text-emerald-400">NEW</span>
          </button>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">Current focus</span>
            <span className="font-semibold text-sky-300">Unified Journey</span>
          </div>
          <p className="mt-2 text-[11px] leading-4 text-slate-500">
            Connecting discovery, evidence and decisions
          </p>
        </div>
      </aside>

      <main className="np-main flex w-full min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-[#263247] bg-[#080B12]/95 px-4 backdrop-blur-md sm:px-5 lg:px-7">
          <div className="min-w-0">
            <p className="text-[11px] text-slate-500">
              NeedProof / Customer Intelligence
            </p>
            <h2 className="text-sm font-semibold">Demand Studio</h2>
          </div>
          <button
            type="button"
            onClick={() => void checkHealth()}
            className="flex shrink-0 items-center gap-2 rounded-full border border-[#2A3850] bg-[#111827] px-3 py-2 text-xs"
            aria-label="Recheck backend connectivity"
          >
            <span
              className={`h-2 w-2 rounded-full ${health === "online" ? "bg-emerald-400" : health === "checking" ? "bg-amber-400" : "bg-rose-400"}`}
            />
            API {health}
            <RefreshCw size={13} className="text-slate-400" />
          </button>
        </header>

        <nav
          aria-label="Mobile workspace navigation"
          className="sticky top-14 z-20 flex gap-2 overflow-x-auto overscroll-x-contain border-b border-[#263247] bg-[#0D121C]/95 px-3 py-2 backdrop-blur-md lg:hidden"
        >
          {[
            {
              label: "Discover Stores",
              action: () => setLiveMerchantsOpen(true),
            },
            {
              label: "Evidence Lab",
              action: () => setEvidenceOpen(true),
            },
            {
              label: "Optimizer",
              action: () => setCommerceOpen(true),
            },
            {
              label: "Catalog",
              action: () => setCatalogOpen(true),
            },
            {
              label: "Benchmarks",
              action: () => setBenchmarkOpen(true),
            },
            {
              label: "Assurance",
              action: () => setAssuranceOpen(true),
            },
            {
              label: "Merchant Portal",
              action: () => setMerchantPortalOpen(true),
            },
            {
              label: "Safety Lab",
              action: () => setTransactionOpen(true),
            },
          ].map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={item.action}
              className="shrink-0 whitespace-nowrap rounded-lg border border-sky-500/20 bg-sky-500/5 px-3 py-2 text-xs font-medium text-sky-300 hover:bg-sky-500/15"
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div
          className="np-workspace
 flex w-full min-w-0 flex-col gap-4 px-4 py-4 lg:px-6 lg:py-5"
        >
          <div className="shrink-0">
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-sky-500/20 bg-sky-500/10 px-2.5 py-1 text-[11px] font-medium text-sky-300">
              <Sparkles size={12} /> Gemini on Vertex AI · Live extraction
            </div>
            <h1 className="text-2xl font-semibold tracking-tight lg:text-[27px]">
              Understand the need.{" "}
              <span className="text-sky-400">Before the decision.</span>
            </h1>
            <p className="mt-1 text-xs text-slate-400 sm:text-sm">
              Extract customer requirements, surface uncertainty, and identify
              the next questions to ask.
            </p>
          </div>

          <DecisionSpotlight
            hasIntent={result?.intent != null}
            isCurrent={result !== null && request.trim() === analyzedRequest}
            discovery={discovery}
            evidenceByPlace={evidenceByPlace}
            decision={decisionView?.result ?? null}
            decisionMode={decisionView?.mode ?? "live"}
            onStart={() => {
              document.getElementById("customer-request")?.focus();
            }}
            onDiscover={() => {
              setLiveMerchantsOpen(true);
            }}
            onReviewDecision={() => {
              document.getElementById("adaptive-decision")?.scrollIntoView({
                behavior: "smooth",
                block: "start",
              });
            }}
            onLaunchDemo={() => {
              setDemoLaunchId((previous) => previous + 1);

              document.getElementById("adaptive-decision")?.scrollIntoView({
                behavior: "smooth",
                block: "start",
              });
            }}
          />

          <div className="np-panels grid min-w-0 auto-rows-max items-stretch gap-4 lg:grid-cols-[minmax(0,0.93fr)_minmax(0,1.07fr)]">
            <section className="flex min-w-0 flex-col rounded-2xl border border-[#273449] bg-[#111827] p-4 lg:p-5">
              <div className="mb-4 flex shrink-0 items-center gap-2.5">
                <div className="rounded-lg bg-sky-500/10 p-2 text-sky-400">
                  <ShoppingBag size={18} />
                </div>
                <div>
                  <h2 className="text-sm font-semibold">Customer request</h2>
                  <p className="text-[11px] text-slate-500">
                    English · Hindi · Marathi
                  </p>
                </div>
              </div>
              <form onSubmit={analyze} className="flex min-w-0 flex-col">
                <label
                  htmlFor="customer-request"
                  className="mb-2 text-xs font-medium text-slate-300"
                >
                  What does the customer need?
                </label>
                <textarea
                  id="customer-request"
                  value={request}
                  onChange={(event) => setRequest(event.target.value)}
                  minLength={8}
                  maxLength={2000}
                  rows={5}
                  required
                  className="min-h-36 max-h-[55dvh] w-full min-w-0 resize-y rounded-xl border border-[#31425B] bg-[#080D17] p-3.5 text-sm leading-6 text-slate-100 outline-none placeholder:text-slate-600 focus:border-sky-500"
                  placeholder="Describe the customer's shopping request..."
                />
                <div className="mt-3 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setRequest(sample)}
                      className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
                    >
                      Load sample
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const nextSequence = ++analysisSequence.current;

                        setRequest("");
                        setResult(null);
                        setAnalyzedRequest("");

                        setAnalysisId(nextSequence);
                        setDiscovery(null);
                        setEvidenceByPlace({});
                        setDecisionView(null);
                        setDemoLaunchId(0);
                        setLiveMerchantsOpen(false);
                        setShowAll(false);
                        setLoading(false);
                        setError("");
                      }}
                      className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
                    >
                      Clear
                    </button>
                  </div>
                  <span className="text-[11px] tabular-nums text-slate-600">
                    {request.length}/2000
                  </span>
                </div>
                <button
                  type="submit"
                  disabled={loading || health !== "online"}
                  className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-sky-500 text-sm font-semibold text-[#07101D] hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <BrainCircuit size={18} />
                  {loading
                    ? "Analyzing with Gemini..."
                    : "Extract customer intelligence"}
                  {!loading && <ArrowRight size={17} />}
                </button>
              </form>
              {error && (
                <div
                  role="alert"
                  className="mt-3 flex items-start gap-2 rounded-lg border border-rose-500/25 bg-rose-500/10 p-3 text-xs leading-5 text-rose-200"
                >
                  <AlertCircle size={16} className="mt-0.5 shrink-0" /> {error}
                </div>
              )}
              <p className="mt-4 border-t border-slate-800 pt-3 text-[11px] leading-5 text-slate-500">
                Gemini interprets the customer need. NeedProof then investigates
                merchant evidence before issuing a provisional recommendation.
              </p>
            </section>

            <section
              className="flex min-w-0 flex-col gap-3 rounded-2xl border border-[#273449] bg-[#111827] p-4 lg:p-5"
              aria-label="Extraction results"
            >
              {result && request.trim() !== analyzedRequest && (
                <div
                  role="status"
                  className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-xs text-amber-300"
                >
                  The request has changed since this Gemini analysis. Re-run
                  extraction before relying on these details.
                </div>
              )}
              {!result || !intent ? (
                <div className="flex min-h-64 flex-1 flex-col items-center justify-center text-center">
                  <BrainCircuit size={37} className="text-slate-600" />
                  <h3 className="mt-4 text-sm font-semibold">
                    {loading
                      ? "Waiting for Gemini..."
                      : "Awaiting customer intelligence"}
                  </h3>
                  <p className="mt-2 max-w-xs text-xs leading-5 text-slate-500">
                    Submit a request to see structured requirements, missing
                    information and clarification questions.
                  </p>
                </div>
              ) : (
                <>
                  <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
                    <h2 className="text-sm font-semibold">Extracted intent</h2>
                    <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-300">
                      Unverified extraction
                    </span>
                  </div>

                  <div className="shrink-0 rounded-xl border border-[#2A3850] bg-[#080D17] p-3">
                    <p className="text-[11px] text-slate-500">
                      Requested product
                    </p>
                    <div
                      className="mt-1 break-words [overflow-wrap:anywhere] text-sm font-semibold leading-5"
                      title={intent.requested_product}
                    >
                      {intent.requested_product}
                    </div>
                    <p className="mt-0.5 break-words [overflow-wrap:anywhere] text-[11px] leading-5 text-slate-500">
                      {intent.product_category ?? "Category not specified"}
                    </p>
                  </div>

                  <div className="grid shrink-0 grid-cols-2 gap-2 xl:grid-cols-4">
                    <DetailBox
                      icon={<Wallet size={13} />}
                      title="Budget"
                      value={
                        intent.budget_amount === null
                          ? "Not specified"
                          : `${intent.budget_currency ?? ""} ${intent.budget_amount.toLocaleString("en-IN")}`
                      }
                    />
                    <DetailBox
                      icon={<Clock3 size={13} />}
                      title="Deadline"
                      value={intent.delivery_deadline_text ?? "Not specified"}
                    />
                    <DetailBox
                      icon={<MapPin size={13} />}
                      title="Location"
                      value={intent.delivery_location ?? "Not specified"}
                    />
                    <DetailBox
                      icon={<BrainCircuit size={13} />}
                      title="Language"
                      value={intent.language}
                    />
                  </div>

                  <div className="grid min-w-0 grid-cols-1 content-start gap-3 sm:grid-cols-2">
                    <div className="space-y-4">
                      <SummaryList
                        heading="Mandatory requirements"
                        items={intent.required_specifications}
                        empty="None specified"
                        limit={4}
                      />
                      <SummaryList
                        heading="Preferences"
                        items={intent.preferred_specifications}
                        empty="No optional preferences"
                        limit={2}
                      />
                    </div>
                    <div className="space-y-4">
                      <SummaryList
                        heading="Missing information"
                        items={intent.missing_information}
                        empty="No gaps identified"
                        tone="warning"
                        limit={2}
                      />
                      <SummaryList
                        heading="Clarification questions"
                        items={intent.clarification_questions}
                        empty="No questions needed"
                        limit={2}
                      />
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-[#263247] pt-3">
                    <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                      <BadgeCheck size={14} className="text-emerald-400" />
                      {result.model} ·{" "}
                      {(result.processing_ms / 1000).toFixed(1)}s
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowAll(true)}
                      className="flex items-center gap-1 text-xs font-semibold text-sky-400 hover:text-sky-300"
                    >
                      View full details <ArrowRight size={13} />
                    </button>
                  </div>
                </>
              )}
            </section>
          </div>

          {result && request.trim() === analyzedRequest && (
            <>
              <div id="adaptive-decision" className="min-w-0 scroll-mt-24">
                <AdaptiveDecisionPanel
                  key={analysisId}
                  discovery={discovery}
                  evidenceByPlace={evidenceByPlace}
                  budgetAmount={result.intent.budget_amount}
                  budgetCurrency={result.intent.budget_currency}
                  onDecisionChange={handleDecisionChange}
                  demoLaunchId={demoLaunchId}
                />
              </div>

              <details className="group min-w-0 overflow-hidden rounded-2xl border border-[#30415B] bg-[#101827]">
                <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-sky-400 sm:px-5 [&::-webkit-details-marker]:hidden">
                  <div className="min-w-0">
                    <h2 className="text-sm font-semibold text-slate-100">
                      Merchant evidence & detailed comparison
                    </h2>

                    <p className="mt-1 text-[11px] leading-5 text-slate-400">
                      Explore discovered stores, merchant reports, evidence
                      readiness and raw price previews
                    </p>
                  </div>

                  <span
                    aria-hidden="true"
                    className="shrink-0 text-lg text-sky-400 transition-transform group-open:rotate-180"
                  >
                    ⌄
                  </span>
                </summary>

                <div className="border-t border-slate-800 p-2 sm:p-3">
                  <CustomerDecisionPanel
                    discovery={discovery}
                    evidenceByPlace={evidenceByPlace}
                    budgetAmount={result.intent.budget_amount}
                    budgetCurrency={result.intent.budget_currency}
                    onOpenDiscovery={() => {
                      setLiveMerchantsOpen(true);
                    }}
                  />
                </div>
              </details>
            </>
          )}

          <p className="shrink-0 text-center text-[11px] text-slate-600 lg:hidden">
            NeedProof AI · Evidence-driven commerce intelligence
          </p>
        </div>
      </main>

      {showAll && result && (
        <AllDetails result={result} onClose={() => setShowAll(false)} />
      )}

      {catalogOpen && <CatalogModal onClose={() => setCatalogOpen(false)} />}

      <LiveMerchantsModal
        key={analysisId}
        isOpen={liveMerchantsOpen}
        onClose={() => setLiveMerchantsOpen(false)}
        initialPrefill={
          result && request.trim() === analyzedRequest
            ? makeJourneyPrefill(result.intent)
            : null
        }
        onDiscovery={(snapshot) => {
          if (
            analysisSequence.current !== analysisId ||
            request.trim() !== analyzedRequest
          ) {
            return;
          }

          setDiscovery(snapshot);

          // Preserve matching evidence when the same product
          // and merchant appear in a refreshed discovery search.
          setEvidenceByPlace((previous) => {
            const visiblePlaceIds = new Set(
              snapshot.merchants.map((merchant) => merchant.place_id),
            );

            const activeProduct = snapshot.product_query
              .trim()
              .toLowerCase()
              .replace(/\s+/g, " ");

            return Object.fromEntries(
              Object.entries(previous).filter(([placeId, evidence]) => {
                const evidenceProduct = evidence.product_query
                  .trim()
                  .toLowerCase()
                  .replace(/\s+/g, " ");

                return (
                  visiblePlaceIds.has(placeId) &&
                  evidenceProduct === activeProduct
                );
              }),
            );
          });
        }}
        onEvidence={(snapshot) => {
          if (
            analysisSequence.current !== analysisId ||
            request.trim() !== analyzedRequest
          ) {
            return;
          }

          setEvidenceByPlace((previous) => ({
            ...previous,
            [snapshot.place_id]: snapshot,
          }));
        }}
      />

      {evidenceOpen && (
        <EvidenceIntelligenceModal onClose={() => setEvidenceOpen(false)} />
      )}

      {commerceOpen && (
        <CommerceOptimizerModal onClose={() => setCommerceOpen(false)} />
      )}
      {assuranceOpen && (
        <AssuranceDeskModal onClose={() => setAssuranceOpen(false)} />
      )}
      {merchantPortalOpen && (
        <MerchantOnboardingModal onClose={() => setMerchantPortalOpen(false)} />
      )}
      {transactionOpen && (
        <TransactionSafetyModal onClose={() => setTransactionOpen(false)} />
      )}
      {benchmarkOpen && (
        <BenchmarkDashboardModal onClose={() => setBenchmarkOpen(false)} />
      )}
    </div>
  );
}

