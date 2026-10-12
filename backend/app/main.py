
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from app.api.intent import router as intent_router
from app.api.catalog import router as catalog_router
from app.api.places import router as places_router
from app.api.verification import router as verification_router
from app.api.decisions import router as decisions_router
app = FastAPI(
    title="NeedProof AI API",
    description="Evidence-driven commerce intelligence",
    version="0.1.0",
)
app.include_router(intent_router)
app.include_router(catalog_router)
app.include_router(places_router)
app.include_router(verification_router)
app.include_router(decisions_router)

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
