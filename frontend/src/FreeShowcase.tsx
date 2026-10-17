import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  cloudApiUrl,
  getShowcaseGeminiModel,
  requestCloudReplan,
  requestCloudVerificationPlan,
  type CloudReplanInput,
  type CloudVerificationPlan,
} from "./lib/cloudDecisions";
import {
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  FlaskConical,
  MapPin,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Wallet,
} from "lucide-react";
import DecisionSpotlight from "./components/DecisionSpotlight";
import EvidenceWorkbench from "./components/EvidenceWorkbench";
import RealStoresDiscovery from "./components/RealStoresDiscovery";
import MerchantEvidenceDesk from "./components/MerchantEvidenceDesk";
import GroundedProductLab from "./components/GroundedProductLab";
import ProductResearch13C2 from "./components/ProductResearch13C2";
import EvidencePlanner14A1 from "./components/EvidencePlanner14A1";
import BasketOptimizer14A2 from "./components/BasketOptimizer14A2";
import DecisionOrchestrator14A3 from "./components/DecisionOrchestrator14A3";
import RetailForecast14B1 from "./components/RetailForecast14B1";
import RetailInsights14B2 from "./components/RetailInsights14B2";
import InventoryReview14B3 from "./components/InventoryReview14B3";
import BusinessCommandCenter14B4 from "./components/BusinessCommandCenter14B4";
import { biCommandCenter14b4Enabled } from "./lib/biCommandCenter14b4";
import { inventoryReview14b3Enabled } from "./lib/inventoryReview14b3";
import { retailInsights14b2Enabled } from "./lib/retailInsights14b2";
import { retailForecast14b1Enabled } from "./lib/retailForecast14b1";
import { decisionOrchestrator14a3Enabled } from "./lib/decisionOrchestrator14a3";
import { basketOptimizer14a2Enabled } from "./lib/basketOptimizer14a2";
import { evidencePlanner14a1Enabled } from "./lib/evidencePlanner14a1";
import { productRetrieval13c2Enabled } from "./lib/productRetrieval13c2";
import { productGrounding13c1Enabled } from "./lib/productGrounding13c1";
import { evidence13bEnabled } from "./lib/evidence13b";
import {
  deleteJourney,
  loadJourney,
  saveJourney,
  type HistoricalDecision,
  type JourneyEvent,
  type SavedJourney,
} from "./lib/journeyStore";
import type { DecisionResult } from "./components/AdaptiveDecisionPanel";

type ExtractedIntent = {
  requested_product: string;
  budget_amount: number | null;
  delivery_location: string | null;
  required_specifications: string[];
  missing_information: string[];
};

const SAMPLE =
  "I need a genuine 65W USB-C PD laptop charger near Thane " +
  "under ₹1000, available today before 6 PM. " +
  "Please check stock, compatibility and delivery.";

const REFERENCE_PRODUCT = "65W USB-C PD laptop charger";
const REFERENCE_BUDGET = 1000;

function parseIntent(text: string): ExtractedIntent {
  const clean = text
    .trim()
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/, "");
  const raw = JSON.parse(clean) as Record<string, unknown>;
  const stringArray = (input: unknown) =>
    Array.isArray(input)
      ? input.filter((value): value is string => typeof value === "string")
      : [];

  if (
    typeof raw.requested_product !== "string" ||
    !raw.requested_product.trim()
  ) {
    throw new Error("Gemini returned an incomplete product extraction.");
  }

  return {
    requested_product: raw.requested_product.trim(),
    budget_amount:
      typeof raw.budget_amount === "number" &&
      Number.isFinite(raw.budget_amount)
        ? raw.budget_amount
        : null,
    delivery_location:
      typeof raw.delivery_location === "string" ? raw.delivery_location : null,
    required_specifications: stringArray(raw.required_specifications),
    missing_information: stringArray(raw.missing_information),
  };
}

function formatINR(amount: number | null) {
  return amount === null
    ? "Not specified"
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
      }).format(amount);
}

function MiniDetail({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: ReactNode;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-[#263247] bg-[#080D17] p-3">
      <p className="flex items-center gap-2 text-[11px] text-slate-400">
        {icon} {label}
      </p>
      <p className="mt-1 break-words text-sm font-semibold text-white">
        {value}
      </p>
    </div>
  );
}

export default function FreeShowcase() {
  const [request, setRequest] = useState(SAMPLE);
  const [intent, setIntent] = useState<ExtractedIntent | null>(null);
  const [analyzedRequest, setAnalyzedRequest] = useState("");
  const [loading, setLoading] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [stockOut, setStockOut] = useState(false);
  const [demoStarted, setDemoStarted] = useState(false);
  // Keep reference scenario independent until the user opts into a
  // personalized, explicitly fictional scenario based on Gemini's extraction.
  const [demoSource, setDemoSource] = useState<"reference" | "customer">(
    "reference",
  );
  const sequence = useRef(0);
  const remoteEnabled = cloudApiUrl.length > 0;
  const [remoteDecision, setRemoteDecision] = useState<DecisionResult | null>(
    null,
  );
  const [remoteSnapshotKey, setRemoteSnapshotKey] = useState("");
  const [remotePending, setRemotePending] = useState(false);
  const [remoteError, setRemoteError] = useState("");
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState("");
  const [plan, setPlan] = useState<CloudVerificationPlan | null>(null);
  const [journeyEvents, setJourneyEvents] = useState<JourneyEvent[]>([]);
  const [savedDecision, setSavedDecision] = useState<HistoricalDecision | null>(
    null,
  );
  const [savedAt, setSavedAt] = useState("");
  const [storeBusy, setStoreBusy] = useState(false);
  const [storeStatus, setStoreStatus] = useState("Checking saved journey...");
  const [storeError, setStoreError] = useState("");
  const userTouched = useRef(false);

  const recordEvent = useCallback(
    (kind: string, message: string, source: JourneyEvent["source"]) => {
      const item: JourneyEvent = {
        id: crypto.randomUUID(),
        at: new Date().toISOString(),
        kind,
        message: message.slice(0, 180),
        source,
      };
      setJourneyEvents((previous) => [...previous, item].slice(-30));
    },
    [],
  );

  function restoreSnapshot(saved: SavedJourney) {
    ++sequence.current; // Invalidate any older in-flight Gemini request.
    setRequest(saved.requestText);
    setAnalyzedRequest(saved.analyzedRequest);
    setIntent(saved.intent);
    setDemoStarted(saved.scenario.demoStarted);
    setDemoSource(saved.scenario.demoSource);
    setStockOut(saved.scenario.stockOut);
    setQuantity(saved.scenario.quantity);
    setLoading(false);
    setError("");
    setPlan(null);
    setPlanError("");
    setJourneyEvents(saved.events);
    setSavedDecision(saved.lastDecision);
    setSavedAt(saved.savedAt ?? "");
    // Active cloud decisions are deliberately not restored. The existing
    // effect reevaluates the saved scenario using Cloud Run.
    setRemoteDecision(null);
    setRemoteSnapshotKey("");
    setStoreError("");
    setStoreStatus("Saved journey restored; decisions are being refreshed.");
  }

  // A previously saved journey is restored automatically in the same browser
  // identity. Never overwrite a request the user started editing while loading.
  useEffect(() => {
    let alive = true;
    loadJourney()
      .then((saved) => {
        if (!alive) return;
        if (saved && !userTouched.current) restoreSnapshot(saved);
        else
          setStoreStatus(
            saved
              ? "Saved journey available; use Restore."
              : "No saved journey yet.",
          );
      })
      .catch((reason: unknown) => {
        if (!alive) return;
        setStoreStatus(
          "Firestore unavailable; Gemini and decision demo remain usable.",
        );
        setStoreError(
          reason instanceof Error
            ? reason.message
            : "Could not load saved journey.",
        );
      });
    return () => {
      alive = false;
    };
    // Only check once; restoreSnapshot is intentionally a local operation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loading) return;
    setSeconds(0);
    const started = Date.now();
    const timer = window.setInterval(
      () => setSeconds(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [loading]);

  const isCurrent = intent !== null && request.trim() === analyzedRequest;

  // Fictional merchant offers only. Price ratios are deliberately synthetic,
  // never inferred from Gemini as real-world shop prices.
  const usingCustomerScenario =
    demoSource === "customer" && isCurrent && intent !== null;
  const extractedBudget =
    usingCustomerScenario &&
    intent.budget_amount !== null &&
    Number.isFinite(intent.budget_amount) &&
    intent.budget_amount > 0
      ? intent.budget_amount
      : null;
  const scenarioBudget = usingCustomerScenario
    ? (extractedBudget ?? REFERENCE_BUDGET)
    : REFERENCE_BUDGET;
  const scenarioProduct = usingCustomerScenario
    ? intent.requested_product
    : REFERENCE_PRODUCT;
  const scenarioPriceA = Math.max(1, Math.round(scenarioBudget * 0.899));
  const scenarioPriceB = Math.max(1, Math.round(scenarioBudget * 0.95));

  const candidates = useMemo(() => {
    const source = [
      {
        place_id: "TEST_STORE_A",
        price: scenarioPriceA,
        stock: stockOut ? 0 : 3,
      },
      { place_id: "TEST_STORE_B", price: scenarioPriceB, stock: 5 },
    ];
    return source.map((merchant) => {
      const subtotal = merchant.price * quantity;
      const reasons: string[] = [];
      if (merchant.stock < quantity)
        reasons.push("REPORTED_STOCK_INSUFFICIENT");
      if (subtotal > scenarioBudget) reasons.push("BUDGET_EXCEEDED");
      return {
        place_id: merchant.place_id,
        name: merchant.place_id,
        price: merchant.price,
        stock: merchant.stock,
        status: reasons.length ? "EXCLUDED" : "PROVISIONAL",
        reported_subtotal_minor: subtotal * 100,
        reasons,
        evidence_gaps: ["MERCHANT_IDENTITY_NOT_VERIFIED"],
      };
    });
  }, [quantity, stockOut, scenarioBudget, scenarioPriceA, scenarioPriceB]);

  const snapshotKey = JSON.stringify([
    scenarioProduct,
    scenarioBudget,
    scenarioPriceA,
    scenarioPriceB,
    quantity,
    stockOut,
  ]);
  const confirmedRemoteDecision =
    demoStarted && remoteSnapshotKey === snapshotKey ? remoteDecision : null;

  // When configured, server decisions are mandatory: never quietly substitute
  // browser decisions when Cloud Run or Firebase authentication fails.
  useEffect(() => {
    if (!remoteEnabled || !demoStarted) {
      setRemoteDecision(null);
      setRemotePending(false);
      setRemoteError("");
      return;
    }
    const controller = new AbortController();
    const timestamp = new Date().toISOString();
    const offer = (
      placeId: string,
      price: number,
      stock: number,
    ): CloudReplanInput["merchants"][number] => ({
      place_id: placeId,
      name: placeId,
      evidence: {
        product_query: scenarioProduct,
        status: "REPORTED_UNVERIFIED",
        submission: {
          product_name: scenarioProduct,
          stock_quantity: stock,
          price_minor: price * 100,
          currency: "INR",
          delivery_available: true,
          submitted_at: timestamp,
        },
        assessment: {
          status: "REPORTED_UNVERIFIED",
          freshness: "RECENT_REPORT",
          eligible_for_commitment: false,
        },
      },
    });
    const payload: CloudReplanInput = {
      customer: {
        product_query: scenarioProduct,
        budget_minor: Math.round(scenarioBudget * 100),
        required_quantity: quantity,
        delivery_required: true,
      },
      merchants: [
        offer("TEST_STORE_A", scenarioPriceA, stockOut ? 0 : 3),
        offer("TEST_STORE_B", scenarioPriceB, 5),
      ],
    };
    setRemoteDecision(null);
    setRemoteSnapshotKey("");
    setRemotePending(true);
    setRemoteError("");
    requestCloudReplan(payload, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setRemoteSnapshotKey(snapshotKey);
          setRemoteDecision(result);
          recordEvent(
            "DECISION_EVALUATED",
            `Backend decision: ${result.selected?.name ?? "no eligible offer"}. Next action: ${result.recommended_next_action}.`,
            "CLOUD_RUN",
          );
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setRemoteError(
            reason instanceof Error
              ? reason.message
              : "Cloud decision request failed.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setRemotePending(false);
      });
    return () => controller.abort();
  }, [
    demoStarted,
    quantity,
    remoteEnabled,
    recordEvent,
    scenarioBudget,
    scenarioPriceA,
    scenarioPriceB,
    scenarioProduct,
    snapshotKey,
    stockOut,
  ]);

  const selected =
    candidates
      .filter((merchant) => merchant.status === "PROVISIONAL")
      .sort(
        (a, b) => a.reported_subtotal_minor - b.reported_subtotal_minor,
      )[0] ?? null;

  // This typed object is strictly a browser-only fictional snapshot.
  // It never contains a real Google Places merchant or submitted evidence.
  const simulatedDecision: DecisionResult | null =
    demoStarted && isCurrent
      ? {
          mode: "CLIENT_SNAPSHOT_REPLANNING",
          decision_status: selected
            ? "PROVISIONAL_OFFER"
            : "NO_PROVISIONAL_OFFER",
          selected,
          candidates,
          evaluated_at: new Date().toISOString(),
          recommended_next_action: selected
            ? "VERIFY_IDENTITY_COMPATIBILITY_AND_DELIVERY"
            : "FIND_OR_REFRESH_ALTERNATIVE_OFFERS",
          purchase_allowed: false,
          notice:
            "Fictional browser-only simulation. Not authorized for purchase.",
        }
      : null;

  const activeDecision: DecisionResult | null = remoteEnabled
    ? confirmedRemoteDecision
    : simulatedDecision;
  const activeSelected = remoteEnabled
    ? (confirmedRemoteDecision?.selected ?? null)
    : selected;
  const displayedCandidates = remoteEnabled
    ? (confirmedRemoteDecision?.candidates ?? []).map((candidate) => ({
        ...candidate,
        price:
          candidate.place_id === "TEST_STORE_A"
            ? scenarioPriceA
            : scenarioPriceB,
        stock: candidate.place_id === "TEST_STORE_A" ? (stockOut ? 0 : 3) : 5,
      }))
    : candidates;

  function startDemo(mode: "reference" | "customer") {
    if (mode === "customer" && !isCurrent) return;
    userTouched.current = true;
    recordEvent(
      "DEMO_STARTED",
      `Started ${mode} scenario with fictional offers.`,
      "USER",
    );
    setPlan(null);
    setPlanError("");
    setDemoSource(mode);
    setDemoStarted(true);
    setStockOut(false);
    setQuantity(1);
    document.getElementById("adaptive-demo")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  function resetDemo() {
    startDemo("reference");
  }

  async function runVerificationPlan() {
    if (!remoteEnabled || planLoading) return;
    setPlanLoading(true);
    setPlan(null);
    setPlanError("");
    try {
      const response = await requestCloudVerificationPlan(scenarioBudget);
      setPlan(response);
      recordEvent(
        "VERIFICATION_PLANNED",
        `Synthetic EVSI recommended: ${response.recommended_action_id ?? response.stopping_reason ?? "none"}.`,
        "CLOUD_RUN",
      );
    } catch (reason) {
      setPlanError(
        reason instanceof Error
          ? reason.message
          : "Verification planning unavailable.",
      );
    } finally {
      setPlanLoading(false);
    }
  }

  async function analyze() {
    const submittedText = request.trim();
    if (submittedText.length < 8 || loading) return;
    userTouched.current = true;
    const current = ++sequence.current;
    setLoading(true);
    setError("");
    setIntent(null);
    setAnalyzedRequest("");
    setDemoStarted(false);
    setDemoSource("reference");
    setStockOut(false);

    try {
      const prompt = `
You are an AI assistant interpreting a retail customer's shopping requirements.
Extract the request without inventing stock, stores, prices, merchant verification,
or delivery commitments.
Return ONLY a JSON object with this schema:
{
  "requested_product": "string",
  "budget_amount": null,
  "delivery_location": null,
  "required_specifications": [],
  "missing_information": []
}
budget_amount is a number in INR when an INR budget is provided, otherwise null.
delivery_location is a string or null.
Customer request: ${JSON.stringify(submittedText)}
`;
      const response = await getShowcaseGeminiModel().generateContent(prompt);
      const extracted = parseIntent(response.response.text());
      if (sequence.current !== current) return;
      setIntent(extracted);
      setAnalyzedRequest(submittedText);
      recordEvent(
        "INTENT_EXTRACTED",
        `Gemini extracted: ${extracted.requested_product}.`,
        "GEMINI",
      );
    } catch (err) {
      if (sequence.current !== current) return;
      setError(
        err instanceof Error ? err.message : "Gemini extraction failed.",
      );
    } finally {
      if (sequence.current === current) setLoading(false);
    }
  }

  function resetRequest() {
    userTouched.current = true;
    ++sequence.current;
    setRequest("");
    setIntent(null);
    setAnalyzedRequest("");
    setLoading(false);
    setError("");
    setDemoStarted(false);
    setDemoSource("reference");
    setStockOut(false);
    setQuantity(1);
    setJourneyEvents([]);
    setSavedDecision(null);
    setStoreStatus(
      "New unsaved journey. Previous saved data remains until replaced or removed.",
    );
  }

  async function saveCurrentJourney() {
    if (storeBusy) return;
    userTouched.current = true;
    setStoreBusy(true);
    setStoreError("");
    setStoreStatus("Saving to Firestore...");
    const decision: HistoricalDecision | null = activeDecision
      ? {
          source: remoteEnabled ? "CLOUD_RUN" : "BROWSER_FIXTURE",
          selectedId: activeDecision.selected?.place_id ?? null,
          status: activeDecision.decision_status,
          nextAction: activeDecision.recommended_next_action,
          evaluatedAt: activeDecision.evaluated_at,
        }
      : null;
    const snapshot: SavedJourney = {
      requestText: request,
      analyzedRequest,
      intent,
      scenario: { demoStarted, demoSource, quantity, stockOut },
      lastDecision: decision,
      events: journeyEvents,
    };
    try {
      await saveJourney(snapshot);
      setSavedDecision(decision);
      const at = new Date().toISOString();
      setSavedAt(at);
      setStoreStatus("Saved to Firestore. Reload this page to test restore.");
    } catch (reason) {
      setStoreStatus(
        "Save failed; your current browser state is still available.",
      );
      setStoreError(
        reason instanceof Error ? reason.message : "Firestore save failed.",
      );
    } finally {
      setStoreBusy(false);
    }
  }

  async function restoreSavedJourney() {
    if (storeBusy) return;
    setStoreBusy(true);
    setStoreError("");
    try {
      const saved = await loadJourney();
      if (saved) restoreSnapshot(saved);
      else setStoreStatus("No saved Firestore journey found.");
    } catch (reason) {
      setStoreStatus("Restore failed.");
      setStoreError(
        reason instanceof Error ? reason.message : "Firestore load failed.",
      );
    } finally {
      setStoreBusy(false);
    }
  }

  async function removeSavedJourney() {
    if (
      storeBusy ||
      !window.confirm("Remove your saved NeedProof journey from Firestore?")
    )
      return;
    setStoreBusy(true);
    setStoreError("");
    try {
      await deleteJourney();
      setSavedAt("");
      setSavedDecision(null);
      setStoreStatus(
        "Saved Firestore journey deleted. Current unsaved view remains on screen.",
      );
    } catch (reason) {
      setStoreStatus("Could not remove saved journey.");
      setStoreError(
        reason instanceof Error ? reason.message : "Firestore delete failed.",
      );
    } finally {
      setStoreBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-[#080B12] text-slate-100 lg:flex">
      <aside className="hidden w-[240px] shrink-0 flex-col border-r border-[#263247] bg-[#0D121C] px-4 py-6 lg:sticky lg:top-0 lg:flex lg:h-dvh">
        <div className="flex items-center gap-3 px-2">
          <span className="rounded-xl bg-sky-500/10 p-2 text-sky-400">
            <ShieldCheck size={22} />
          </span>
          <div>
            <h1 className="text-base font-bold">
              NeedProof <span className="text-sky-400">AI</span>
            </h1>
            <p className="text-[10px] tracking-wider text-slate-500">
              COMMERCE INTELLIGENCE
            </p>
          </div>
        </div>
        <p className="mb-3 mt-9 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Workspace
        </p>
        <nav aria-label="Showcase workspace" className="space-y-2">
          <a href="#real-store-discovery" className="block rounded-lg border border-sky-500/20 bg-sky-500/5 px-3 py-3 text-xs text-sky-300">Discover Real Stores</a>
          {evidence13bEnabled && <a href="#merchant-evidence-desk" className="block rounded-lg border border-sky-500/20 px-3 py-3 text-xs text-sky-300">Merchant Desk</a>}
          <a href="#evidence-workbench" className="flex items-center rounded-lg border border-sky-500/25 bg-sky-500/5 px-3 py-3 text-xs text-sky-200 hover:bg-sky-500/10">Evidence Intelligence</a>
          <a
            href="#customer-request"
            className="flex items-center gap-2 rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-3 text-xs font-semibold text-sky-300"
          >
            <BrainCircuit size={15} /> Demand Studio
          </a>
          <a
            href="#adaptive-demo"
            className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-3 text-xs text-slate-300 hover:bg-slate-800"
          >
            <FlaskConical size={15} /> Scenario Lab
          </a>
          <a
            href="#journey-history"
            className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-3 text-xs text-slate-300 hover:bg-slate-800"
          >
            <Clock3 size={15} /> Saved Journey
          </a>
        </nav>
        <div className="mt-7 border-t border-slate-800 pt-5">
          <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Local full-stack modules
          </p>
          <p className="mt-2 px-3 text-xs leading-7 text-slate-500">
            Real store discovery
            <br />
            Merchant evidence
            <br />
            Commerce optimizer
            <br />
            Merchant portal
            <br />
            Assurance desk
          </p>
          <p className="mt-2 px-3 text-[11px] leading-5 text-amber-200/75">
            Merchant operations still require the local FastAPI backend; the
            isolated decision API runs on Cloud Run when enabled.
          </p>
        </div>
        <div className="mt-auto rounded-xl border border-[#273449] bg-[#101829] p-3">
          <p className="flex items-center gap-2 text-xs font-semibold text-sky-300">
            <Sparkles size={14} /> Firebase Spark Showcase
          </p>
          <p className="mt-2 text-[11px] leading-5 text-slate-400">
            Live Gemini · Cloud Run decision engine when configured · Synthetic
            merchant evidence
          </p>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex min-h-14 items-center justify-between gap-3 border-b border-[#263247] bg-[#080B12]/95 px-4 backdrop-blur-lg sm:px-6">
          <div>
            <p className="text-[10px] text-slate-500">
              NeedProof / Customer Intelligence
            </p>
            <p className="text-sm font-semibold">Demand Studio</p>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 px-3 py-1.5 text-[11px] text-emerald-300">
            <CheckCircle2 size={13} /> Firebase showcase
          </span>
        </header>

        <div className="mx-auto flex max-w-[1380px] flex-col gap-5 px-4 py-5 sm:px-6">
          <nav
            aria-label="Mobile showcase navigation"
            className="flex gap-2 lg:hidden"
          >
            <a href="#real-store-discovery" className="shrink-0 rounded-lg border border-sky-500/25 px-3 py-2 text-xs text-sky-200">Real Stores</a>
            {evidence13bEnabled && <a href="#merchant-evidence-desk" className="shrink-0 rounded-lg border border-sky-500/25 px-3 py-2 text-xs text-sky-200">Merchant Desk</a>}
            <a href="#evidence-workbench" className="shrink-0 rounded-lg border border-sky-500/30 bg-sky-500/5 px-3 py-2 text-xs text-sky-200">Evidence Lab</a>
            <a
              className="rounded-lg bg-sky-500/10 px-3 py-2 text-xs text-sky-300"
              href="#customer-request"
            >
              Demand Studio
            </a>
            <a
              className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300"
              href="#adaptive-demo"
            >
              Scenario Lab
            </a>
            <a
              className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300"
              href="#journey-history"
            >
              Saved Journey
            </a>
          </nav>
          <div>
            <p className="mb-2 inline-flex items-center gap-2 rounded-full border border-sky-500/25 bg-sky-500/10 px-3 py-1 text-[11px] text-sky-300">
              <Sparkles size={13} /> Gemini via Firebase AI Logic
            </p>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              Understand the need.{" "}
              <span className="text-sky-400">Before the decision.</span>
            </h1>
            <p className="mt-2 text-sm text-slate-400">
              Live customer-intent intelligence with a separate, fictional
              merchant decision scenario.
            </p>
          </div>

          <DecisionSpotlight
            hasIntent={intent !== null}
            isCurrent={isCurrent}
            discovery={null}
            evidenceByPlace={{}}
            decision={activeDecision}
            decisionMode="fictional"
            showcaseMode
            showcaseDemoStarted={demoStarted}
            showcaseDemoReplanned={
              demoStarted &&
              stockOut &&
              (!remoteEnabled || confirmedRemoteDecision !== null)
            }
            onStart={() => document.getElementById("customer-request")?.focus()}
            onDiscover={resetDemo}
            onReviewDecision={() =>
              document
                .getElementById("adaptive-demo")
                ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }
            onLaunchDemo={resetDemo}
          />

          <section
            id="journey-history"
            className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#101A2A] p-4 sm:p-5"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="flex items-center gap-2 text-sm font-semibold">
                  <Clock3 size={16} className="text-sky-400" /> Firestore
                  Journey History
                </h2>
                <p className="mt-1 text-xs leading-5 text-slate-400">
                  Private to this browser's Firebase anonymous account. Save
                  only when you choose; no writing on every keystroke.
                </p>
                <p className="mt-2 text-[11px] text-sky-300" aria-live="polite">
                  {storeStatus}
                </p>
                {storeError && (
                  <p
                    role="alert"
                    className="mt-1 max-w-2xl break-words text-xs text-rose-300"
                  >
                    {storeError}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={storeBusy}
                  onClick={() => void saveCurrentJourney()}
                  className="rounded-lg bg-sky-500 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50"
                >
                  {storeBusy ? "Working..." : "Save journey"}
                </button>
                <button
                  type="button"
                  disabled={storeBusy}
                  onClick={() => void restoreSavedJourney()}
                  className="rounded-lg border border-slate-600 px-3 py-2 text-xs text-slate-200 disabled:opacity-50"
                >
                  Restore saved
                </button>
                <button
                  type="button"
                  disabled={storeBusy}
                  onClick={() => void removeSavedJourney()}
                  className="rounded-lg border border-rose-500/25 px-3 py-2 text-xs text-rose-200 disabled:opacity-50"
                >
                  Delete saved
                </button>
              </div>
            </div>
            <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
              <div className="rounded-xl border border-slate-700/70 bg-[#080D17] p-3">
                <p className="text-xs font-semibold">
                  Event timeline{" "}
                  <span className="font-normal text-slate-500">
                    · {journeyEvents.length} captured locally
                  </span>
                </p>
                {journeyEvents.length === 0 ? (
                  <p className="mt-2 text-xs text-slate-500">
                    Extract with Gemini or start a demo; then Save journey to
                    preserve the events in Firestore.
                  </p>
                ) : (
                  <ol className="mt-3 max-h-48 space-y-2 overflow-y-auto pr-2">
                    {[...journeyEvents].reverse().map((event) => (
                      <li
                        key={event.id}
                        className="rounded-lg border border-slate-800 px-3 py-2"
                      >
                        <div className="flex flex-wrap justify-between gap-2 text-[10px] text-slate-500">
                          <span>
                            {event.kind.replaceAll("_", " ")} · {event.source}
                          </span>
                          <time dateTime={event.at}>
                            {new Date(event.at).toLocaleTimeString()}
                          </time>
                        </div>
                        <p className="mt-1 break-words text-xs text-slate-200">
                          {event.message}
                        </p>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
              <div className="rounded-xl border border-slate-700/70 bg-[#080D17] p-3">
                <p className="text-xs font-semibold">
                  Last stored decision{" "}
                  <span className="font-normal text-amber-200">
                    · historical only
                  </span>
                </p>
                {savedDecision ? (
                  <div className="mt-2 space-y-1 text-xs leading-5 text-slate-300">
                    <p>Source: {savedDecision.source}</p>
                    <p>Saved leader: {savedDecision.selectedId ?? "none"}</p>
                    <p>Status: {savedDecision.status}</p>
                    <p className="break-words">
                      Next action: {savedDecision.nextAction}
                    </p>
                    <p className="text-slate-500">
                      Evaluated: {savedDecision.evaluatedAt}
                    </p>
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-slate-500">
                    No historical decision saved yet.
                  </p>
                )}
                {savedAt && (
                  <p className="mt-3 text-[11px] text-slate-500">
                    Saved at {new Date(savedAt).toLocaleString()}
                  </p>
                )}
                <p className="mt-3 text-[11px] leading-5 text-amber-200/85">
                  Restoring a saved scenario triggers fresh Cloud Run evaluation
                  when configured. Firestore does not verify merchants or
                  prices. Anonymous accounts may be lost if browser storage is
                  cleared or another device is used.
                </p>
              </div>
            </div>
          </section>

          <div className="grid min-w-0 items-stretch gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <section className="min-w-0 rounded-2xl border border-[#273449] bg-[#111827] p-4 sm:p-5">
              <div className="mb-4 flex items-center gap-3">
                <span className="rounded-lg bg-sky-500/10 p-2 text-sky-400">
                  <ShoppingBag size={18} />
                </span>
                <div>
                  <h2 className="text-sm font-semibold">Customer request</h2>
                  <p className="text-[11px] text-slate-500">
                    Live Gemini interpretation · No fabricated merchant facts
                  </p>
                </div>
              </div>
              <label
                htmlFor="customer-request"
                className="mb-2 block text-xs text-slate-300"
              >
                What does the customer need?
              </label>
              <textarea
                id="customer-request"
                value={request}
                onChange={(event) => {
                  userTouched.current = true;
                  setRequest(event.target.value);
                  setDemoStarted(false);
                  setPlan(null);
                }}
                maxLength={2000}
                rows={5}
                className="min-h-36 w-full resize-y rounded-xl border border-[#31425B] bg-[#080D17] p-3.5 text-sm leading-6 text-white outline-none focus:border-sky-500"
              />
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      userTouched.current = true;
                      setRequest(SAMPLE);
                    }}
                    className="rounded-lg border border-slate-700 px-3 py-2 text-xs hover:bg-slate-800"
                  >
                    Load sample
                  </button>
                  <button
                    type="button"
                    onClick={resetRequest}
                    className="rounded-lg border border-slate-700 px-3 py-2 text-xs hover:bg-slate-800"
                  >
                    Clear
                  </button>
                </div>
                <span className="text-[11px] text-slate-500">
                  {request.length}/2000
                </span>
              </div>
              <button
                type="button"
                disabled={loading || request.trim().length < 8}
                onClick={() => void analyze()}
                className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-sky-500 px-4 py-3 text-sm font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-50"
              >
                {loading ? (
                  <RefreshCw size={17} className="animate-spin" />
                ) : (
                  <BrainCircuit size={17} />
                )}
                {loading
                  ? "Extracting customer intelligence..."
                  : "Extract with live Gemini"}
                {!loading && <ArrowRight size={15} />}
              </button>
              {loading && (
                <div
                  role="status"
                  aria-live="polite"
                  className="mt-3 rounded-lg border border-sky-500/20 bg-sky-500/5 p-3 text-xs leading-5 text-sky-200"
                >
                  <p className="flex items-center gap-2">
                    <Clock3 size={14} /> Gemini request running · {seconds}s
                    elapsed
                  </p>
                  <p className="mt-1 text-slate-400">
                    {seconds < 10
                      ? "Understanding the product, budget and requirements..."
                      : "Still waiting for the AI service. The free tier can respond slowly; please keep this tab open."}
                  </p>
                </div>
              )}
              {error && (
                <p
                  role="alert"
                  className="mt-3 break-words rounded-lg border border-rose-500/25 bg-rose-500/10 p-3 text-xs leading-5 text-rose-300"
                >
                  {error}
                </p>
              )}
              <p className="mt-4 border-t border-slate-800 pt-3 text-[11px] leading-5 text-slate-500">
                This request is analyzed by Gemini. Merchant inventory,
                authenticity, delivery and prices are not checked by the AI
                extraction.
              </p>
            </section>

            <section
              className="min-w-0 rounded-2xl border border-[#273449] bg-[#111827] p-4 sm:p-5"
              aria-label="Gemini extraction results"
            >
              <div className="mb-4 flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold">Extracted intent</h2>
                <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1 text-[11px] text-amber-200">
                  AI-extracted · Unverified
                </span>
              </div>
              {!isCurrent || !intent ? (
                <div className="flex min-h-64 flex-col items-center justify-center text-center">
                  <BrainCircuit size={38} className="text-slate-600" />
                  <h3 className="mt-4 text-sm font-semibold">
                    {loading
                      ? "Awaiting Gemini..."
                      : "Awaiting customer intelligence"}
                  </h3>
                  <p className="mt-2 max-w-xs text-xs leading-5 text-slate-500">
                    Submit the request to see structured requirements and
                    missing information.
                  </p>
                </div>
              ) : (
                <div className="space-y-4" aria-live="polite">
                  <div className="rounded-xl border border-slate-700 bg-[#080D17] p-3">
                    <p className="text-[11px] text-slate-500">
                      Requested product
                    </p>
                    <p className="mt-1 break-words text-sm font-semibold">
                      {intent.requested_product}
                    </p>
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <MiniDetail
                      label="Budget"
                      value={formatINR(intent.budget_amount)}
                      icon={<Wallet size={13} />}
                    />
                    <MiniDetail
                      label="Location"
                      value={intent.delivery_location ?? "Not specified"}
                      icon={<MapPin size={13} />}
                    />
                  </div>
                  <div>
                    <p className="text-xs font-semibold">
                      Mandatory requirements
                    </p>
                    {intent.required_specifications.length ? (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {intent.required_specifications.map((item, index) => (
                          <span
                            className="max-w-full break-words rounded-lg border border-slate-700 bg-[#080D17] px-3 py-2 text-xs"
                            key={`${item}-${index}`}
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-2 text-xs text-slate-500">
                        No mandatory specifications extracted.
                      </p>
                    )}
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-amber-200">
                      Missing information
                    </p>
                    {intent.missing_information.length ? (
                      <ul className="mt-2 space-y-1.5">
                        {intent.missing_information.map((item, index) => (
                          <li
                            key={`${item}-${index}`}
                            className="rounded-lg border border-amber-500/15 bg-amber-500/5 px-3 py-2 text-xs text-amber-100/85"
                          >
                            {item}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-xs text-slate-500">
                        No gaps identified by the extraction.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </section>
          </div>

          <RealStoresDiscovery
            requestedProduct={isCurrent && intent ? intent.requested_product : null}
            location={isCurrent && intent ? intent.delivery_location : null}
            onEvent={recordEvent}
          />


          {productGrounding13c1Enabled && (
            <GroundedProductLab
              requestedProduct={isCurrent && intent ? intent.requested_product : null}
              onEvent={recordEvent}
            />
          )}

          {productRetrieval13c2Enabled && (
            <ProductResearch13C2
              requestedProduct={isCurrent && intent ? intent.requested_product : null}
              onEvent={recordEvent}
            />
          )}

          {evidencePlanner14a1Enabled && (
            <EvidencePlanner14A1
              requestedProduct={isCurrent && intent ? intent.requested_product : null}
              extractedBudget={isCurrent && intent ? intent.budget_amount : null}
              onEvent={recordEvent}
            />
          )}

          {basketOptimizer14a2Enabled && (
            <BasketOptimizer14A2 onEvent={recordEvent} />
          )}

          {decisionOrchestrator14a3Enabled && (
            <DecisionOrchestrator14A3
              requestedProduct={isCurrent && intent ? intent.requested_product : null}
              extractedBudget={isCurrent && intent ? intent.budget_amount : null}
              onEvent={recordEvent}
            />
          )}

          {retailForecast14b1Enabled && (
            <RetailForecast14B1 onEvent={recordEvent} />
          )}

          {retailInsights14b2Enabled && (
            <RetailInsights14B2 onEvent={recordEvent} />
          )}

          {inventoryReview14b3Enabled && (
            <InventoryReview14B3 onEvent={recordEvent} />
          )}

          {biCommandCenter14b4Enabled && (
            <BusinessCommandCenter14B4 onEvent={recordEvent} />
          )}

          <MerchantEvidenceDesk />

<EvidenceWorkbench
            requestedProduct={isCurrent && intent ? intent.requested_product : null}
            extractedBudget={isCurrent && intent ? intent.budget_amount : null}
            onEvent={recordEvent}
          />

          <section
            id="adaptive-demo"
            className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#111827] p-4 sm:p-5"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <FlaskConical size={19} className="text-sky-400" />
                  <h2 className="text-sm font-semibold">
                    Adaptive Decision Intelligence
                  </h2>
                </div>
                <p className="mt-2 text-xs text-slate-400">
                  {usingCustomerScenario
                    ? `Personalized fictional scenario: ${scenarioProduct}, invented budget ${formatINR(scenarioBudget)}.`
                    : `Independent reference scenario: ${REFERENCE_PRODUCT}, fictional ₹1,000 budget.`}
                </p>
              </div>
              <span className="rounded-full border border-amber-500/30 px-3 py-1.5 text-[11px] font-semibold text-amber-200">
                FICTIONAL MERCHANTS
              </span>
            </div>
            <p className="mt-3 max-w-3xl text-xs leading-5 text-amber-100/80">
              {usingCustomerScenario
                ? "This scenario uses only the Gemini-extracted product name and budget to create clearly invented test offers. No store search, market-price lookup, or merchant verification occurs."
                : "This reference example is independent of the customer's Gemini request. Both stores, their prices and inventory are invented."}{" "}
              No actual store is contacted and no purchase is authorized.
            </p>
            <div className="mt-4 rounded-xl border border-slate-700 bg-[#0A101B] p-3">
              <p className="text-xs font-semibold text-slate-200">
                Choose a fictional test scenario
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => startDemo("reference")}
                  className="min-h-10 rounded-lg border border-sky-500/30 px-3 py-2 text-xs font-semibold text-sky-300 hover:bg-sky-500/10"
                >
                  65W charger reference example
                </button>
                <button
                  type="button"
                  disabled={!isCurrent}
                  onClick={() => startDemo("customer")}
                  className="min-h-10 rounded-lg border border-amber-500/30 px-3 py-2 text-xs font-semibold text-amber-200 hover:bg-amber-500/10 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Use Gemini request (synthetic offers)
                </button>
              </div>
              {!isCurrent && (
                <p className="mt-2 text-[11px] text-slate-500">
                  Extract a customer request with live Gemini to enable
                  personalized fictional offers.
                </p>
              )}
              {usingCustomerScenario && (
                <p className="mt-2 text-[11px] text-amber-200">
                  Test-only prices: Store A = 89.9% of demo budget, Store B =
                  95%.{" "}
                  {extractedBudget === null
                    ? "No positive INR budget was extracted, so the test uses a ₹1,000 fictional fallback."
                    : "No real-world prices are used."}
                </p>
              )}
            </div>
            <div className="mt-4 flex flex-wrap items-end gap-3">
              <button
                type="button"
                onClick={resetDemo}
                className="min-h-11 rounded-lg border border-sky-500/30 px-4 py-2.5 text-xs font-semibold text-sky-300 hover:bg-sky-500/10"
              >
                Run / reset fictional example
              </button>
              <label className="text-xs text-slate-300">
                Quantity
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={quantity}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    if (Number.isInteger(value)) {
                      const next = Math.max(1, Math.min(20, value));
                      userTouched.current = true;
                      setQuantity(next);
                      recordEvent(
                        "QUANTITY_CHANGED",
                        `Scenario quantity changed to ${next}.`,
                        "USER",
                      );
                    }
                  }}
                  className="mt-1 block w-24 rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
                />
              </label>
              <button
                type="button"
                disabled={!demoStarted || stockOut}
                onClick={() => {
                  userTouched.current = true;
                  setStockOut(true);
                  recordEvent(
                    "STOCK_CHANGED",
                    "Synthetic Store A stock set to zero.",
                    "BROWSER_FIXTURE",
                  );
                }}
                className="min-h-11 rounded-lg bg-amber-500 px-4 py-2.5 text-xs font-semibold text-slate-950 disabled:opacity-40"
              >
                Simulate Store A stock-out
              </button>
            </div>
            <div className="mt-3 text-xs" aria-live="polite">
              {remoteEnabled ? (
                <span className="text-sky-300">
                  Decision source: FastAPI on Cloud Run · validated Firebase
                  session · synthetic merchant snapshot
                </span>
              ) : (
                <span className="text-amber-200">
                  Decision source: browser-only fiction (Cloud Run API not
                  configured)
                </span>
              )}
              {remotePending && (
                <p className="mt-2 text-sky-200">
                  Recalculating on Cloud Run...
                </p>
              )}
              {remoteError && (
                <p role="alert" className="mt-2 text-rose-300">
                  Cloud decision unavailable: {remoteError}. No browser fallback
                  was used.
                </p>
              )}
            </div>
            {!demoStarted ? (
              <p className="mt-5 rounded-xl border border-slate-800 bg-[#080D17] p-4 text-sm text-slate-400">
                Launch the fictional example to compare two reported offers and
                see how stock-out changes the provisional leader.
              </p>
            ) : remoteEnabled && !confirmedRemoteDecision ? (
              <p className="mt-5 rounded-xl border border-slate-800 bg-[#080D17] p-4 text-sm text-slate-300">
                {remotePending
                  ? "Waiting for secured Cloud Run evaluation..."
                  : "Decision unavailable. Check authentication and Cloud Run status."}
              </p>
            ) : (
              <div
                className="mt-5 grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)]"
                aria-live="polite"
              >
                <div className="space-y-4">
                  <div className="rounded-xl border border-sky-500/20 bg-[#080D17] p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-sky-400">
                      Current fictional provisional decision
                    </p>
                    <p className="mt-2 text-[11px] text-slate-400">
                      Simulated product: {scenarioProduct}
                    </p>
                    {activeSelected ? (
                      <>
                        <h3 className="mt-2 break-words text-xl font-semibold">
                          {activeSelected.name}
                        </h3>
                        <p className="mt-2 text-2xl font-bold">
                          {formatINR(
                            (activeSelected.reported_subtotal_minor ?? 0) / 100,
                          )}
                        </p>
                      </>
                    ) : (
                      <h3 className="mt-3 text-base font-semibold text-amber-300">
                        No provisionally eligible offer
                      </h3>
                    )}
                    <p className="mt-2 text-xs text-amber-300">
                      Not authorized for purchase
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-[#080D17] p-4">
                    <h3 className="text-sm font-semibold">
                      Merchant evaluations
                    </h3>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      {displayedCandidates.map((candidate) => (
                        <div
                          key={candidate.place_id}
                          className="min-w-0 rounded-lg border border-slate-800 p-3"
                        >
                          <p className="break-words text-xs font-semibold">
                            {candidate.name}
                          </p>
                          <p className="mt-2 text-xs text-slate-400">
                            ₹{candidate.price} per item · Reported stock{" "}
                            {candidate.stock}
                          </p>
                          <p
                            className={
                              "mt-2 text-xs font-semibold " +
                              (candidate.reasons.length
                                ? "text-rose-300"
                                : "text-emerald-300")
                            }
                          >
                            {candidate.status}
                          </p>
                          {candidate.reasons.length > 0 && (
                            <p className="mt-2 break-words text-xs leading-5 text-amber-200">
                              {candidate.reasons.join(" · ")}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="rounded-xl border border-slate-800 bg-[#080D17] p-4">
                    <h3 className="text-sm font-semibold">Decision timeline</h3>
                    <div className="mt-3 border-l-2 border-sky-500/40 pl-3 text-xs leading-6 text-slate-300">
                      <p>
                        Initial fictional offers: TEST_STORE_A at{" "}
                        {formatINR(scenarioPriceA)} and TEST_STORE_B at{" "}
                        {formatINR(scenarioPriceB)} per item.{" "}
                        {quantity === 1
                          ? "Store A is initially provisionally preferred."
                          : "Quantity constraints are applied to both offers."}
                      </p>
                      {stockOut && (
                        <p className="mt-3">
                          Changed evidence: TEST_STORE_A stock becomes zero.{" "}
                          {activeSelected
                            ? `New leader: ${activeSelected.name}.`
                            : "No eligible offer remains."}
                        </p>
                      )}
                      {quantity > 1 && (
                        <p className="mt-3">
                          Quantity {quantity} changes the offer totals and
                          eligibility.
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
                    <ShieldAlert
                      className="shrink-0 text-amber-300"
                      size={18}
                    />
                    <div>
                      <p className="text-xs font-semibold text-amber-300">
                        Evidence is not independently verified
                      </p>
                      <p className="mt-2 text-xs leading-5 text-slate-400">
                        Fictional, client-provided merchant data. Merchant
                        ownership, inventory, compatibility and delivery are not
                        authenticated; a Cloud Run result does not make them
                        real. No checkout or real transaction.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
            {remoteEnabled && (
              <div className="mt-5 rounded-xl border border-sky-500/25 bg-[#090F1B] p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-white">
                      Active Evidence Planner · Bayesian / EVSI research fixture
                    </h3>
                    <p className="mt-1 text-xs text-slate-400">
                      Executes the existing Python expected-value-of-information
                      algorithm on Cloud Run. This is an independent synthetic
                      research case, not a verification of the stores above.
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={planLoading}
                    onClick={() => void runVerificationPlan()}
                    className="min-h-10 rounded-lg border border-sky-500/30 bg-sky-500/10 px-4 py-2 text-xs font-semibold text-sky-300 disabled:opacity-40"
                  >
                    {planLoading
                      ? "Computing on Cloud Run..."
                      : "Calculate next verification action"}
                  </button>
                </div>
                {planError && (
                  <p className="mt-3 text-xs text-rose-300" role="alert">
                    {planError}
                  </p>
                )}
                {plan && (
                  <div aria-live="polite" className="mt-4 space-y-3 text-xs">
                    <div className="rounded-lg border border-slate-700 p-3">
                      <p className="text-slate-400">
                        Recommended verification action
                      </p>
                      <p className="mt-1 text-base font-semibold text-sky-300">
                        {plan.recommended_action_id ??
                          plan.stopping_reason ??
                          "No feasible action"}
                      </p>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {plan.actions.map((action) => (
                        <div
                          key={action.action_id}
                          className="rounded-lg border border-slate-800 p-3"
                        >
                          <p className="font-semibold text-white">
                            {action.action_id} · {action.merchant}
                          </p>
                          <p className="mt-1 text-slate-300">
                            Modeled net EVSI: ₹{action.net_evsi_inr}
                          </p>
                          {action.skip_reason && (
                            <p className="mt-1 text-amber-300">
                              {action.skip_reason}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                    <p className="text-amber-200">
                      Synthetic priors, costs and outcomes; no merchant
                      contacted or independently verified.
                    </p>
                  </div>
                )}
              </div>
            )}
          </section>
          <p className="py-2 text-center text-[11px] text-slate-500">
            NeedProof AI · Google AI Builder Cup · Firebase Hosting demo with
            live Gemini and clearly identified synthetic decision support
          </p>
        </div>
      </main>
    </div>
  );
}
