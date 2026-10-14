/**
 * Chunk 12B: explicitly saved showcase state. Firestore is not a source of
 * inventory truth; stored decisions are historical, never active advice.
 */
import { getAuth, signInAnonymously, type User } from "firebase/auth";
import { getToken } from "firebase/app-check";
import {
  deleteDoc,
  doc,
  getDoc,
  getFirestore,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";
import { firebaseShowcaseClients } from "./cloudDecisions";

export type StoredIntent = {
  requested_product: string;
  budget_amount: number | null;
  delivery_location: string | null;
  required_specifications: string[];
  missing_information: string[];
};

export type JourneyEvent = {
  id: string;
  at: string;
  kind: string;
  message: string;
  source: "GEMINI" | "CLOUD_RUN" | "BROWSER_FIXTURE" | "USER";
};

export type HistoricalDecision = {
  source: "CLOUD_RUN" | "BROWSER_FIXTURE";
  selectedId: string | null;
  status: string;
  nextAction: string;
  evaluatedAt: string;
};

export type SavedJourney = {
  requestText: string;
  analyzedRequest: string;
  intent: StoredIntent | null;
  scenario: {
    demoStarted: boolean;
    demoSource: "reference" | "customer";
    quantity: number;
    stockOut: boolean;
  };
  lastDecision: HistoricalDecision | null;
  events: JourneyEvent[];
  savedAt?: string;
};

async function identity(): Promise<{ uid: string; ref: ReturnType<typeof doc> }> {
  const { app, appCheck } = firebaseShowcaseClients();
  const auth = getAuth(app);
  await auth.authStateReady();
  const user: User = auth.currentUser ?? (await signInAnonymously(auth)).user;
  // SDK Firestore requests attach App Check automatically; warming the token
  // here also provides an explicit failure when this device is blocked.
  await getToken(appCheck);
  return {
    uid: user.uid,
    ref: doc(getFirestore(app), "showcase_users", user.uid, "journeys", "current"),
  };
}

const trim = (s: string, limit: number) => s.slice(0, limit);

/** Save only an explicit user-triggered snapshot: never on each keystroke. */
export async function saveJourney(snapshot: SavedJourney): Promise<void> {
  const { uid, ref } = await identity();
  const intent = snapshot.intent
    ? {
        requested_product: trim(snapshot.intent.requested_product, 180),
        budget_amount: snapshot.intent.budget_amount,
        delivery_location: snapshot.intent.delivery_location?.slice(0, 180) ?? null,
        required_specifications: snapshot.intent.required_specifications.slice(0, 20).map((s) => trim(s, 160)),
        missing_information: snapshot.intent.missing_information.slice(0, 20).map((s) => trim(s, 160)),
      }
    : null;
  await setDoc(ref, {
    ownerUid: uid,
    version: 1,
    requestText: trim(snapshot.requestText, 2000),
    analyzedRequest: trim(snapshot.analyzedRequest, 2000),
    intent,
    scenario: {
      demoStarted: snapshot.scenario.demoStarted,
      demoSource: snapshot.scenario.demoSource,
      quantity: snapshot.scenario.quantity,
      stockOut: snapshot.scenario.stockOut,
    },
    lastDecision: snapshot.lastDecision,
    events: snapshot.events.slice(-30).map((event) => ({
      id: trim(event.id, 80),
      at: trim(event.at, 40),
      kind: trim(event.kind, 48),
      message: trim(event.message, 180),
      source: event.source,
    })),
    savedAt: serverTimestamp(),
  });
}

function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}
const text = (value: unknown, fallback = "") => typeof value === "string" ? value : fallback;

/** Validate saved client data before displaying it; it is not verified evidence. */
export async function loadJourney(): Promise<SavedJourney | null> {
  const { uid, ref } = await identity();
  const snapshot = await getDoc(ref);
  if (!snapshot.exists()) return null;
  const data = snapshot.data() as Record<string, unknown>;
  if (data.ownerUid !== uid || data.version !== 1 || !isObject(data.scenario)) {
    throw new Error("Saved journey has an unexpected format.");
  }
  const rawIntent = data.intent;
  const intent: StoredIntent | null = isObject(rawIntent) && typeof rawIntent.requested_product === "string"
    ? {
        requested_product: rawIntent.requested_product.slice(0, 180),
        budget_amount: typeof rawIntent.budget_amount === "number" && Number.isFinite(rawIntent.budget_amount)
          ? rawIntent.budget_amount : null,
        delivery_location: typeof rawIntent.delivery_location === "string" ? rawIntent.delivery_location : null,
        required_specifications: Array.isArray(rawIntent.required_specifications)
          ? rawIntent.required_specifications.filter((s): s is string => typeof s === "string").slice(0, 20)
          : [],
        missing_information: Array.isArray(rawIntent.missing_information)
          ? rawIntent.missing_information.filter((s): s is string => typeof s === "string").slice(0, 20)
          : [],
      } : null;
  const scenario = data.scenario;
  const rawDecision = data.lastDecision;
  const lastDecision: HistoricalDecision | null = isObject(rawDecision) &&
    (rawDecision.source === "CLOUD_RUN" || rawDecision.source === "BROWSER_FIXTURE")
    ? {
        source: rawDecision.source,
        selectedId: typeof rawDecision.selectedId === "string" ? rawDecision.selectedId : null,
        status: text(rawDecision.status),
        nextAction: text(rawDecision.nextAction),
        evaluatedAt: text(rawDecision.evaluatedAt),
      } : null;
  const events: JourneyEvent[] = Array.isArray(data.events)
    ? data.events.filter(isObject).filter((entry) =>
        typeof entry.id === "string" && typeof entry.at === "string" &&
        typeof entry.kind === "string" && typeof entry.message === "string" &&
        ["GEMINI", "CLOUD_RUN", "BROWSER_FIXTURE", "USER"].includes(String(entry.source))
      ).slice(-30).map((entry) => ({
        id: String(entry.id).slice(0, 80),
        at: String(entry.at).slice(0, 40),
        kind: String(entry.kind).slice(0, 48),
        message: String(entry.message).slice(0, 180),
        source: entry.source as JourneyEvent["source"],
      })) : [];
  const savedAt = data.savedAt as { toDate?: () => Date } | undefined;
  return {
    requestText: text(data.requestText).slice(0, 2000),
    analyzedRequest: text(data.analyzedRequest).slice(0, 2000),
    intent,
    scenario: {
      demoStarted: scenario.demoStarted === true,
      demoSource: scenario.demoSource === "customer" ? "customer" : "reference",
      quantity: typeof scenario.quantity === "number" && Number.isInteger(scenario.quantity)
        ? Math.max(1, Math.min(20, scenario.quantity)) : 1,
      stockOut: scenario.stockOut === true,
    },
    lastDecision,
    events,
    savedAt: savedAt?.toDate?.()?.toISOString(),
  };
}

export async function deleteJourney(): Promise<void> {
  const { ref } = await identity();
  await deleteDoc(ref);
}
