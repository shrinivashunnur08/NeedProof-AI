import {cloudApiUrl, firebaseShowcaseConfigured, requestCloudFreshJourney17C} from "./cloudDecisions";

export type Simulation17C = "reported_offer" | "stockout" | "no_merchants";
export type FreshInput17C = {
  product_query: string;
  budget_inr: number;
  location_note: string;
  reported_price_inr: number;
  simulated_report: Simulation17C;
  simulation_acknowledged: true;
};
export type FreshResult17C = {
  mode: "FRESH_STRUCTURED_WHAT_IF_17C";
  execution: "LIVE_LOCAL_OR_CLOUD_PYTHON_NO_MODEL";
  evidence_origin: "SERVER_GENERATED_FICTIONAL_FROM_CUSTOMER_CONTROLS";
  input_product_query: string;
  input_budget_inr: number;
  input_reported_price_inr: number;
  location_note_unverified: string;
  location_used_for_discovery: false;
  simulated_report: Simulation17C;
  gemini_called: false;
  merchant_contacted: false;
  stock_independently_verified: false;
  purchase_allowed: false;
  workflow: {
    workflow_state: string;
    recommended_next_action: string;
    reason: string;
    snapshot_sha256: string;
    merchant_replanning: {selected: {name: string} | null};
    change_detection: {changed: boolean | null; changes: Array<{event: string}>};
    workflow_trace: Array<{stage: string; state: string; status: string}>;
    purchase_allowed: false;
  };
  limitations: string[];
};

export const local17C = import.meta.env.DEV && import.meta.env.VITE_NP17C_LOCAL_DEV === "true";
export const cloud17C = !local17C && import.meta.env.VITE_NP17C_CLOUD_ENABLED === "true"
  && Boolean(cloudApiUrl) && firebaseShowcaseConfigured();
export const fresh17CEnabled = local17C || cloud17C;

function isResult(body: unknown): body is FreshResult17C {
  if (!body || typeof body !== "object") return false;
  const r = body as Partial<FreshResult17C>;
  return r.mode === "FRESH_STRUCTURED_WHAT_IF_17C"
    && r.execution === "LIVE_LOCAL_OR_CLOUD_PYTHON_NO_MODEL"
    && r.purchase_allowed === false && r.stock_independently_verified === false
    && r.gemini_called === false && r.merchant_contacted === false
    && r.location_used_for_discovery === false
    && r.workflow?.purchase_allowed === false
    && typeof r.workflow?.workflow_state === "string"
    && typeof r.workflow?.reason === "string"
    && Array.isArray(r.workflow?.workflow_trace)
    && Array.isArray(r.limitations);
}

export async function runFresh17C(payload: FreshInput17C, signal?: AbortSignal): Promise<FreshResult17C> {
  if (!fresh17CEnabled) throw new Error("17C is not activated. Local dev requires the explicit Vite flag and loopback API.");
  let body: unknown;
  if (local17C) {
    const response = await fetch("/api/v1/demo/fresh-journey", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload), cache: "no-store", signal,
    });
    if (!response.ok) throw new Error(`Local Python API HTTP ${response.status}. Check backend flag and localhost:8000.`);
    body = await response.json();
  } else {
    body = await requestCloudFreshJourney17C(payload, signal);
  }
  if (!isResult(body)) throw new Error("17C API returned an invalid or unsafe response.");
  return body;
}
