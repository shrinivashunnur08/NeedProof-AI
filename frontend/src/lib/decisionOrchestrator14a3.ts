import { getAuth, signInAnonymously } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";

export const decisionOrchestrator14a3Enabled = import.meta.env.VITE_DECISION_ORCHESTRATOR_14A3_ENABLED === "true";

export type Orchestration14A3 = {
  mode: "EVIDENCE_SEPARATED_ORCHESTRATION_14A3";
  client_revision: number;
  snapshot_sha256: string;
  workflow_state: string;
  recommended_next_action: string;
  reason: string;
  workflow_trace: Array<{ stage: string; status: string; state: string; source: string }>;
  change_detection: { comparison: string; changed: boolean | null; changes: Array<{ place_id: string | null; event: string }> };
  merchant_replanning: { decision_status: string; candidates: Array<{ place_id: string; status: string }> };
  product_research: null | { review: { status: string; evidence_gaps: Array<{kind:string;reason:string}> }; passages: Array<{citation_id:string;quote:string;source_id:string}>; sources_verified: false };
  hypothetical_verification_plan: null | {recommended_action_id:string|null;calibration_status:string;actions: Array<{action_id:string;skip_reason?:string}>};
  synthetic_basket_scenario: null | {scenario_status:string; synthetic_optimum: {totals: {total_minor:number}|null; selected_offers: Array<{sku:string}>}; verification_backlog: Array<{sku:string}>};
  purchase_allowed: false;
  merchant_contact_performed: false;
  stock_independently_verified: false;
  workflow_persisted: false;
  gemini_used: false;
  limitations: string[];
};

export async function orchestrate14a3(payload: unknown): Promise<Orchestration14A3> {
  if (!decisionOrchestrator14a3Enabled) throw new Error("14A.3 orchestration is disabled in this build.");
  if (!cloudApiUrl || (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl))) {
    throw new Error("A secure backend URL is required.");
  }
  const {app, appCheck} = firebaseShowcaseClients();
  const auth = getAuth(app);
  await auth.authStateReady();
  const user = auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [idToken, appToken] = await Promise.all([user.getIdToken(), getToken(appCheck)]);
  if (!appToken.token) throw new Error("App Check token unavailable.");
  const response = await fetch(`${cloudApiUrl}/api/v1/decision/orchestrate`, {
    method: "POST", cache: "no-store", headers: {
      "Content-Type": "application/json", "Authorization": `Bearer ${idToken}`,
      "X-Firebase-AppCheck": appToken.token,
    }, body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(response.status === 503 ? "Orchestration is not enabled on the backend." :
    response.status === 401 ? "Firebase authentication / App Check failed." :
    response.status === 422 ? "Inconsistent research, EVSI, or merchant snapshots." :
    `Orchestration API HTTP ${response.status}`);
  const value: unknown = await response.json();
  if (!value || typeof value !== "object") throw new Error("Invalid orchestration response.");
  const result = value as Orchestration14A3;
  if (result.mode !== "EVIDENCE_SEPARATED_ORCHESTRATION_14A3" ||
      result.purchase_allowed !== false || result.merchant_contact_performed !== false ||
      result.stock_independently_verified !== false || result.gemini_used !== false ||
      !Array.isArray(result.workflow_trace) || !Array.isArray(result.limitations)) {
    throw new Error("Orchestration safety response is invalid.");
  }
  return result;
}
