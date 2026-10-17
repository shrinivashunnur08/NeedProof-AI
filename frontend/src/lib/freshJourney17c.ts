import {cloudApiUrl, firebaseShowcaseConfigured, requestCloudFreshJourney17C} from "./cloudDecisions";

export type DocumentCase17D = "not_submitted" | "matching_fixture" | "conflicting_fixtures";
export type EvidencePassport17D = {
  mode: "EVIDENCE_PASSPORT_17D"; data_origin: "SERVER_CREATED_FICTIONAL_WHAT_IF_ONLY";
  issued_at: string; snapshot_sha256: string; overall_trust_state: string;
  sources: Array<{source_id: string; source_type: string; display_title: string; content_sha256: string; captured_at: string; freshness_label: string; independently_verified: false; origin_authenticated: false; external_url: null}>;
  claims: Array<{claim_id: string; kind: string; display_value: string; source_id: string | null; citation_id: string | null; verification_status: string; explanation: string; purchase_eligible: false}>;
  conflicts: Array<{conflict_id: string; topic: string; status: string; source_ids: string[]; citations: Array<{source_id: string; quote: string}>; action: string}>;
  unresolved_verification: Array<{kind: string; label: string}>;
  freshness_is_real_world_verified: false; real_world_evidence_present: false;
  merchant_verified: false; stock_verified: false; compatibility_verified: false;
  purchase_allowed: false; interpretation: string;
};

export type Simulation17C = "reported_offer" | "stockout" | "no_merchants";
export type FictionalUpdate17E = "none" | "stockout_after_report" | "restock_after_stockout";
export type VerificationQueue17E = {
  mode: "NEXT_BEST_PROOF_17E"; data_origin: "FICTIONAL_SCENARIO_AND_UNCALIBRATED_ASSUMPTIONS";
  snapshot_sha256: string; workflow_state: string; recommended_action_id: string;
  selection_rule: string;
  actions: Array<{rank: number; action_id: string; label: string; reason: string; suggested_human_check: string; status: "NOT_EXECUTED"; requires_independent_evidence: true; score_origin: string}>;
  hypothetical_evsi: {status: string; recommended_action_id: string | null; actions: Array<{action_id: string; net_evsi_inr: string; skip_reason: string | null}>; assumptions_calibrated: false; assumptions?: Record<string, string>; purchase_allowed?: false};
  hypothetical_merchant_update: null | {event_id: string; previous_fictional_report: Simulation17C; current_fictional_report: Simulation17C; origin: string; authenticated_merchant: false; persistent_history: false; actual_merchant_contact: false};
  real_merchant_evidence_submitted: false; merchant_verified: false; stock_verified: false; external_requests_performed: false; database_written: false; purchase_allowed: false;
  interpretation: string; business_kpis: {actual_contact_count: 0; real_customer_time_saved_measured: false; real_merchant_response_rate_measured: false; real_conversion_improvement_measured: false};
};
export type FreshInput17C = {
  product_query: string;
  budget_inr: number;
  location_note: string;
  reported_price_inr: number;
  simulated_report: Simulation17C;
  simulation_acknowledged: true;
  synthetic_documents?: DocumentCase17D;
  fictional_merchant_update_17e?: FictionalUpdate17E;
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
  synthetic_documents: DocumentCase17D;
  fictional_merchant_update_17e: FictionalUpdate17E;
  verification_queue_17e: VerificationQueue17E;
  evidence_passport: EvidencePassport17D;
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
    && r.verification_queue_17e?.mode === "NEXT_BEST_PROOF_17E"
    && r.verification_queue_17e?.data_origin === "FICTIONAL_SCENARIO_AND_UNCALIBRATED_ASSUMPTIONS"
    && r.verification_queue_17e?.snapshot_sha256 === r.workflow?.snapshot_sha256
    && r.verification_queue_17e?.workflow_state === r.workflow?.workflow_state
    && r.verification_queue_17e?.purchase_allowed === false
    && r.verification_queue_17e?.real_merchant_evidence_submitted === false
    && r.verification_queue_17e?.external_requests_performed === false
    && r.verification_queue_17e?.merchant_verified === false
    && r.verification_queue_17e?.stock_verified === false
    && r.verification_queue_17e?.hypothetical_evsi?.assumptions_calibrated === false
    && Array.isArray(r.verification_queue_17e?.actions)
    && r.verification_queue_17e.actions.length > 0
    && r.verification_queue_17e.actions.every(a => a.status === "NOT_EXECUTED" && a.requires_independent_evidence === true)
    && r.evidence_passport?.mode === "EVIDENCE_PASSPORT_17D"
    && r.evidence_passport?.data_origin === "SERVER_CREATED_FICTIONAL_WHAT_IF_ONLY"
    && r.evidence_passport?.purchase_allowed === false
    && r.evidence_passport?.real_world_evidence_present === false
    && r.evidence_passport?.merchant_verified === false
    && r.evidence_passport?.stock_verified === false
    && r.evidence_passport?.compatibility_verified === false
    && r.evidence_passport?.snapshot_sha256 === r.workflow?.snapshot_sha256
    && Array.isArray(r.evidence_passport?.claims)
    && Array.isArray(r.evidence_passport?.sources)
    && Array.isArray(r.evidence_passport?.conflicts)
    && Array.isArray(r.evidence_passport?.unresolved_verification)
    && r.evidence_passport.claims.every(c => c.purchase_eligible === false)
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
