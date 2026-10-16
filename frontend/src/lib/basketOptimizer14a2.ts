import { getAuth, signInAnonymously } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";

export const basketOptimizer14a2Enabled = import.meta.env.VITE_BASKET_OPTIMIZER_14A2_ENABLED === "true";

export type BasketResult14A2 = {
  mode: "EVIDENCE_SEPARATED_BASKET_SCENARIO_14A2";
  solver_engine: string;
  scenario_status: string;
  purchase_allowed: false;
  real_merchant_inventory_verified: false;
  disclosure: string;
  synthetic_optimum: {
    selected_offers: Array<{ sku: string; item_name: string; merchant: string; quantity: number; line_total_minor: number }>;
    used_merchants: Array<{ name: string; fulfillment_fee_minor: number }>;
    totals: null | { subtotal_minor: number; fulfillment_fees_minor: number; total_minor: number; remaining_minor: number };
    excluded_offers: Array<{sku:string; reasons:string[]}>;
    blocked_items: string[];
  };
  verification_backlog: Array<{ sku: string; merchant: string; required_checks: string[]; evidence_source: string }>;
};

export async function requestBasket14a2(payload: unknown): Promise<BasketResult14A2> {
  if (!basketOptimizer14a2Enabled) throw new Error("Basket scenario planner is disabled in this build.");
  if (!cloudApiUrl || (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl))) {
    throw new Error("A secure backend URL is required.");
  }
  const { app, appCheck } = firebaseShowcaseClients();
  const auth = getAuth(app);
  await auth.authStateReady();
  const current = auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [idToken, appToken] = await Promise.all([current.getIdToken(), getToken(appCheck)]);
  if (!appToken.token) throw new Error("App Check token unavailable.");
  const response = await fetch(`${cloudApiUrl}/api/v1/commerce/basket-plan`, {
    method: "POST", cache: "no-store",
    headers: { Authorization: `Bearer ${idToken}`, "X-Firebase-AppCheck": appToken.token, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(response.status === 503 ? "Basket engine disabled on Cloud Run." :
    response.status === 401 ? "Authentication or App Check failed." :
    response.status === 422 ? "Please check basket constraints and offer evidence." : `Basket API HTTP ${response.status}`);
  const data: unknown = await response.json();
  if (!data || typeof data !== "object" ||
      (data as BasketResult14A2).mode !== "EVIDENCE_SEPARATED_BASKET_SCENARIO_14A2" ||
      (data as BasketResult14A2).purchase_allowed !== false ||
      (data as BasketResult14A2).real_merchant_inventory_verified !== false ||
      !Array.isArray((data as BasketResult14A2).verification_backlog)) {
    throw new Error("Invalid basket optimization response.");
  }
  return data as BasketResult14A2;
}
