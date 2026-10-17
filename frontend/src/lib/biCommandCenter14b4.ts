import { getAuth, signInAnonymously } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";

export const biCommandCenter14b4Enabled = import.meta.env.VITE_BI_COMMAND_CENTER_14B4_ENABLED === "true";
export type BIInput14B4 = {
  as_of:string; synthetic_demo:boolean;
  forecast?:{sku_code:string;projected_sales_units:number;horizon_days:number;backtest_wape_pct:number|null;reported_stockout_days:number}|null;
  inventory?:{sku_code:string;reported_on_hand_units:number;balance_mismatches:number;cross_day_gaps:number;unusual_sales_days:number;modeled_lead_time_shortfall_units:number|null}|null;
  cohorts?:{anonymous_profile_count:number;aggregate_cohort_count:number;minimum_cohort_size:number;association_rule_count:number}|null;
  verification?:{candidates_considered:number;unresolved_evidence_items:number;provisional_candidates:number}|null;
};
export type BIKPI14B4={key:string;label:string;value:number;unit:string;source_module:string;data_origin:string;interpretation:string};
export type BIAction14B4={key:string;priority:number;source_module:string;title:string;reason:string;requires_human_verification:true};
export type BIResult14B4={
  mode:"AGGREGATE_BI_COMMAND_CENTER_14B4";data_origin:string;as_of:string;snapshot_age_days:number;
  coverage:{available_modules:number;total_modules:4;supplied:Record<string,boolean>;missing_modules:string[]};
  metrics:BIKPI14B4[];review_queue:BIAction14B4[];executive_summary:string;limitations:string[];
  source_records_persisted:false;independently_verified:false;cloud_model_used:false;
  bigquery_used:false;purchase_allowed:false;fraud_determined:false;individual_customer_data_returned:false;
};

export async function evaluateBI14B4(input:BIInput14B4):Promise<BIResult14B4>{
  if(!biCommandCenter14b4Enabled) throw new Error("BI command center is disabled in this build.");
  if(!cloudApiUrl || (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl)))
    throw new Error("A secure backend URL is required.");
  const {app,appCheck}=firebaseShowcaseClients();
  const auth=getAuth(app);await auth.authStateReady();
  const user=auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [idToken,appToken]=await Promise.all([user.getIdToken(),getToken(appCheck)]);
  if(!appToken.token) throw new Error("App Check token unavailable.");
  const response=await fetch(`${cloudApiUrl}/api/v1/analytics/command-center`,{
    method:"POST",cache:"no-store",headers:{"Content-Type":"application/json","Authorization":`Bearer ${idToken}`,
      "X-Firebase-AppCheck":appToken.token},body:JSON.stringify(input),
  });
  if(!response.ok) throw new Error(response.status===503?"BI command-center endpoint is disabled on the backend.":
    response.status===401?"Firebase authentication or App Check failed.":
    response.status===413?"Summary payload exceeds API size limits.":
    response.status===422?"Invalid aggregate summary. Check dates, SKU IDs and numeric limits.":
    `BI API HTTP ${response.status}`);
  const raw:unknown=await response.json();
  if(!raw || typeof raw!=="object") throw new Error("Invalid BI response.");
  const out=raw as BIResult14B4;
  if(out.mode!=="AGGREGATE_BI_COMMAND_CENTER_14B4" || out.source_records_persisted!==false ||
    out.independently_verified!==false || out.cloud_model_used!==false || out.bigquery_used!==false ||
    out.purchase_allowed!==false || out.fraud_determined!==false || out.individual_customer_data_returned!==false ||
    !out.coverage || !Array.isArray(out.metrics) || !Array.isArray(out.review_queue) || !Array.isArray(out.limitations))
    throw new Error("BI evidence boundary or API contract invalid.");
  return out;
}
