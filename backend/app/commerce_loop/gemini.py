"""Single Gemini gateway: AI Studio key, Vertex AI, or mock, chosen by providers.py."""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from pydantic import BaseModel

from app.commerce_loop.providers import Providers, get_providers, setting

logger = logging.getLogger(__name__)


class GeminiUnavailable(Exception):
    pass


def _describe(exc: Exception) -> str:
    """Status code and Google's error message only; never echoes the prompt or customer text."""
    code = getattr(exc, "code", None)
    status = getattr(exc, "status", None)
    message = str(getattr(exc, "message", "") or "")[:200]
    return " ".join(str(x) for x in (type(exc).__name__, code, status, message) if x)


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
            return genai.Client(api_key=self.p.gemini_api_key, http_options=self._http())
        if self.p.gemini_backend == "vertex":
            if not self.p.gcp_project:
                raise GeminiUnavailable("GOOGLE_CLOUD_PROJECT is not set")
            return genai.Client(vertexai=True, project=self.p.gcp_project, location=self.p.gcp_location,
                                http_options=self._http())
        raise GeminiUnavailable(f"Unsupported GEMINI_BACKEND {self.p.gemini_backend}")

    @staticmethod
    def _http():
        from google.genai import types

        return types.HttpOptions(timeout=int(setting("LOOP_GEMINI_TIMEOUT_MS", "40000")))

    @staticmethod
    def _thinking():
        """Low thinking keeps the shopper chat fast; set LOOP_THINKING=off to omit the setting."""
        from google.genai import types

        level = setting("LOOP_THINKING", "low").lower()
        if level == "off":
            return None
        if "thinking_level" in types.ThinkingConfig.model_fields:
            return types.ThinkingConfig(thinking_level=level)
        return types.ThinkingConfig(thinking_budget=0 if level in {"low", "minimal"} else -1)

    def _generate(self, client, **kwargs):
        """Call Gemini; if the model rejects the thinking setting, retry once without it."""
        try:
            return client.models.generate_content(**kwargs)
        except Exception as exc:  # noqa: BLE001
            config = kwargs.get("config")
            if getattr(exc, "code", None) == 400 and getattr(config, "thinking_config", None) is not None:
                kwargs["config"] = config.model_copy(update={"thinking_config": None})
                return client.models.generate_content(**kwargs)
            raise

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
            resp = self._generate(
                client,
                model=self.p.gemini_model,
                contents=parts,
                config=types.GenerateContentConfig(
                    system_instruction=system, response_mime_type="application/json",
                    response_schema=schema, temperature=0.1, max_output_tokens=2048,
                    thinking_config=self._thinking()),
            )
        except Exception as exc:  # noqa: BLE001 - surface a clean error, never customer text
            logger.warning("Gemini JSON call failed (%s)", type(exc).__name__)
            raise GeminiUnavailable(f"Gemini call failed: {_describe(exc)}") from exc
        parsed = resp.parsed if isinstance(resp.parsed, schema) else schema.model_validate_json(resp.text or "{}")
        return parsed, self._meta(resp, started)

    def run_agent(self, *, system: str, history: list[dict], tools: list[Callable],
                  max_steps: int = 5) -> tuple[str, dict]:
        """Multi-turn chat with an explicit function-calling loop over our Python tools.

        Gemini proposes tool calls; we execute them and return results until it answers in text.
        """
        from google.genai import types

        started = time.perf_counter()
        client = self._client()
        by_name = {t.__name__: t for t in tools}
        declarations = [types.FunctionDeclaration.from_callable(client=client, callable=t) for t in tools]
        config = types.GenerateContentConfig(
            system_instruction=system, temperature=0.3, max_output_tokens=2048,
            tools=[types.Tool(function_declarations=declarations)], thinking_config=self._thinking(),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        contents: list[Any] = [types.Content(role="model" if h["role"] == "assistant" else "user",
                                             parts=[types.Part(text=h["text"])]) for h in history if h.get("text")]
        steps, tokens_in, tokens_out = 0, 0, 0
        text = ""
        for _ in range(max_steps):
            try:
                resp = self._generate(client, model=self.p.gemini_model, contents=contents, config=config)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini agent call failed (%s)", type(exc).__name__)
                raise GeminiUnavailable(f"Gemini call failed: {_describe(exc)}") from exc
            usage = getattr(resp, "usage_metadata", None)
            tokens_in += getattr(usage, "prompt_token_count", 0) or 0
            tokens_out += getattr(usage, "candidates_token_count", 0) or 0
            calls = resp.function_calls or []
            if not calls:
                text = (resp.text or "").strip()
                break
            # Keep the model turn as-is (preserves thought signatures), then answer each call.
            contents.append(resp.candidates[0].content)
            parts = []
            for call in calls:
                steps += 1
                fn = by_name.get(call.name)
                try:
                    result = fn(**dict(call.args or {})) if fn else {"error": f"Unknown tool {call.name}"}
                except TypeError as exc:
                    result = {"error": f"Bad arguments: {exc}"}
                parts.append(types.Part.from_function_response(name=call.name, response={"result": result}))
            contents.append(types.Content(role="user", parts=parts))
        meta = {"backend": self.p.gemini_backend, "model": self.p.gemini_model,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "input_tokens": tokens_in, "output_tokens": tokens_out, "tool_calls": steps}
        return text, meta

    def _meta(self, resp, started: float) -> dict:
        usage = getattr(resp, "usage_metadata", None)
        return {
            "backend": self.p.gemini_backend,
            "model": self.p.gemini_model,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "input_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
        }
