"""One switchboard for every external service.

`NEEDPROOF_PROFILE=free` (default) uses no-cost services; `google_full` switches
defaults to Vertex AI and BigQuery. Each component can still be overridden.
Tests force `GEMINI_BACKEND=mock`, so CI never spends money.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_PROFILE_DEFAULTS = {
    "free": {"gemini": "ai_studio", "analytics": "local", "media": "local"},
    "google_full": {"gemini": "vertex", "analytics": "bigquery", "media": "gcs"},
}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _dotenv_value(name: str) -> str:
    """Read a key from backend/.env when it was not exported (uvicorn does not load .env)."""
    path = Path(__file__).resolve().parents[2] / ".env"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def setting(name: str, default: str = "") -> str:
    return _env(name) or _dotenv_value(name) or default


@dataclass(frozen=True)
class Providers:
    profile: str
    gemini_backend: str
    gemini_model: str
    gemini_api_key: str
    gcp_project: str
    gcp_location: str
    analytics_backend: str
    media_store: str
    bigquery_dataset: str

    def public_status(self) -> dict:
        live = self.gemini_backend in {"ai_studio", "vertex"} and self.gemini_ready
        return {
            "profile": self.profile,
            "gemini": {
                "backend": self.gemini_backend,
                "model": self.gemini_model,
                "ready": self.gemini_ready,
                "label": {
                    "ai_studio": "Gemini API (AI Studio)",
                    "vertex": "Gemini on Vertex AI",
                    "mock": "Mock model (offline)",
                }.get(self.gemini_backend, self.gemini_backend),
            },
            "analytics": {"backend": self.analytics_backend,
                          "label": {"local": "Local SQLite + BigQuery export",
                                    "bigquery": "BigQuery"}.get(self.analytics_backend, self.analytics_backend)},
            "media": {"backend": self.media_store},
            "live_model": live,
        }

    @property
    def gemini_ready(self) -> bool:
        if self.gemini_backend == "mock":
            return True
        if self.gemini_backend == "ai_studio":
            return bool(self.gemini_api_key)
        if self.gemini_backend == "vertex":
            return bool(self.gcp_project)
        return False


def get_providers() -> Providers:
    profile = setting("NEEDPROOF_PROFILE", "free")
    defaults = _PROFILE_DEFAULTS.get(profile, _PROFILE_DEFAULTS["free"])
    backend = setting("GEMINI_BACKEND", defaults["gemini"]).lower()
    api_key = setting("GEMINI_API_KEY") or setting("GOOGLE_API_KEY")
    # Free profile without a key falls back to the mock so the app still runs.
    if backend == "ai_studio" and not api_key and not _env("GEMINI_BACKEND") and not _dotenv_value("GEMINI_BACKEND"):
        backend = "mock"
    project = setting("GOOGLE_CLOUD_PROJECT")
    if project.startswith("YOUR_"):
        project = ""
    return Providers(
        profile=profile,
        gemini_backend=backend,
        gemini_model=setting("LOOP_GEMINI_MODEL", "gemini-flash-lite-latest"),
        gemini_api_key=api_key,
        gcp_project=project,
        gcp_location=setting("GOOGLE_CLOUD_LOCATION", "global"),
        analytics_backend=setting("ANALYTICS_BACKEND", defaults["analytics"]).lower(),
        media_store=setting("MEDIA_STORE", defaults["media"]).lower(),
        bigquery_dataset=setting("BIGQUERY_DATASET", "needproof_loop"),
    )
