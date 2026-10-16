/** Merchant-only Firebase session. Never replaces the customer's anonymous session. */
import { getApp, initializeApp } from "firebase/app";
import { getAuth, initializeAuth, inMemoryPersistence, signInWithEmailAndPassword, signOut, type Auth, type User } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";
import { evidence13bEnabled, type EvidenceInquiry13B } from "./evidence13b";

export type MerchantInboxItem13B3 = {
  inquiry_id: string;
  place_id: string;
  product_query: string;
  created_at: string;
  expires_at: string;
};
export type MerchantInbox13B3 = { inquiries: MerchantInboxItem13B3[]; notice: string };

const MERCHANT_APP_NAME = "needproof-merchant-13b3";
let merchantAuth: Auth | null = null;

export function merchantAuthInstance(): Auth {
  if (merchantAuth) return merchantAuth;
  const { app } = firebaseShowcaseClients();
  let isolatedApp;
  try { isolatedApp = getApp(MERCHANT_APP_NAME); }
  catch { isolatedApp = initializeApp(app.options, MERCHANT_APP_NAME); }
  // No durable merchant sessions: refreshing the page signs out the merchant.
  try { merchantAuth = initializeAuth(isolatedApp, { persistence: inMemoryPersistence }); }
  catch { merchantAuth = getAuth(isolatedApp); }
  return merchantAuth;
}

export async function merchantSignIn(email: string, password: string): Promise<User> {
  const auth = merchantAuthInstance();
  await auth.authStateReady();
  const credentials = await signInWithEmailAndPassword(auth, email.trim(), password);
  if (!credentials.user.emailVerified) {
    await signOut(auth);
    throw new Error("Verify your email address in Firebase Authentication before using the merchant desk.");
  }
  return credentials.user;
}

export async function merchantSignOut(): Promise<void> {
  if (merchantAuth) await signOut(merchantAuth);
}

async function merchantRequest<T>(path: string, body?: unknown): Promise<T> {
  if (!evidence13bEnabled) throw new Error("Merchant evidence is not enabled in this release.");
  if (!cloudApiUrl || (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl))) {
    throw new Error("Secure Cloud Run URL is not configured.");
  }
  const user = merchantAuthInstance().currentUser;
  if (!user || !user.emailVerified || user.isAnonymous) throw new Error("Verified merchant sign-in is required.");
  const { appCheck } = firebaseShowcaseClients();
  const [idToken, appCheckToken] = await Promise.all([user.getIdToken(), getToken(appCheck)]);
  if (!appCheckToken.token) throw new Error("Firebase App Check is unavailable.");
  const response = await fetch(`${cloudApiUrl}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "X-Firebase-AppCheck": appCheckToken.token,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    cache: "no-store",
  });
  if (!response.ok) {
    const message = response.status === 401 ? "Authentication or App Check failed." :
      response.status === 403 ? "Merchant email verification or authorization failed." :
      response.status === 404 ? "Inquiry not found, or your business claim has not been approved." :
      response.status === 410 ? "This inquiry has expired." :
      response.status === 429 ? "Report limit reached. Try again later." :
      response.status === 503 ? "Merchant evidence API is not active yet." :
      `Merchant evidence API returned HTTP ${response.status}.`;
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function getApprovedMerchantInquiries(): Promise<MerchantInbox13B3> {
  const data = await merchantRequest<MerchantInbox13B3>("/api/v1/evidence/merchant/inquiries");
  if (!data || !Array.isArray(data.inquiries)) throw new Error("Invalid merchant inbox response.");
  return data;
}

export type MerchantReportInput13B3 = {
  authorized_to_report: true;
  stock_quantity: number;
  price_minor: number | null;
  specification_notes: string | null;
  delivery_available: boolean | null;
};

export async function submitMerchantReport(inquiryId: string, report: MerchantReportInput13B3): Promise<EvidenceInquiry13B> {
  if (!/^[0-9a-f-]{36}$/i.test(inquiryId)) throw new Error("Invalid inquiry reference.");
  if (!Number.isSafeInteger(report.stock_quantity) || report.stock_quantity < 0 || report.stock_quantity > 1_000_000) {
    throw new Error("Stock quantity is outside the supported range.");
  }
  if (report.stock_quantity > 0 && (!report.price_minor || report.price_minor <= 0)) {
    throw new Error("Enter a reported price when stock is greater than zero.");
  }
  const result = await merchantRequest<EvidenceInquiry13B>(`/api/v1/evidence/merchant/inquiries/${encodeURIComponent(inquiryId)}/reports`, report);
  if (!result || !Array.isArray(result.history) || result.inquiry_id !== inquiryId) {
    throw new Error("Invalid evidence update response.");
  }
  return result;
}
