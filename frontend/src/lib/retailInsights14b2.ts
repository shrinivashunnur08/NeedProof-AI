import { getAuth, signInAnonymously } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";

export const retailInsights14b2Enabled = import.meta.env.VITE_RETAIL_INSIGHTS_14B2_ENABLED === "true";

export type Profile14B2 = {recency_days:number;orders_90d:number;spend_minor_90d:number};
export type Segment14B2 = {
  segment:string;count:number;share_pct:number;mean_recency_days:number;
  mean_orders_90d:number;mean_spend_minor_90d:number;
};
export type PairRule14B2 = {
  antecedent_sku:string;consequent_sku:string;cooccurring_orders:number;
  support_pct:number;confidence_pct:number;confidence_wilson95_lower_pct:number;
  lift:number;leverage:number;association_only:true;
};
export type RetailInsights14B2 = {
  mode:"DESCRIPTIVE_COHORT_BASKET_INSIGHTS_14B2";
  data_origin:"CLIENT_LABELED_SYNTHETIC_DEMO"|"USER_SUPPLIED_UNVERIFIED_AGGREGATES";
  segmentation:{method:string;profile_count:number;selected_k:number;exploratory_silhouette:number|null;
    segments:Segment14B2[];individual_assignments_disclosed:false;min_reported_group_size:number;interpretation:string};
  basket_analysis:{method:string;basket_count:number;distinct_product_codes:number;minimum_pair_orders:number;
    rules:PairRule14B2[];eligible_rules_before_cap:number;interpretation:string};
  limitations:string[];source_records_persisted:false;direct_identifiers_accepted:false;
  cloud_model_used:false;purchase_allowed:false;personalized_targeting_allowed:false;independently_verified:false;
};

export async function analyzeRetail14b2(input:{
  profiles:Profile14B2[];baskets:string[][];minimum_pair_orders:number;synthetic_demo:boolean;
}):Promise<RetailInsights14B2>{
  if(!retailInsights14b2Enabled) throw new Error("14B.2 cohort and basket analytics are disabled in this build.");
  if(!cloudApiUrl || (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl)))
    throw new Error("A secure backend URL is required.");
  const {app,appCheck}=firebaseShowcaseClients();
  const auth=getAuth(app);
  await auth.authStateReady();
  const user=auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [idToken,appToken]=await Promise.all([user.getIdToken(),getToken(appCheck)]);
  if(!appToken.token) throw new Error("App Check token unavailable.");
  const response=await fetch(`${cloudApiUrl}/api/v1/analytics/cohort-basket-insights`,{
    method:"POST",cache:"no-store",headers:{
      "Content-Type":"application/json","Authorization":`Bearer ${idToken}`,
      "X-Firebase-AppCheck":appToken.token,
    },body:JSON.stringify(input),
  });
  if(!response.ok) throw new Error(response.status===503 ? "Cohort/basket endpoint is disabled on the backend." :
    response.status===401 ? "Firebase authentication or App Check failed." :
    response.status===413 ? "Request too large: shorten the CSV inputs." :
    response.status===422 ? "Invalid aggregate profile or order basket values." :
    `Retail insights API HTTP ${response.status}`);
  const json:unknown=await response.json();
  if(!json || typeof json!=="object") throw new Error("Invalid analytics response.");
  const result=json as RetailInsights14B2;
  if(result.mode!=="DESCRIPTIVE_COHORT_BASKET_INSIGHTS_14B2" || result.source_records_persisted!==false ||
    result.direct_identifiers_accepted!==false || result.cloud_model_used!==false ||
    result.purchase_allowed!==false || result.personalized_targeting_allowed!==false ||
    result.independently_verified!==false || !result.segmentation || !result.basket_analysis ||
    !Array.isArray(result.segmentation.segments) || !Array.isArray(result.basket_analysis.rules) ||
    !Array.isArray(result.limitations)) throw new Error("Cohort/basket safety contract is invalid.");
  return result;
}
