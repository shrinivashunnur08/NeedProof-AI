
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="NeedProof AI API",
    description="Evidence-driven commerce intelligence",
    version="0.1.0",
)

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
