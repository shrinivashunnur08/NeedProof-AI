import { getAuth, signInAnonymously } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";

export type StoreCandidate = {
  place_id: string;
  name: string;
  address: string;
  maps_url: string | null;
  inventory_status: "UNKNOWN";
  verification_status: "NOT_VERIFIED";
};
export type DiscoveryResult = {
  source: "GOOGLE_PLACES_NEW";
  status: "CANDIDATES_ONLY";
  stores: StoreCandidate[];
  disclaimer: string;
};

export async function discoverRealStores(product: string, area: string, signal?: AbortSignal): Promise<DiscoveryResult> {
  if (!cloudApiUrl) throw new Error("Cloud Run URL not configured.");
  const { app, appCheck } = firebaseShowcaseClients();
  const auth = getAuth(app);
  await auth.authStateReady();
  const user = auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [idToken, appToken] = await Promise.all([user.getIdToken(), getToken(appCheck)]);
  if (!appToken.token) throw new Error("App Check token unavailable.");
  const res = await fetch(`${cloudApiUrl}/api/v1/discovery/stores`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
      "X-Firebase-AppCheck": appToken.token,
    },
    body: JSON.stringify({ product_query: product.trim(), area: area.trim() }),
    signal,
    cache: "no-store",
  });
  if (!res.ok) {
    if (res.status === 429) throw new Error("Please wait before searching again (rate limit).");
    if (res.status === 503) throw new Error("Store discovery isn't available yet or its quota is exhausted.");
    if (res.status === 401) throw new Error("Firebase authentication/App Check rejected this request.");
    throw new Error(`Store discovery returned HTTP ${res.status}.`);
  }
  const data: unknown = await res.json();
  if (!data || typeof data !== "object") throw new Error("Invalid Places response.");
  const result = data as DiscoveryResult;
  if (result.source !== "GOOGLE_PLACES_NEW" || result.status !== "CANDIDATES_ONLY" || !Array.isArray(result.stores)) {
    throw new Error("Unexpected store discovery response.");
  }
  return result;
}
