"""ASGI HTTP request-size and response-header hardening for the NeedProof demo.

A scoped, *per-request* body cap prevents bypassing Content-Length checks by
streaming or chunked uploads. This is neither a distributed rate limiter nor
protection against slow-client attacks: retain upstream Cloud Run/edge limits.
No request, token, body, user identifier or raw sales data is logged/stored.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

MAX_BODY_BYTES = 32_768
_SECURITY_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"cache-control", b"no-store"),
)


class BoundedAPIGuard15A:
    """Pure ASGI middleware: cap POST/PUT/PATCH bodies before request parsing.

    Appended as the last FastAPI middleware registration to ensure it also
    covers responses rejected by the existing Content-Length middleware.
    """

    def __init__(self, app: Callable[..., Any], max_body_bytes: int = MAX_BODY_BYTES):
        if max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive")
        self.app = app
        self.limit = max_body_bytes

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def safe_send(message: dict) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {k.lower() for k, _ in headers}
                headers.extend((k, v) for k, v in _SECURITY_HEADERS if k not in existing)
                message = {**message, "headers": headers}
            await send(message)

        async def reject(status: int, text: str) -> None:
            raw = json.dumps({"detail": text}, separators=(",", ":")).encode("utf-8")
            await safe_send({
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(raw)).encode("ascii"))],
            })
            await safe_send({"type": "http.response.body", "body": raw})

        if scope.get("method", "").upper() not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, safe_send)
            return

        lengths = [v for k, v in scope.get("headers", []) if k.lower() == b"content-length"]
        if len(lengths) > 1:
            await reject(400, "Invalid content length")
            return
        if lengths:
            try:
                raw_length = lengths[0].decode("ascii")
                if not raw_length.isdecimal():
                    raise ValueError
                content_length = int(raw_length)
            except (UnicodeDecodeError, ValueError):
                await reject(400, "Invalid content length")
                return
            if content_length > self.limit:
                await reject(413, "Request too large")
                return

        body = bytearray()
        # Read up to MAX_BODY_BYTES+1, not an arbitrary entire request.
        while True:
            message = await receive()
            if message.get("type") == "http.disconnect":
                return
            if message.get("type") != "http.request":
                # Ignore unrelated ASGI extension messages; no request data stored.
                continue
            chunk = message.get("body", b"") or b""
            if not isinstance(chunk, bytes):
                await reject(400, "Invalid request body")
                return
            if len(chunk) > self.limit - len(body):
                await reject(413, "Request too large")
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive() -> dict:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, safe_send)
