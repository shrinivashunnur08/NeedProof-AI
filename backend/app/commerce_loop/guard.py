"""Spend guard for the public demo: per-visitor rate limit and a daily cap on AI calls.

On by default only when LOOP_RATE_LIMIT=true (set on Cloud Run). In-memory, per instance: run the public
service with max-instances 1-2 so the cap stays meaningful. The cap protects the Gemini bill; the
Google Cloud budget alert only warns.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import date

from fastapi import HTTPException, Request

from app.commerce_loop.providers import setting

_LOCK = threading.Lock()
_HITS: dict[str, deque] = defaultdict(deque)
_DAY = {"day": date.today(), "count": 0}


def _enabled() -> bool:
    return setting("LOOP_RATE_LIMIT", "false").lower() == "true"


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else "") or (request.client.host if request.client else "unknown")


def ai_call_guard(request: Request) -> None:
    """FastAPI dependency for endpoints that call Gemini, BigQuery AI or map services."""
    if not _enabled():
        return
    per_min = int(setting("LOOP_RATE_PER_MIN", "20"))
    daily = int(setting("LOOP_DAILY_AI_CAP", "1500"))
    now = time.monotonic()
    ip = _client_ip(request)
    with _LOCK:
        if _DAY["day"] != date.today():
            _DAY.update(day=date.today(), count=0)
        if _DAY["count"] >= daily:
            raise HTTPException(status_code=429, detail="The demo reached today's AI limit. Please try again tomorrow.")
        hits = _HITS[ip]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= per_min:
            raise HTTPException(status_code=429, detail="Too many requests; please wait a minute.",
                                headers={"Retry-After": "30"})
        hits.append(now)
        _DAY["count"] += 1


def reset() -> None:
    with _LOCK:
        _HITS.clear()
        _DAY.update(day=date.today(), count=0)


def usage() -> dict:
    return {"enabled": _enabled(), "ai_calls_today": _DAY["count"],
            "daily_cap": int(setting("LOOP_DAILY_AI_CAP", "1500")),
            "per_minute": int(setting("LOOP_RATE_PER_MIN", "20"))}
