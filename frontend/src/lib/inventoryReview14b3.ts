import { getAuth, signInAnonymously } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";

export const inventoryReview14b3Enabled = import.meta.env.VITE_INVENTORY_INTELLIGENCE_14B3_ENABLED === "true";

export type InventoryDay14B3 = {
  day: string; opening_units: number; received_units: number; sold_units: number;
  closing_units: number; reported_stockout: boolean;
};
export type InventoryPayload14B3 = {
  sku_code: string; history: InventoryDay14B3[]; lead_time_days: number; synthetic_demo: boolean;
};
export type ReviewSignal14B3 = { day: string; signal: string; difference_units: number|null; detail: string };
export type InventoryResult14B3 = {
  mode: "REPORTED_STOCK_RECONCILIATION_14B3";
  sku_code: string; data_origin: string; record_count: number; latest_day: string;
  reported_closing_units: number; observed_stockout_days: number;
  average_nonstockout_sales_units: number|null; coverage_days_at_observed_sales_rate: number|null;
  forecast_model_reused_14b1: string;
  inventory_review: {
    totals:{balance_mismatches:number;cross_day_gaps:number;sales_spikes:number;reported_stockout_days:number};
    total_review_signals:number; signals:ReviewSignal14B3[];
    signals_truncated:boolean; review_not_fraud_prediction:true;
  };
  lead_time_scenario:{
    status:"INSUFFICIENT_CLEAN_WINDOWS"|"REPLENISHMENT_REVIEW"|"NO_MODELED_SHORTFALL";
    clean_windows:number;minimum_clean_windows:number; empirical_80p_units:number|null;
    gap_to_empirical_80p_units:number|null;reported_on_hand_units:number;
    forecast_sales_proxy_units:number;forecast_shortfall_scenario_units:number;interpretation:string;
  };
  review_actions:string[]; limitations:string[];
  source_records_persisted:false;cloud_model_used:false;inventory_independently_verified:false;
  fraud_determined:false;purchase_allowed:false;
};

export async function analyzeInventory14b3(payload:InventoryPayload14B3):Promise<InventoryResult14B3> {
  if(!inventoryReview14b3Enabled) throw new Error("14B.3 inventory intelligence is not enabled in this build.");
  if(!cloudApiUrl || (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl)))
    throw new Error("Secure Cloud API URL required.");
  const {app,appCheck}=firebaseShowcaseClients();
  const auth=getAuth(app);
  await auth.authStateReady();
  const user=auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [idToken,appCheckToken]=await Promise.all([user.getIdToken(),getToken(appCheck)]);
  if(!appCheckToken.token) throw new Error("Firebase App Check token unavailable.");
  const response=await fetch(`${cloudApiUrl}/api/v1/analytics/inventory-review`,{
    method:"POST",cache:"no-store",headers:{
      "Content-Type":"application/json",Authorization:`Bearer ${idToken}`,
      "X-Firebase-AppCheck":appCheckToken.token,
    },body:JSON.stringify(payload),
  });
  if(!response.ok) throw new Error(response.status===503?"Inventory endpoint is disabled on backend.":
    response.status===401?"Authentication or App Check failed.":
    response.status===413?"Request exceeds 32KB API limit.":
    response.status===422?"Inventory observations failed validation.":
    `Inventory API HTTP ${response.status}`);
  const json:unknown=await response.json();
  if(!json || typeof json!=="object") throw new Error("Invalid inventory response.");
  const r=json as InventoryResult14B3;
  if(r.mode!=="REPORTED_STOCK_RECONCILIATION_14B3" || r.source_records_persisted!==false ||
    r.cloud_model_used!==false || r.inventory_independently_verified!==false ||
    r.fraud_determined!==false || r.purchase_allowed!==false ||
    !r.inventory_review?.signals || !Array.isArray(r.inventory_review.signals) ||
    !r.inventory_review?.review_not_fraud_prediction ||
    !r.lead_time_scenario || !Array.isArray(r.review_actions) || !Array.isArray(r.limitations))
    throw new Error("Invalid inventory safety response contract.");
  return r;
}
