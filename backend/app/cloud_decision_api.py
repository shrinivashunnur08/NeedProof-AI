"""Isolated public Cloud Run API. Does not mount any local-only routes.

Client snapshots are unverified; this service never authorizes purchases.
"""

import os
import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.algorithms.adaptive_replanning import ReplanInput, evaluate_replan
from app.api.decisions import demo_evidence_plan
from app.public_places import DiscoveryInput, discover_stores
from app.product_grounding_13c1 import ReviewInput, review_product
from app.product_retrieval_13c2 import RetrievalInput, retrieve_and_review
from app.evidence_planner_14a1 import EvidencePlanInput14A1, evaluate_evidence_plan
from app.basket_optimizer_14a2 import BasketPlan14A2, evaluate_basket_14a2
from app.decision_orchestrator_14a3 import OrchestrationInput14A3, orchestrate_decision_14a3
from app.retail_forecast_14b1 import ForecastInput14B1, evaluate_retail_forecast_14b1
from app.retail_segments_14b2 import CommerceInsightsInput14B2, evaluate_commerce_insights_14b2
from app.inventory_intelligence_14b3 import InventoryInput14B3, evaluate_inventory_14b3
from app.bi_command_center_14b4 import BIInput14B4, evaluate_bi_command_center_14b4
from app.merchant_evidence_13b import router as evidence_13b_router


FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "").strip()
FIREBASE_WEB_APP_ID = os.environ.get("FIREBASE_WEB_APP_ID", "").strip()
ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app = FastAPI(
    title="NeedProof AI — Decision API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"],
    max_age=3600,
)


@app.middleware("http")
async def reject_oversized_bodies(request: Request, call_next):
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > 32_768:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Invalid content length"}, status_code=400)
    return await call_next(request)


@lru_cache(maxsize=1)
def _firebase_app():
    if not FIREBASE_PROJECT_ID or not FIREBASE_WEB_APP_ID:
        raise RuntimeError("FIREBASE_PROJECT_ID/FIREBASE_WEB_APP_ID missing")
    import firebase_admin
    try:
        return firebase_admin.get_app("needproof-public-api")
    except ValueError:
        return firebase_admin.initialize_app(
            options={"projectId": FIREBASE_PROJECT_ID},
            name="needproof-public-api",
        )


def require_firebase_client(
    authorization: Annotated[str | None, Header()] = None,
    x_firebase_appcheck: Annotated[str | None, Header()] = None,
) -> str:
    """Validate Firebase Auth ID token AND App Check token, fail closed."""
    if not authorization or not authorization.startswith("Bearer ") or not x_firebase_appcheck:
        raise HTTPException(status_code=401, detail="Authentication and App Check required")

    try:
        from firebase_admin import app_check, auth
        firebase_app = _firebase_app()
        decoded_user = auth.verify_id_token(
            authorization.removeprefix("Bearer ").strip(), app=firebase_app
        )
        decoded_app = app_check.verify_token(x_firebase_appcheck, app=firebase_app)
        if decoded_app.get("app_id") != FIREBASE_WEB_APP_ID:
            raise ValueError("App Check application does not match")
        uid = decoded_user.get("uid")
        if not isinstance(uid, str) or not uid:
            raise ValueError("Missing Firebase UID")
        return uid
    except Exception as exc:
        # Only the exception CLASS is logged; never log tokens or user content.
        logging.warning("NeedProof Firebase token verification failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=401, detail="Invalid authentication") from exc


Identity = Annotated[str, Depends(require_firebase_client)]


# SQL backend remains the default for existing local tests and tooling.
# Firestore requires explicit deployment configuration; no automatic migration.
if os.environ.get("MERCHANT_EVIDENCE_STORAGE", "").strip().lower() == "firestore":
    from app.evidence_firestore_13b2 import router as evidence_13b_router
app.include_router(evidence_13b_router)


@app.post("/api/v1/analytics/command-center")
def bi_command_center_14b4(payload: BIInput14B4, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("BI_COMMAND_CENTER_14B4_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="BI command center is disabled")
    return evaluate_bi_command_center_14b4(payload)


@app.post("/api/v1/analytics/inventory-review")
def inventory_review_14b3(payload: InventoryInput14B3, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("INVENTORY_INTELLIGENCE_14B3_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Inventory intelligence is disabled")
    return evaluate_inventory_14b3(payload)


@app.post("/api/v1/analytics/cohort-basket-insights")
def cohort_and_basket_insights_14b2(payload: CommerceInsightsInput14B2, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("RETAIL_INSIGHTS_14B2_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Retail cohort/basket analysis is disabled")
    return evaluate_commerce_insights_14b2(payload)


@app.post("/api/v1/analytics/sales-forecast")
def bounded_sales_forecast_14b1(payload: ForecastInput14B1, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("RETAIL_FORECAST_14B1_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Retail forecasting is disabled")
    return evaluate_retail_forecast_14b1(payload)


@app.post("/api/v1/decision/orchestrate")
def evidence_orchestration_14a3(payload: OrchestrationInput14A3, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("DECISION_ORCHESTRATOR_14A3_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Evidence orchestration is disabled")
    try:
        return orchestrate_decision_14a3(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/commerce/basket-plan")
def basket_scenario_plan(payload: BasketPlan14A2, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("BASKET_OPTIMIZER_14A2_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Basket scenario planner is disabled")
    return evaluate_basket_14a2(payload)


@app.post("/api/v1/decision/evidence-plan")
def hypothetical_evidence_plan(payload: EvidencePlanInput14A1, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("EVIDENCE_PLANNER_14A1_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Evidence verification planning is not enabled")
    try:
        return evaluate_evidence_plan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/products/research")
def product_evidence_research(payload: RetrievalInput, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("PRODUCT_RETRIEVAL_13C2_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Document research is not enabled")
    return retrieve_and_review(payload)


@app.post("/api/v1/products/grounded-review")
def product_grounding_review(payload: ReviewInput, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if os.environ.get("PRODUCT_GROUNDING_13C1_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="Product evidence review is not enabled")
    return review_product(payload)


@app.post("/api/v1/discovery/stores")
async def candidate_store_discovery(payload: DiscoveryInput, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return await discover_stores(payload, user_id)


@app.get("/health")
def health():
    return {"status": "ok", "component": "needproof-decision-api"}


@app.post("/api/v1/decision/replan")
def replan(payload: ReplanInput, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    # uid intentionally not logged or stored; request is a client-supplied snapshot.
    return evaluate_replan(payload)


class PlanInput(BaseModel):
    budget_inr: int = Field(default=1000, ge=100, le=10000)
    deadline_minutes: int = Field(default=15, ge=0, le=120)
    a_verification_cost_inr: int = Field(default=8, ge=0, le=1000)
    a_prior: float = Field(default=0.65, ge=0, le=1)
    a_response_probability: float = Field(default=0.8, ge=0, le=1)


@app.post("/api/v1/decision/verification-plan")
def verification_plan(payload: PlanInput, user_id: Identity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return demo_evidence_plan(
        budget_inr=payload.budget_inr,
        deadline_minutes=payload.deadline_minutes,
        a_verification_cost_inr=payload.a_verification_cost_inr,
        a_prior=payload.a_prior,
        a_response_probability=payload.a_response_probability,
    )
