import os
from pathlib import Path
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from app.config import get_settings
from app.api.intent import router as intent_router
from app.api.catalog import router as catalog_router
from app.api.places import router as places_router
from app.api.verification import router as verification_router
from app.api.decisions import router as decisions_router
from app.api.optimization import router as optimization_router
from app.api.advisory import router as advisory_router
from app.api.assurance import router as assurance_router
from app.api.technical_review import router as technical_router
from app.api.merchant_onboarding import router as onboarding_router
from app.api.transactions import router as transactions_router
from app.api.benchmarks import router as benchmarks_router
from app.api.journey import router as journey_router
from app.fresh_journey_17c import FreshJourney17C, evaluate_fresh_journey_17c
app = FastAPI(
    title="NeedProof AI API",
    description="Evidence-driven commerce intelligence",
    version="0.1.0",
)

CLOUD_PREVIEW_ALLOWED_API_PATHS = {
    "/api/health",
    "/api/decisions/demo-plan",
    "/api/optimization/demo-plan",
}


@app.middleware("http")
async def cloud_preview_guard(request: Request, call_next):
    preview_mode = (
        os.environ.get(
            "NEEDPROOF_CLOUD_PREVIEW", "false"
        ).lower() == "true"
    )

    # The legacy intent endpoint has no Firebase auth. Never make a paid
    # Gemini invocation through this development-only route in production.
    if (request.url.path == "/api/intent/extract" and
            (os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
             or get_settings().environment == "production")):
        return JSONResponse(status_code=403, content={"detail": "Local intent endpoint disabled in production"})

    if preview_mode:
        path = request.url.path

        if path in {
            "/docs",
            "/redoc",
            "/openapi.json",
        }:
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found"},
            )

        if (
            path.startswith("/api/")
            and path not in CLOUD_PREVIEW_ALLOWED_API_PATHS
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "This API is disabled in the "
                        "cloud preview environment."
                    )
                },
            )

    return await call_next(request)

app.include_router(intent_router)
app.include_router(catalog_router)
app.include_router(places_router)
app.include_router(verification_router)
app.include_router(decisions_router)
app.include_router(optimization_router)
app.include_router(advisory_router)
app.include_router(assurance_router)
app.include_router(technical_router)
app.include_router(onboarding_router)
app.include_router(transactions_router)
app.include_router(benchmarks_router)
app.include_router(journey_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.post("/api/v1/demo/fresh-journey")
def local_fresh_journey_17c(payload: FreshJourney17C, request: Request):
    """LOCAL ONLY. Never available to a remote client or production instance.

    Use `uvicorn app.main:app --host 127.0.0.1 --port 8000` plus explicit
    NEEDPROOF_17C_LOCAL_ENABLED=true. Do not expose this dev app on 0.0.0.0.
    """
    enabled = os.environ.get("NEEDPROOF_17C_LOCAL_ENABLED", "false").strip().lower() == "true"
    production = (os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
                  or get_settings().environment == "production")
    local_client = request.client is not None and request.client.host in {"127.0.0.1", "::1"}
    if not enabled or production or not local_client:
        raise HTTPException(status_code=403, detail="Local development route unavailable")
    return JSONResponse(evaluate_fresh_journey_17c(payload), headers={"Cache-Control": "no-store"})


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "application": "NeedProof AI",
        "version": "0.1.0",
    }


class RequestPreview(BaseModel):
    text: str = Field(min_length=8, max_length=2000)


@app.post("/api/requests/preview")
def preview_request(request: RequestPreview):
    return {
        "status": "accepted_preview",
        "customer_text": request.text,
        "message": (
            "Request received by FastAPI. "
            "Gemini extraction and database storage "
            "will be implemented in upcoming chunks."
        ),
    }

# ------------------------------------------------------------------
# Cloud Run: serve the compiled Vite application.
# During local development this folder does not exist,
# so the existing Vite dev server continues to be used.
# ------------------------------------------------------------------

FRONTEND_DIST = Path(
    os.environ.get(
        "FRONTEND_DIST_DIR",
        "/srv/frontend_dist",
    )
)

if FRONTEND_DIST.is_dir():
    ASSETS_DIR = FRONTEND_DIST / "assets"

    if ASSETS_DIR.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=ASSETS_DIR),
            name="frontend_assets",
        )

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def serve_frontend(frontend_path: str):
        # Don't convert missing API routes to React HTML.
        if (
            frontend_path == "api"
            or frontend_path.startswith("api/")
            or frontend_path in (
                "docs",
                "redoc",
                "openapi.json",
            )
        ):
            raise HTTPException(status_code=404)

        candidate = (
            FRONTEND_DIST / frontend_path
        ).resolve()

        base = FRONTEND_DIST.resolve()

        if (
            candidate.is_relative_to(base)
            and candidate.is_file()
        ):
            return FileResponse(candidate)

        # Supports client-side routes such as:
        # /verify/<request_id>
        return FileResponse(
            FRONTEND_DIST / "index.html"
        )
