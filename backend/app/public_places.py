"""NeedProof public Places discovery: candidate businesses only, never inventory evidence.

Google Maps content is returned for immediate presentation only; do not persist
business names, addresses, or URLs to Firestore/SQLite/analytics. Place IDs
are the documented exception to caching restrictions.
"""
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator

PLACES_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = "places.id,places.displayName.text,places.formattedAddress,places.googleMapsUri"
WINDOW_SECONDS = 300
MAX_PER_USER = 3
MAX_PER_INSTANCE = 30
_recent_users: dict[str, deque[float]] = defaultdict(deque)
_recent_all: deque[float] = deque()
_gate = Lock()


class DiscoveryInput(BaseModel):
    product_query: str = Field(min_length=3, max_length=120)
    area: str = Field(min_length=2, max_length=80)

    @field_validator("product_query", "area")
    @classmethod
    def clean(cls, value: str) -> str:
        result = " ".join(value.strip().split())
        if not result or any(ord(char) < 32 for char in result):
            raise ValueError("Enter normal search text")
        return result


class CandidatePlace(BaseModel):
    place_id: str
    name: str
    address: str
    maps_url: str | None = None
    inventory_status: str = "UNKNOWN"
    verification_status: str = "NOT_VERIFIED"


class DiscoveryOutput(BaseModel):
    source: str = "GOOGLE_PLACES_NEW"
    status: str = "CANDIDATES_ONLY"
    stores: list[CandidatePlace]
    disclaimer: str = (
        "Google Places identifies candidate businesses. It does not confirm stock, "
        "product compatibility, merchant identity, price, delivery, or a purchase commitment."
    )


def enforce_rate_limit(uid: str) -> None:
    """Best-effort per-instance throttle; ALSO configure a GCP Places API quota.

    No paid upstream call can occur when this local limiter denies a request.
    It is NOT a distributed or durable security control.
    """
    now = time.monotonic()
    with _gate:
        while _recent_all and now - _recent_all[0] > WINDOW_SECONDS:
            _recent_all.popleft()
        user = _recent_users[uid]
        while user and now - user[0] > WINDOW_SECONDS:
            user.popleft()
        if len(user) >= MAX_PER_USER or len(_recent_all) >= MAX_PER_INSTANCE:
            raise HTTPException(status_code=429, detail="Discovery rate limit reached. Please retry later.")
        user.append(now)
        _recent_all.append(now)


def _get_oauth_token() -> str:
    """Use the Cloud Run runtime service account; never ship a Places API key."""
    import google.auth
    from google.auth.transport.requests import Request as GoogleAuthRequest

    credentials, _project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/maps-platform.places.textsearch"]
    )
    if not credentials.valid:
        credentials.refresh(GoogleAuthRequest())
    if not credentials.token:
        raise RuntimeError("Google service account credentials have no token")
    return str(credentials.token)


async def _call_places(query: str) -> dict[str, Any]:
    from starlette.concurrency import run_in_threadpool

    token = await run_in_threadpool(_get_oauth_token)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-FieldMask": FIELD_MASK,
    }
    async with httpx.AsyncClient(timeout=9.0) as client:
        response = await client.post(
            PLACES_ENDPOINT,
            json={"textQuery": query, "pageSize": 5, "languageCode": "en"},
            headers=headers,
        )
    if response.status_code == 429:
        raise HTTPException(status_code=503, detail="Places quota temporarily unavailable")
    if response.status_code >= 400:
        logging.warning("Google Places request failed with status %s", response.status_code)
        raise HTTPException(status_code=502, detail="Places discovery unavailable")
    payload = response.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Places response invalid")
    return payload


def parse_places(payload: dict[str, Any]) -> DiscoveryOutput:
    raw = payload.get("places", [])
    if not isinstance(raw, list):
        raise ValueError("Places list missing")
    candidates: list[CandidatePlace] = []
    seen: set[str] = set()
    for entry in raw[:5]:
        if not isinstance(entry, dict):
            continue
        place_id = entry.get("id")
        display = entry.get("displayName")
        name = display.get("text") if isinstance(display, dict) else None
        if not isinstance(place_id, str) or not place_id.strip() or place_id in seen:
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        seen.add(place_id)
        raw_url = entry.get("googleMapsUri")
        # Don't send arbitrary upstream URLs to a browser-controlled link.
        maps_url = raw_url if isinstance(raw_url, str) and (
            raw_url.startswith("https://www.google.com/maps/")
            or raw_url.startswith("https://maps.google.com/")
            or raw_url.startswith("https://maps.app.goo.gl/")
        ) else None
        if maps_url is None:
            maps_url = (
                "https://www.google.com/maps/search/?api=1&query="
                + quote(name, safe="") + "&query_place_id=" + quote(place_id, safe="")
            )
        candidates.append(CandidatePlace(
            place_id=place_id[:300],
            name=name[:180],
            address=entry.get("formattedAddress", "")[:240]
            if isinstance(entry.get("formattedAddress"), str) else "",
            maps_url=maps_url,
        ))
    return DiscoveryOutput(stores=candidates)


async def discover_stores(payload: DiscoveryInput, uid: str) -> DiscoveryOutput:
    # Fail closed to prevent unexpected chargeable requests before configuration.
    if os.environ.get("PLACES_DISCOVERY_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=503, detail="Real store discovery is not enabled yet")
    enforce_rate_limit(uid)
    try:
        # Search for RETAIL BUSINESSES; product stock is never inferred.
        query = f"{payload.product_query} retail stores in {payload.area}"
        results = await _call_places(query)
        return parse_places(results)
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        logging.warning("Places discovery error (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Places discovery unavailable") from exc
    except Exception as exc:
        logging.error("Places discovery unexpected failure (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Places discovery unavailable") from exc
