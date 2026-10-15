import { getAuth, signInAnonymously } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";

export const evidence13bEnabled = import.meta.env.VITE_MERCHANT_EVIDENCE_ENABLED === "true";

export type EvidenceRevision13B = {
  revision_id: number;
  stock_quantity: number;
  price_minor: number | null;
  currency: string;
  specification_notes: string | null;
  delivery_available: boolean | null;
  recorded_at: string;
  source: "MERCHANT_REPORTED_UNVERIFIED";
};
export type EvidenceInquiry13B = {
  inquiry_id: string;
  place_id: string;
  product_query: string;
  status: "AWAITING_MERCHANT" | "REPORTED_UNVERIFIED" | "EXPIRED";
  merchant_contacted: false;
  current_report: EvidenceRevision13B | null;
  history: EvidenceRevision13B[];
  replanning: { recommended_next_action: string; candidates: Array<{ status: string; reasons: string[]; evidence_gaps: string[] }> };
  notice: string;
};

async function authorizedRequest(path: string, options: { method?: "GET" | "POST"; body?: unknown; signal?: AbortSignal }): Promise<EvidenceInquiry13B> {
  if (!evidence13bEnabled) throw new Error("Evidence tracking is not enabled in this release.");
  if (!cloudApiUrl || (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl))) {
    throw new Error("Secure Cloud Run URL is not configured.");
  }
  const { app, appCheck } = firebaseShowcaseClients();
  const auth = getAuth(app);
  await auth.authStateReady();
  const user = auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [idToken, appCheckToken] = await Promise.all([user.getIdToken(), getToken(appCheck)]);
  if (!appCheckToken.token) throw new Error("Firebase App Check token unavailable.");
  const response = await fetch(`${cloudApiUrl}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "X-Firebase-AppCheck": appCheckToken.token,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
    },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
    cache: "no-store",
    signal: options.signal,
  });
  if (!response.ok) {
    const generic = response.status === 503 ? "Evidence tracking is not configured on Cloud Run yet." :
      response.status === 429 ? "Too many evidence requests. Please try later." :
      response.status === 401 ? "Authentication or App Check was rejected." :
      `Evidence API returned HTTP ${response.status}.`;
    throw new Error(generic);
  }
  const result = (await response.json()) as EvidenceInquiry13B;
  if (!result || typeof result.inquiry_id !== "string" || !Array.isArray(result.history)) {
    throw new Error("Evidence API returned an unexpected response.");
  }
  return result;
}

export function createEvidenceInquiry(placeId: string, productQuery: string, signal?: AbortSignal): Promise<EvidenceInquiry13B> {
  return authorizedRequest("/api/v1/evidence/inquiries", {
    method: "POST", body: { place_id: placeId, product_query: productQuery }, signal,
  });
}
export function getEvidenceInquiry(inquiryId: string, signal?: AbortSignal): Promise<EvidenceInquiry13B> {
  if (!/^[a-f0-9-]{36}$/.test(inquiryId)) throw new Error("Invalid evidence reference.");
  return authorizedRequest(`/api/v1/evidence/inquiries/${encodeURIComponent(inquiryId)}`, { signal });
}
