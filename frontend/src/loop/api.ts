export type City = { id: string; name: string; currency: string; symbol: string; languages: string[]; country?: string; lat?: number; lng?: number; demo?: boolean };
export type Intent = {
  item: string | null; category: string | null; wattage_w: number | null; connector: string | null; usb_pd: boolean | null;
  device_model: string | null; features: string[]; budget_amount: number | null; budget_currency: string | null;
  quantity: number | null; urgency: string | null; location_text: string | null; language: string;
  missing_info: string[]; clarifying_question: string | null;
};
export type NearbyShop = { shop_id: string; shop: string; area: string; distance_km: number | null; source: string; photo_proof: string };
export type Located = {
  city: City; label: string; lat: number; lng: number; shops_found: number; source: string;
  nearest: { id: string; name: string; area: string; distance_km?: number }[]; note: string;
};
export type ShopperLocation = { lat: number; lng: number; label: string; cityId: string; source: string; shopsFound: number; detected: boolean };
export type Providers = {
  profile: string;
  gemini: { backend: string; model: string; ready: boolean; label: string };
  analytics: { backend: string; label: string };
  live_model: boolean;
};
export type SpecCheck = { ok: boolean; issues: string[]; matches: string[] };
export type Offer = {
  shop_id: string; shop: string; area: string; distance_km?: number | null; listing: string; price: string; currency: string;
  listed_stock: number; spec_check: SpecCheck; over_budget: boolean; usable: boolean; photo_proof: string;
  decision: { workflow_state: string; state_text: string; next_best_proof: string | null; purchase_allowed: boolean };
};
export type TraceStep = { tool: string; args: Record<string, unknown>; result: string };
export type ChatResult = {
  reply: string; mode: string; model: { latency_ms?: number; model?: string; backend?: string; error?: string };
  trace: TraceStep[]; offers: Offer[]; request: { id: number; shops_notified: number } | null;
  intent?: Intent; intent_model?: { mode?: string; latency_ms?: number }; nearby?: NearbyShop[];
  location?: { city: City; lat?: number; lng?: number; label?: string };
};
export type PhotoCheck = { status: string; issues: string[]; missing: string[]; matches: string[]; cautions?: string[] };
export type ShopResponse = {
  id: number; shop_id: string; shop_name: string; price: number | null; status: string;
  claim: Record<string, unknown>; check_result: PhotoCheck; created_at: string;
};
export type LoopRequest = {
  id: number; city: string; product: string; specs: Record<string, unknown>; budget: number | null;
  currency: string | null; language: string; status: string; created_at: string; responses: ShopResponse[];
};
export type Shop = { id: string; city: string; name: string; area: string; source?: string; lat?: number; lng?: number };
export type DemandProduct = {
  product_key: string; product: string; asks: number; answered: number; unmet: number; unmet_rate: number;
  avg_budget: string | null; last_7_days: number; previous_7_days: number; growth_pct: number;
  forecast_next_7_days: number; daily_series: number[]; live_asks: number;
};
export type Insights = { city: string; currency: string; products: DemandProduct[]; method: string; data_note: string };
export type Brief = {
  brief: { headline: string; actions: string[]; biggest_gap: string; caution: string };
  mode: string; model: { latency_ms?: number; error?: string };
};

const BASE = "/api/v2/loop";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `Request failed (HTTP ${res.status})`;
    try { const body = await res.json(); if (typeof body.detail === "string") detail = body.detail; } catch { /* keep default */ }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  status: () => call<{ providers: Providers; cities: City[]; discovery: string }>("/status"),
  chat: (city: string, history: { role: "user" | "assistant"; text: string }[], loc?: ShopperLocation | null) =>
    call<ChatResult>("/agent/chat", { method: "POST", body: JSON.stringify({
      city, history, lat: loc?.lat, lng: loc?.lng, location_label: loc?.label }) }),
  locate: (body: { lat?: number; lng?: number; query?: string; near_city?: string }) =>
    call<Located>("/locate", { method: "POST", body: JSON.stringify(body) }),
  request: (id: number) => call<LoopRequest>(`/requests/${id}`),
  cityRequests: (city: string) => call<LoopRequest[]>(`/cities/${city}/requests`),
  shops: (city: string) => call<Shop[]>(`/cities/${city}/shops`),
  reply: (id: number, body: { shop_id: string; price?: number; stock?: number; image_base64?: string; image_mime?: string }) =>
    call<{ claim: Record<string, unknown>; check: PhotoCheck; mode: string; model: { latency_ms?: number; error?: string } }>(
      `/requests/${id}/reply`, { method: "POST", body: JSON.stringify(body) }),
  insights: (city: string) => call<Insights>(`/cities/${city}/insights`),
  brief: (city: string, language: string) =>
    call<Brief>(`/cities/${city}/brief`, { method: "POST", body: JSON.stringify({ language }) }),
  reset: () => call<{ reset: boolean }>("/demo/reset", { method: "POST" }),
  exportBq: () => call<{ rows: number; next: string }>("/analytics/export", { method: "POST" }),
};

/** Shrink phone photos before upload so they stay well under the 5 MB limit. */
export async function photoToBase64(file: File): Promise<{ data: string; mime: string; preview: string }> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error("Could not read that image"));
      el.src = url;
    });
    const scale = Math.min(1, 1600 / Math.max(img.width, img.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
    const preview = canvas.toDataURL("image/jpeg", 0.85);
    return { data: preview.split(",")[1], mime: "image/jpeg", preview };
  } finally {
    URL.revokeObjectURL(url);
  }
}
