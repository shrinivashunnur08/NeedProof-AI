import { getAuth, signInAnonymously } from "firebase/auth";
import { getToken } from "firebase/app-check";
import { cloudApiUrl, firebaseShowcaseClients } from "./cloudDecisions";

export const retailForecast14b1Enabled = import.meta.env.VITE_RETAIL_FORECAST_14B1_ENABLED === "true";

export type DailySales14B1 = { day: string; units_sold: number; reported_stockout: boolean };
export type RetailForecast14B1 = {
  mode: "LOCAL_BASELINES_14B1";
  product_label: string;
  data_origin: "CLIENT_LABELED_SYNTHETIC_DEMO" | "USER_SUPPLIED_UNVERIFIED";
  target: "OBSERVED_UNIT_SALES_AS_DEMAND_PROXY";
  training_observations: number;
  holdout_origin_count: number;
  holdout_method: string;
  selected_model: string;
  model_comparison: Array<{method:string;mae_units:number;wape_pct:number|null;mean_signed_error_units:number;evaluated_forecast_points:number;rolling_origins:number}>;
  predictions: Array<{day:string;expected_units:number;lower_heuristic_80:number|null;upper_heuristic_80:number|null}>;
  reported_stockout_days:number;
  inventory_exposure_scenario: null | {
    reported_on_hand_units:number;lead_days:number;
    projected_sales_units_before_replenishment:number;projected_shortfall_units:number;interpretation:string;
  };
  limitations:string[];
  observations_persisted:false;
  cloud_model_used:false;
  forecast_independently_verified:false;
  purchase_allowed:false;
};

export async function forecastRetail14b1(input: {
  product_label: string; history: DailySales14B1[]; horizon_days: number;
  on_hand_units: number | null; replenishment_lead_days: number | null;
  synthetic_demo: boolean;
}): Promise<RetailForecast14B1> {
  if (!retailForecast14b1Enabled) throw new Error("14B.1 forecasting is disabled in this build.");
  if (!cloudApiUrl || (!cloudApiUrl.startsWith("https://") && !/^http:\/\/localhost(?::\d+)?$/.test(cloudApiUrl))) {
    throw new Error("A secure backend URL is required.");
  }
  const {app, appCheck} = firebaseShowcaseClients();
  const auth = getAuth(app);
  await auth.authStateReady();
  const user = auth.currentUser ?? (await signInAnonymously(auth)).user;
  const [idToken, appToken] = await Promise.all([user.getIdToken(), getToken(appCheck)]);
  if (!appToken.token) throw new Error("App Check token unavailable.");
  const response = await fetch(`${cloudApiUrl}/api/v1/analytics/sales-forecast`, {
    method: "POST", cache: "no-store", headers: {
      "Content-Type":"application/json", "Authorization":`Bearer ${idToken}`,
      "X-Firebase-AppCheck":appToken.token,
    }, body:JSON.stringify(input),
  });
  if (!response.ok) throw new Error(response.status === 503 ? "Forecast endpoint is disabled on the backend." :
    response.status === 401 ? "Firebase authentication / App Check failed." :
    response.status === 422 ? "Sales history or input constraints are invalid." :
    `Sales forecast API HTTP ${response.status}`);
  const value:unknown = await response.json();
  if (!value || typeof value !== "object") throw new Error("Invalid forecast response.");
  const result = value as RetailForecast14B1;
  if (result.mode !== "LOCAL_BASELINES_14B1" || result.purchase_allowed !== false ||
    result.cloud_model_used !== false || result.observations_persisted !== false ||
    result.forecast_independently_verified !== false || !Array.isArray(result.predictions) ||
    !Array.isArray(result.model_comparison) || !Array.isArray(result.limitations)) {
    throw new Error("Forecast safety contract is invalid.");
  }
  return result;
}
