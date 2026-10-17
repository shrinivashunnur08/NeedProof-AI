"""Single Gemini gateway: AI Studio key, Vertex AI, or mock, chosen by providers.py."""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from pydantic import BaseModel

from app.commerce_loop.providers import Providers, get_providers

logger = logging.getLogger(__name__)


class GeminiUnavailable(Exception):
    pass


class Gemini:
    def __init__(self, providers: Providers | None = None):
        self.p = providers or get_providers()

    @property
    def is_mock(self) -> bool:
        return self.p.gemini_backend == "mock"

    def _client(self):
        from google import genai

        if self.p.gemini_backend == "ai_studio":
            if not self.p.gemini_api_key:
                raise GeminiUnavailable("GEMINI_API_KEY is not set")
            return genai.Client(api_key=self.p.gemini_api_key)
        if self.p.gemini_backend == "vertex":
            if not self.p.gcp_project:
                raise GeminiUnavailable("GOOGLE_CLOUD_PROJECT is not set")
            return genai.Client(vertexai=True, project=self.p.gcp_project, location=self.p.gcp_location)
        raise GeminiUnavailable(f"Unsupported GEMINI_BACKEND {self.p.gemini_backend}")

    def generate_json(self, prompt: str, schema: type[BaseModel], *, system: str,
                      image: tuple[bytes, str] | None = None) -> tuple[BaseModel, dict]:
        from google.genai import types

        started = time.perf_counter()
        client = self._client()
        parts: list[Any] = []
        if image:
            parts.append(types.Part.from_bytes(data=image[0], mime_type=image[1]))
        parts.append(prompt)
        try:
            resp = client.models.generate_content(
                model=self.p.gemini_model,
                contents=parts,
                config=types.GenerateContentConfig(
                    system_instruction=system, response_mime_type="application/json",
                    response_schema=schema, temperature=0.1, max_output_tokens=2048),
            )
        except Exception as exc:  # noqa: BLE001 - surface a clean error, never customer text
            logger.warning("Gemini JSON call failed (%s)", type(exc).__name__)
            raise GeminiUnavailable(f"Gemini call failed: {type(exc).__name__}") from exc
        parsed = resp.parsed if isinstance(resp.parsed, schema) else schema.model_validate_json(resp.text or "{}")
        return parsed, self._meta(resp, started)

    def run_agent(self, *, system: str, history: list[dict], tools: list[Callable]) -> tuple[str, dict]:
        """Multi-turn chat with automatic function calling over our Python tools."""
        from google.genai import types

        started = time.perf_counter()
        client = self._client()
        contents = [types.Content(role="model" if h["role"] == "assistant" else "user",
                                  parts=[types.Part(text=h["text"])]) for h in history if h.get("text")]
        try:
            resp = client.models.generate_content(
                model=self.p.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system, tools=tools, temperature=0.3, max_output_tokens=1500,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=6)),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini agent call failed (%s)", type(exc).__name__)
            raise GeminiUnavailable(f"Gemini call failed: {type(exc).__name__}") from exc
        return (resp.text or "").strip(), self._meta(resp, started)

    def _meta(self, resp, started: float) -> dict:
        usage = getattr(resp, "usage_metadata", None)
        return {
            "backend": self.p.gemini_backend,
            "model": self.p.gemini_model,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "input_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
        }
