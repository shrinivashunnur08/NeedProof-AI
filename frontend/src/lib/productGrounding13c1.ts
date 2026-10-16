import { getAuth, signInAnonymously } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";

export const productGrounding13c1Enabled = import.meta.env.VITE_PRODUCT_GROUNDING_13C1_ENABLED === "true";

export type SourceFact13C1 = { kind: "USB_PD_SUPPORT" | "OUTPUT_PROFILE" | "CABLE_CURRENT_RATING"; quote: string; value: string };
export type Document13C1 = { source_id: string; title: string; url: string | null; captured_at: string; excerpt: string; facts: SourceFact13C1[] };
export type GroundingInput13C1 = {
  product_label: string;
  device_model: string;
  device_supports_usb_pd: boolean | null;
  required_power_w: number;
  required_voltage_v: number;
  sources: Document13C1[];
};
export type GroundingResult13C1 = {
  product_label: string;
  status: string;
  cited_facts: Array<{kind: string; source_id: string; title: string; url: string | null; quote: string; captured_at: string}>;
  evidence_gaps: Array<{kind: string; reason: string}>;
  compatibility: {status: string; reasons: string[]; recommended_next_action: string; purchase_allowed: false};
  provenance: "USER_SUPPLIED_EXCERPTS_NOT_INDEPENDENTLY_VERIFIED";
  purchase_allowed: false;
  notice: string;
};

export async function reviewGroundedProduct(input: GroundingInput13C1): Promise<GroundingResult13C1> {
  if (!productGrounding13c1Enabled) throw new Error("Product evidence review is not enabled in this build.");
  if (!cloudApiUrl || (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl))) {
    throw new Error("Authenticated Cloud Run API is not configured.");
  }
  const { app, appCheck } = firebaseShowcaseClients();
  const auth = getAuth(app);
  await auth.authStateReady();
  const user = auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [userToken, appToken] = await Promise.all([user.getIdToken(), getToken(appCheck)]);
  if (!appToken.token) throw new Error("Firebase App Check is unavailable.");
  const response = await fetch(`${cloudApiUrl}/api/v1/products/grounded-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${userToken}`, "X-Firebase-AppCheck": appToken.token },
    body: JSON.stringify(input),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(response.status === 401 ? "Firebase authorization failed." :
      response.status === 422 ? "Evidence input invalid: check the quoted claims against the original excerpt." :
      `Grounded review API returned HTTP ${response.status}.`);
  }
  const body: unknown = await response.json();
  if (!body || typeof body !== "object" || !Array.isArray((body as GroundingResult13C1).cited_facts) ||
      (body as GroundingResult13C1).purchase_allowed !== false) {
    throw new Error("Invalid grounded review response.");
  }
  return body as GroundingResult13C1;
}
