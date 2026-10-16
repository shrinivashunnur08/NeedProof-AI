import { getAuth, signInAnonymously } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";
import type { CloudReplanInput } from "./cloudDecisions";

export const evidencePlanner14a1Enabled = import.meta.env.VITE_EVIDENCE_PLANNER_14A1_ENABLED === "true";

type ReplanSnapshot = {
  customer: CloudReplanInput["customer"];
  merchants: Array<{
    place_id: string;
    name: string;
    evidence?: {
      product_query: string;
      status: "REPORTED_UNVERIFIED";
      submission: {
        product_name: string; stock_quantity: number; price_minor: number | null;
        currency: string; delivery_available: boolean | null; submitted_at: string | null;
      };
      assessment: { status: string; freshness: string; eligible_for_commitment: false };
    } | null;
  }>;
};

export type EvidenceProposal14A1 = {
  place_id: string;
  indicative_price_minor: number | null;
  assumed_prior_feasible: number;
  assumed_response_probability: number;
  verification_cost_minor: number;
  verification_delay_minutes: number;
  compatibility_status: "UNKNOWN" | "CONDITIONAL_SPEC_MATCH" | "INSUFFICIENT_SPEC_INPUT" | "INSUFFICIENT_SOURCE_EVIDENCE" | "REPORTED_SPEC_MISMATCH";
  source_reference_ids: string[];
  signals: Array<{
    evidence_kind: "MERCHANT_REPORTED_UNVERIFIED" | "USER_SUPPLIED_EXCERPT_UNVERIFIED" | "OPERATOR_ASSUMPTION";
    observed_positive: boolean;
    assumed_sensitivity: number;
    assumed_specificity: number;
    source_reference: string;
  }>;
};

export type EvidencePlan14A1Input = {
  snapshot: ReplanSnapshot;
  proposals: EvidenceProposal14A1[];
  deadline_minutes: number;
  assumption_acknowledged: true;
};

export type EvidencePlan14A1Result = {
  mode: "CLIENT_EVIDENCE_HYPOTHETICAL_EVSI_14A1";
  recommended_action_id: string | null;
  stopping_reason: string | null;
  actions: Array<{ action_id: string; merchant: string; sku: string; net_evsi_inr: string; skip_reason: string | null }>;
  evidence_traces: Array<{ place_id: string; price_provenance: string; assumed_prior: number; assumed_posterior: number; blocked_reason: string | null }>;
  snapshot_replanning: { purchase_allowed: false; recommended_next_action: string; candidates: Array<{status: string }> };
  purchase_allowed: false;
  calibration_status: string;
  assumptions: string[];
};

export async function requestEvidencePlan14A1(payload: EvidencePlan14A1Input): Promise<EvidencePlan14A1Result> {
  if (!evidencePlanner14a1Enabled) throw new Error("Evidence verification planning is disabled in this build.");
  if (!cloudApiUrl || (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl))) {
    throw new Error("A secure Cloud Run decision API URL is required.");
  }
  const { app, appCheck } = firebaseShowcaseClients();
  const auth = getAuth(app);
  await auth.authStateReady();
  const user = auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [idToken, appToken] = await Promise.all([user.getIdToken(), getToken(appCheck)]);
  if (!appToken.token) throw new Error("Firebase App Check token unavailable.");
  const res = await fetch(`${cloudApiUrl}/api/v1/decision/evidence-plan`, {
    method: "POST", cache: "no-store",
    headers: { Authorization: `Bearer ${idToken}`, "X-Firebase-AppCheck": appToken.token, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(res.status === 503 ? "Evidence planner is disabled on Cloud Run." :
    res.status === 401 ? "Authentication or App Check failed." :
    res.status === 422 ? "Check evidence assumptions, budget, or linked store IDs." : `Planning API returned HTTP ${res.status}.`);
  const result: unknown = await res.json();
  if (!result || typeof result !== "object" ||
      (result as EvidencePlan14A1Result).purchase_allowed !== false ||
      !Array.isArray((result as EvidencePlan14A1Result).actions) ||
      (result as EvidencePlan14A1Result).mode !== "CLIENT_EVIDENCE_HYPOTHETICAL_EVSI_14A1") {
    throw new Error("Invalid evidence planning result.");
  }
  return result as EvidencePlan14A1Result;
}
