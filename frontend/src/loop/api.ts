export type City = { id: string; name: string; currency: string; symbol: string; languages: string[]; country?: string; lat?: number; lng?: number; demo?: boolean };
export type Intent = {
  item: string | null; category: string | null; wattage_w: number | null; connector: string | null; usb_pd: boolean | null;
  device_model: string | null; features: string[]; budget_amount: number | null; budget_currency: string | null;
  quantity: number | null; urgency: string | null; location_text: string | null; language: string;
  missing_info: string[]; clarifying_question: string | null;
};
export type NearbyShop = { shop_id: string; shop: string; area: string; distance_km: number | null; source: string; photo_proof: string; lat?: number | null; lng?: number | null };
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
  lat?: number | null; lng?: number | null;
  listed_stock: number; spec_check: SpecCheck; over_budget: boolean; usable: boolean; photo_proof: string;
  decision: {
    workflow_state: string; state_text: string; next_best_proof: string | null; purchase_allowed: boolean;
    trust_state?: string; unresolved?: string[]; conflicts?: number; snapshot_sha256?: string;
    next_checks?: { rank: number; label: string; reason: string; check: string }[];
  };
};
export type TraceStep = { tool: string; args: Record<string, unknown>; result: string };
export type ChatResult = {
  reply: string; mode: string; model: { latency_ms?: number; model?: string; backend?: string; error?: string };
  trace: TraceStep[]; offers: Offer[]; request: { id: number; shops_notified: number } | null;
  intent?: Intent; intent_model?: { mode?: string; latency_ms?: number }; nearby?: NearbyShop[];
  location?: { city: City; lat?: number; lng?: number; label?: string };
  remembered?: string[]; profile?: Profile | null; basket?: Basket | null; proof_plan?: ProofPlan | null; addon?: { item: string; share_pct: number; note: string } | null;
};
export type ProofPlan = {
  engine: string; advice: string; verified_available: boolean; currency?: string; assumptions?: string;
  ranked: { shop: string; shop_id: string; basis: string; history: string; price: string | null; p_has_it: number;
    reply_chance: number; net_value: number; worth_asking: boolean; skip_reason: string | null }[];
};
export type Basket = {
  status: string; items: string[]; budget: string | null; max_shops: number; solver: string; currency: string;
  lines: { item: string; shop: string; shop_id: string; listing: string; price: string; stock: number; proof: string }[];
  shops: { shop_id: string; shop: string; area: string; lat?: number | null; lng?: number | null; distance_km?: number | null; items: string[]; subtotal: string }[];
  total?: string; within_budget?: boolean | null; verified_lines?: number; missing?: string[]; reason?: string; solve_ms?: number; note?: string;
  baselines?: { cheapest_item_first: { total: string; shops: number; fits_max_shops: boolean }; single_shop: { shop: string; total: string } | null };
};
export type Profile = {
  id: string; name: string; city: string; device: string | null; budget: number | null; currency: string | null;
  language: string | null; needs: { item: string; wattage_w?: number | null; connector?: string | null; at?: string }[];
};
export type Analytics = {
  shop: { id: string; name: string }; currency: string; data_note: string; stock_source?: string;
  command_center?: { summary: string; queue: { priority: number; title: string; reason: string; source_module: string }[]; method: string } | null;
  forecast: { product: string; selected_model: string; models: { model: string; mae: number; wape_pct: number | null }[];
    next_7_days_units: number; daily: { day: string; units: number; low: number; high: number }[]; history: number[];
    shortfall_before_restock: number | null; method: string };
  inventory: { sku: string; on_hand: number; stockout_days_56: number; coverage_days: number | null; status: string | null;
    shortfall_units: number | null; review_signals: number | null; actions: unknown[]; method: string };
  segments: { items: { name: string; share_pct: number; count: number; recency_days: number; orders_90d: number; spend_90d: string }[];
    silhouette: number | null; method: string };
  baskets: { rules: { if_bought: string; also_bought: string; confidence_pct: number; lift: number; orders: number }[];
    basket_count: number; method: string };
};
export type PhotoCheck = { status: string; issues: string[]; missing: string[]; matches: string[]; cautions?: string[] };
export type ShopResponse = {
  id: number; shop_id: string; shop_name: string; price: number | null; status: string;
  claim: Record<string, unknown>; check_result: PhotoCheck; created_at: string;
  message?: string | null; evidence_class?: string | null; inventory_id?: number | null; inventory_product?: string | null;
};
export type BqForecast = {
  city: string; engine: string; model: string; console_url: string;
  rows: { product_key: string; next_7_days: number; low: number; high: number }[];
};
export type TrustReport = {
  pipeline: { step: string; who: string; what: string }[];
  safeguards: { rule: string; where: string; tested: string }[];
  evals: { model: string; backend: string; run_at: string;
    tasks: { task: string; passed: number; total: number; median_ms: number | null }[];
    photos: { photo: string; got: string; ok: boolean; summary: string | null }[] }[];
  benchmarks: { seconds?: number; mode?: string; error?: string; notes?: string[];
    evidence?: Record<string, { average_realized_net_utility_inr: number; average_verification_cost_inr: number; average_checks: number; failed_selection_rate_pct: number }>;
    basket?: Record<string, { feasibility_rate_pct: number; mean_extra_cost_vs_needproof_inr: number; missed_feasible_cases: number }> };
  live: { requests: number; answered: number; drafts_approved: number; replies_by_status: Record<string, number> };
  limits: string[];
};
export type ShopDashboard = {
  shop: { id: string; name: string; area: string; city: string; currency: string };
  period_days: number;
  kpis: { requests_reached: number; answered: number; could_serve: number; reply_rate_pct: number | null;
    median_reply_minutes: number | null; units_sold: number; revenue: string | null; missed_sales_requests: number };
  outcomes: Record<string, number>;
  inventory: { id: number; product: string; brand: string | null; sku: string | null; specs: Record<string, unknown>;
    price: number; price_text: string; stock: number; image_url: string | null; asks: number; sold: number;
    budget_fit_pct: number | null; median_budget: string | null; low_stock: boolean; updated_at: string | null }[];
  missed_sales: { product: string; asks: number; median_budget: string | null; suggestion: string }[];
  requests: { request_id: number; product: string; budget: string | null; state: string; created_at: string;
    matched_item: string | null; returning_shopper: boolean }[];
  customers: { known: number; returning: number };
  sales: { product: string; qty: number; price: string | null; at: string }[];
  note: string;
};
export type EngineCatalog = {
  engines: { id: string; chunk: string; name: string; what: string; used_in: string; status: string }[];
  retired: { chunk: string; name: string; replaced_by: string }[];
};
export type EngineRun = { id: string; ms: number; input: string; result: Record<string, unknown> };
export type InventoryItem = {
  id: number; shop_id: string; sku: string | null; product: string; brand: string | null; specs: Record<string, unknown>;
  price: number; currency: string; stock: number; image_file: string | null; image_url: string | null;
};
export type InventoryUpload = { items: number; with_photo: number; columns: Record<string, string>; problems: string[]; currency: string };
export type DraftCandidate = {
  inventory_id: number; product: string; brand: string | null; price_text: string; stock: number; score: number;
  spec_issues: string[]; within_budget: boolean; image_url: string | null;
};
export type Draft = {
  request_id: number; shop_id: string; has_inventory: boolean; needs_human_approval: boolean; mode: string; retrieval?: string;
  model?: { latency_ms?: number; error?: string }; reason: string; candidates: DraftCandidate[];
  draft: null | { inventory_id: number; product: string; brand: string | null; price: number; price_text: string;
    stock: number; image_url: string | null; message: string; caveats: string[] };
};
export type LoopRequest = {
  id: number; city: string; product: string; specs: Record<string, unknown>; budget: number | null;
  currency: string | null; language: string; status: string; created_at: string; responses: ShopResponse[];
  shopper_past_requests?: number;
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

/** Demo identity chosen in the role dropdown; the server checks every shop-private call against it. */
export type Persona = "shopper" | "shopkeeper" | "business" | "admin";
export const identity: { role: Persona; shop: string } = { role: "shopper", shop: "" };

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    ...init,
    headers: { "Content-Type": "application/json", "X-NeedProof-Role": identity.role,
      ...(identity.shop ? { "X-NeedProof-Shop": identity.shop } : {}), ...(init?.headers ?? {}) },
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
  status: () => call<{ providers: Providers; cities: City[]; discovery: string; maps_key?: string }>("/status"),
  chat: (city: string, history: { role: "user" | "assistant"; text: string }[], loc?: ShopperLocation | null,
         shopper?: { id: string; name: string }) =>
    call<ChatResult>("/agent/chat", { method: "POST", body: JSON.stringify({
      city, history, lat: loc?.lat, lng: loc?.lng, location_label: loc?.label,
      shopper_id: shopper?.id, shopper_name: shopper?.name }) }),
  profile: (id: string) => call<{ profile: Profile | null }>(`/shoppers/${id}`),
  forget: (id: string) => call<{ forgotten: boolean }>(`/shoppers/${id}`, { method: "DELETE" }),
  analytics: (city: string, shopId?: string) =>
    call<Analytics>(`/cities/${city}/analytics${shopId ? `?shop_id=${encodeURIComponent(shopId)}` : ""}`),
  locate: (body: { lat?: number; lng?: number; query?: string; near_city?: string }) =>
    call<Located>("/locate", { method: "POST", body: JSON.stringify(body) }),
  request: (id: number) => call<LoopRequest>(`/requests/${id}`),
  cityRequests: (city: string) => call<LoopRequest[]>(`/cities/${city}/requests`),
  shops: (city: string) => call<Shop[]>(`/cities/${city}/shops`),
  reply: (id: number, body: { shop_id: string; price?: number; stock?: number; image_base64?: string; image_mime?: string;
    inventory_id?: number; message?: string; approved_by_shopkeeper?: boolean; reply_token?: string }) =>
    call<{ claim: Record<string, unknown>; check: PhotoCheck; mode: string; model: { latency_ms?: number; error?: string }; evidence_class?: string }>(
      `/requests/${id}/reply`, { method: "POST", body: JSON.stringify(body) }),
  insights: (city: string) => call<Insights>(`/cities/${city}/insights`),
  brief: (city: string, language: string, shopId?: string) =>
    call<Brief>(`/cities/${city}/brief`, { method: "POST", body: JSON.stringify({ language, shop_id: shopId || null }) }),
  inventory: (shopId: string) => call<InventoryItem[]>(`/shops/${shopId}/inventory`),
  uploadInventory: (shopId: string, body: { filename: string; sheet_base64: string; images: { name: string; data: string; mime: string }[] }) =>
    call<InventoryUpload>(`/shops/${shopId}/inventory`, { method: "POST", body: JSON.stringify(body) }),
  sampleInventory: (shopId: string) => call<InventoryUpload>(`/shops/${shopId}/inventory/sample`, { method: "POST" }),
  draft: (requestId: number, shopId: string) => call<Draft>(`/requests/${requestId}/draft?shop_id=${encodeURIComponent(shopId)}`),
  templateUrl: `${BASE}/inventory/template.xlsx`,
  bqSync: () => call<{ rows: number; seconds: number; console_url: string; location: string }>("/analytics/bigquery/sync", { method: "POST" }),
  bqForecast: (city: string) => call<BqForecast>(`/cities/${city}/bigquery/forecast`),
  bqBrief: (city: string) => call<{ bullets: string[]; engine: string; seconds: number; console_url: string }>(`/cities/${city}/bigquery/brief`, { method: "POST" }),
  trust: () => call<TrustReport>("/trust"),
  dashboard: (shopId: string) => call<ShopDashboard>(`/shops/${shopId}/dashboard`),
  shopBrief: (shopId: string, language: string) =>
    call<{ brief: { headline: string; actions: string[]; watch_out: string }; mode: string; model: { latency_ms?: number } }>(
      `/shops/${shopId}/brief`, { method: "POST", body: JSON.stringify({ language }) }),
  editItem: (shopId: string, itemId: number, body: { price?: number; stock?: number }) =>
    call<InventoryItem>(`/shops/${shopId}/inventory/${itemId}`, { method: "POST", body: JSON.stringify(body) }),
  sell: (shopId: string, body: { inventory_id?: number; request_id?: number; qty: number }) =>
    call<{ sale_id: number; product: string; qty: number; stock_left: number | null }>(`/shops/${shopId}/sales`, { method: "POST", body: JSON.stringify(body) }),
  engines: () => call<EngineCatalog>("/engines"),
  runEngine: (id: string) => call<EngineRun>(`/engines/${id}/run`, { method: "POST" }),
  replyLink: (requestId: number, shopId: string) =>
    call<{ url: string; text: string; phone: string | null; whatsapp_url: string; direct: boolean }>(`/requests/${requestId}/reply-link?shop_id=${encodeURIComponent(shopId)}`),
  forShop: (requestId: number, shopId: string, t: string) =>
    call<{ request: { id: number; product: string; specs: Record<string, unknown>; budget: number | null; currency: string | null; language: string; status: string; created_at: string };
      shop: { id: string; name: string; area: string }; already_replied: ShopResponse | null }>(`/requests/${requestId}/for-shop?shop_id=${encodeURIComponent(shopId)}&t=${encodeURIComponent(t)}`),
  snap: (image_base64: string, image_mime: string) =>
    call<{ mode: string; message?: string; need: null | { is_relevant: boolean; what_i_see: string; item: string | null; brand: string | null;
      model_number: string | null; wattage_w: number | null; connector: string | null; usb_pd: boolean | null; request_text: string; confidence: number };
      model?: { latency_ms?: number } }>("/agent/snap", { method: "POST", body: JSON.stringify({ image_base64, image_mime }) }),
  reset: () => call<{ reset: boolean }>("/demo/reset", { method: "POST" }),
  exportBq: () => call<{ rows: number; next: string }>("/analytics/export", { method: "POST" }),
};

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",").pop() ?? "");
    r.onerror = () => reject(new Error(`Could not read ${file.name}`));
    r.readAsDataURL(file);
  });
}

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
