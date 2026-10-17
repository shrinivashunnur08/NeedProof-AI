import { getAI, getGenerativeModel, GoogleAIBackend } from "firebase/ai";
import { initializeApp, type FirebaseApp } from "firebase/app";
import {
  initializeAppCheck,
  getToken,
  ReCaptchaEnterpriseProvider,
  type AppCheck,
} from "firebase/app-check";
import { getAuth, signInAnonymously } from "firebase/auth";
import type { DecisionResult } from "../components/AdaptiveDecisionPanel";

type Clients = { app: FirebaseApp; appCheck: AppCheck };
let cached: Clients | null = null;
let model: ReturnType<typeof getGenerativeModel> | null = null;

export const cloudApiUrl = (import.meta.env.VITE_CLOUD_DECISION_API_URL ?? "").trim().replace(/\/$/, "");

/** Check required public web-client configuration without contacting Firebase. */
export function firebaseShowcaseConfigured(): boolean {
  return Boolean(
    import.meta.env.VITE_FIREBASE_PROJECT_ID &&
    import.meta.env.VITE_FIREBASE_API_KEY &&
    import.meta.env.VITE_FIREBASE_APP_ID &&
    import.meta.env.VITE_APPCHECK_SITE_KEY
  );
}

export function firebaseShowcaseClients(): Clients {
  if (cached) return cached;
  const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID;
  const apiKey = import.meta.env.VITE_FIREBASE_API_KEY;
  const appId = import.meta.env.VITE_FIREBASE_APP_ID;
  const siteKey = import.meta.env.VITE_APPCHECK_SITE_KEY;
  if (!projectId || !apiKey || !appId || !siteKey) {
    throw new Error("Firebase web configuration is incomplete. Configure this Vite environment before using Gemini or Firestore.");
  }
  const app = initializeApp({
    apiKey,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId,
    appId,
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  });
  const appCheck = initializeAppCheck(app, {
    provider: new ReCaptchaEnterpriseProvider(siteKey),
    isTokenAutoRefreshEnabled: true,
  });
  cached = { app, appCheck };
  return cached;
}

export function getShowcaseGeminiModel() {
  if (model) return model;
  const { app } = firebaseShowcaseClients();
  model = getGenerativeModel(getAI(app, { backend: new GoogleAIBackend() }), {
    model: "gemini-3.5-flash-lite",
  });
  return model;
}

export type CloudReplanInput = {
  customer: {
    product_query: string;
    budget_minor: number | null;
    required_quantity: number;
    delivery_required: boolean;
  };
  merchants: Array<{
    place_id: string;
    name: string;
    evidence: {
      product_query: string;
      status: "REPORTED_UNVERIFIED";
      submission: {
        product_name: string;
        stock_quantity: number;
        price_minor: number;
        currency: "INR";
        delivery_available: boolean;
        submitted_at: string;
      };
      assessment: {
        status: "REPORTED_UNVERIFIED";
        freshness: "RECENT_REPORT";
        eligible_for_commitment: false;
      };
    };
  }>;
};

export type CloudVerificationPlan = {
  mode: string;
  recommended_action_id: string | null;
  stopping_reason: string | null;
  baseline: { merchant: string; sku: string; price_inr: string } | null;
  actions: Array<{
    action_id: string;
    merchant: string;
    net_evsi_inr: string;
    skip_reason: string | null;
  }>;
  assumptions: string[];
};

async function authorizedPost(path: string, payload: unknown, signal?: AbortSignal): Promise<unknown> {
  if (!cloudApiUrl) throw new Error("Cloud decision API URL not configured.");
  if (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl)) {
    throw new Error("Cloud decision API must use HTTPS.");
  }
  const { app, appCheck } = firebaseShowcaseClients();
  const auth = getAuth(app);
  await auth.authStateReady();
  const user = auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [userToken, appToken] = await Promise.all([user.getIdToken(), getToken(appCheck)]);
  if (!appToken.token) throw new Error("Firebase App Check token unavailable.");
  const res = await fetch(`${cloudApiUrl}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${userToken}`,
      "X-Firebase-AppCheck": appToken.token,
    },
    body: JSON.stringify(payload),
    cache: "no-store",
    signal,
  });
  if (!res.ok) {
    throw new Error(
      res.status === 401
        ? "Cloud API authentication failed. Check Anonymous Auth, App Check and Cloud Run permissions."
        : `Cloud decision API returned HTTP ${res.status}.`,
    );
  }
  return (await res.json()) as unknown;
}

export async function requestCloudReplan(payload: CloudReplanInput, signal?: AbortSignal): Promise<DecisionResult> {
  const body = await authorizedPost("/api/v1/decision/replan", payload, signal);
  if (
    !body || typeof body !== "object" ||
    !Array.isArray((body as DecisionResult).candidates) ||
    (body as DecisionResult).purchase_allowed !== false ||
    typeof (body as DecisionResult).recommended_next_action !== "string"
  ) {
    throw new Error("Cloud decision API returned an invalid response.");
  }
  return body as DecisionResult;
}

export async function requestCloudVerificationPlan(
  budgetInr = 1000,
  signal?: AbortSignal,
): Promise<CloudVerificationPlan> {
  const body = await authorizedPost("/api/v1/decision/verification-plan", {
    budget_inr: Math.max(100, Math.min(10000, Math.round(budgetInr))),
    deadline_minutes: 15,
    a_prior: 0.65,
    a_response_probability: 0.8,
    a_verification_cost_inr: 8,
  }, signal);
  if (
    !body || typeof body !== "object" ||
    !Array.isArray((body as CloudVerificationPlan).actions) ||
    typeof (body as CloudVerificationPlan).mode !== "string"
  ) {
    throw new Error("Cloud verification planner returned an invalid response.");
  }
  return body as CloudVerificationPlan;
}
