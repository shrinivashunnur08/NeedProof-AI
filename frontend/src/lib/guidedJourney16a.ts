import { getAuth, signInAnonymously } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";

export const guidedJourney16aEnabled = import.meta.env.VITE_GUIDED_JOURNEY_16A_ENABLED === "true";
export type Scenario16A = "reported_offer" | "stockout" | "document_conflict" | "no_merchants";
export type JourneyStep16A = {stage: string; status: string; state: string; source: string};
export type JourneyResult16A = {
  mode: "GUIDED_EVIDENCE_JOURNEY_16A";
  scenario: Scenario16A; title: string; product: string;
  fixture_origin: "SERVER_OWNED_SYNTHETIC_NOT_REAL_MERCHANTS";
  workflow: {
    workflow_state: string; recommended_next_action: string; reason: string;
    workflow_trace: JourneyStep16A[];
    change_detection:{comparison:string;changed:boolean|null;changes:Array<{event:string;place_id:string|null}>};
    merchant_replanning:{decision_status:string; selected: unknown; candidates:Array<{place_id:string;status:string}>};
    product_research: {review:{status:string}; sources_verified:false} | null;
    hypothetical_verification_plan:{recommended_action_id:string|null;calibration_status:string}|null;
    synthetic_basket_scenario:{scenario_status:string;purchase_allowed:false}|null;
    purchase_allowed:false; merchant_contact_performed:false; stock_independently_verified:false;
    gemini_used:false;
  };
  separate_illustrative_business_context: {
    coverage:{available_modules:number;total_modules:number}; executive_summary:string;
    metrics:Array<{key:string;label:string;value:number;unit:string}>;
    review_queue:Array<{key:string;title:string;priority:number;reason:string}>;
    purchase_allowed:false; data_origin:string;
  } | null;
  business_context_is_derived_from_customer_journey:false;
  journey_is_historical_verified_record:false; real_merchant_contact:false;
  stock_independently_verified:false;purchase_allowed:false;cloud_model_used:false;
  database_used:false;source_records_persisted:false;limitations:string[];
};

export async function runGuidedJourney16A(scenario:Scenario16A, includeBusiness:boolean, signal?:AbortSignal):Promise<JourneyResult16A>{
  if(!guidedJourney16aEnabled) throw new Error("Guided journey disabled in this build.");
  if(!cloudApiUrl || (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl)))
    throw new Error("A configured secure API URL is required.");
  const {app,appCheck}=firebaseShowcaseClients();
  const auth=getAuth(app);await auth.authStateReady();
  const user=auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [idToken,appToken]=await Promise.all([user.getIdToken(),getToken(appCheck)]);
  if(!appToken.token) throw new Error("App Check token unavailable.");
  const response=await fetch(`${cloudApiUrl}/api/v1/demo/guided-journey`,{
    method:"POST",cache:"no-store",signal,
    headers:{"Content-Type":"application/json","Authorization":`Bearer ${idToken}`,
      "X-Firebase-AppCheck":appToken.token},
    body:JSON.stringify({scenario, include_illustrative_business_context:includeBusiness, simulation_acknowledged:true}),
  });
  if(!response.ok) throw new Error(response.status===503?"Guided demo disabled on the backend.":
    response.status===401?"Firebase Auth or App Check failed.":
    response.status===413?"Demo request exceeded the API size limit.":
    response.status===422?"Invalid synthetic scenario.":
    `Guided demo API HTTP ${response.status}`);
  const raw:unknown=await response.json();
  if(!raw||typeof raw!=="object") throw new Error("Invalid guided journey response.");
  const data=raw as JourneyResult16A;
  if(data.mode!=="GUIDED_EVIDENCE_JOURNEY_16A" || data.fixture_origin!=="SERVER_OWNED_SYNTHETIC_NOT_REAL_MERCHANTS" ||
      data.purchase_allowed!==false ||data.real_merchant_contact!==false||data.stock_independently_verified!==false||
      data.cloud_model_used!==false||data.database_used!==false||data.source_records_persisted!==false||
      data.business_context_is_derived_from_customer_journey!==false || data.journey_is_historical_verified_record!==false ||
      data.workflow?.purchase_allowed!==false||data.workflow?.gemini_used!==false||
      !Array.isArray(data.workflow?.workflow_trace)||!Array.isArray(data.limitations) ||
      (data.separate_illustrative_business_context!==null&&data.separate_illustrative_business_context?.purchase_allowed!==false)){
    throw new Error("Guided journey safety contract failed; result withheld.");
  }
  return data;
}
