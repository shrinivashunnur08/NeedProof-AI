"""HTTP API for the commerce loop: /api/v2/loop/*"""
from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from app.commerce_loop import store
from app.commerce_loop.agent import ShopperAgent
from app.commerce_loop.insights import city_demand, demand_brief, export_events_ndjson
from app.commerce_loop.locale import CITIES
from app.commerce_loop.discovery import DiscoveryError, locate
from app.commerce_loop.providers import get_providers, setting
from app.commerce_loop.vision import read_photo

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic"}


def loop_enabled() -> None:
    flag = os.environ.get("COMMERCE_LOOP_ENABLED", "").strip().lower()
    production = os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
    if flag == "false" or (production and flag != "true"):
        raise HTTPException(status_code=503, detail="Commerce loop is disabled")


router = APIRouter(prefix="/api/v2/loop", tags=["commerce-loop"], dependencies=[Depends(loop_enabled)])


def _city(city: str) -> str:
    store.conn()  # loads cities discovered earlier
    if city not in CITIES:
        raise HTTPException(status_code=404, detail="Unknown city")
    return city


@router.get("/status")
def status():
    store.conn()
    return {"providers": get_providers().public_status(),
            "cities": [c for c in CITIES.values() if c.get("demo")],
            "discovery": setting("DISCOVERY", "osm").lower(),
            "data_note": "Shops and listings are fictional demo data."}


@router.get("/cities/{city}/shops")
def city_shops(city: str):
    city = _city(city)
    return [{**s, "listings": store.listings_for(s["id"])} for s in store.shops_in_city(city)]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=2000)


class ChatIn(BaseModel):
    city: str
    history: list[ChatTurn] = Field(min_length=1, max_length=30)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    location_label: str | None = Field(default=None, max_length=120)
    shopper_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{3,40}$")
    shopper_name: str = Field(default="Shopper", max_length=40)


class LocateIn(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    query: str | None = Field(default=None, max_length=120)
    near_city: str | None = None


@router.post("/locate")
def locate_shopper(body: LocateIn):
    """Detected position or typed place -> city, currency and real shops nearby."""
    if body.query is None and (body.lat is None or body.lng is None):
        raise HTTPException(status_code=422, detail="Send lat/lng or a place name")
    try:
        return locate(lat=body.lat, lng=body.lng, query=body.query, near_city=body.near_city)
    except DiscoveryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - network issues with public map services
        raise HTTPException(status_code=502, detail=f"Location service unavailable ({type(exc).__name__})") from exc


@router.post("/agent/chat")
def agent_chat(body: ChatIn):
    city = _city(body.city)
    if body.history[-1].role != "user" or not body.history[-1].text.strip():
        raise HTTPException(status_code=422, detail="Last turn must be a non-empty user message")
    origin = {"lat": body.lat, "lng": body.lng, "label": body.location_label} if body.lat is not None else None
    agent = ShopperAgent(city, origin=origin, shopper_id=body.shopper_id, shopper_name=body.shopper_name)
    return agent.chat([t.model_dump() for t in body.history])


@router.get("/requests/{request_id}")
def get_request(request_id: int):
    req = store.get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return req


def _city_version(city: str) -> str:
    row = store.rows(
        "SELECT (SELECT COALESCE(MAX(id),0) FROM requests WHERE city=?) AS r,"
        " (SELECT COALESCE(MAX(x.id),0) FROM responses x JOIN requests q ON q.id=x.request_id WHERE q.city=?) AS s,"
        " (SELECT COUNT(*) FROM requests WHERE city=?) AS n", (city, city, city))[0]
    return f"{row['r']}-{row['s']}-{row['n']}"


@router.get("/cities/{city}/events")
async def city_events(city: str, request: Request):
    """Server-Sent Events: pushes a new version whenever a request or a shop reply lands in this city."""
    city = _city(city)

    async def stream():
        # Each stream lives at most 60 s; EventSource reconnects on its own. This keeps
        # `uvicorn --reload` and graceful shutdowns from waiting on open connections.
        last, idle, started = None, 0, asyncio.get_running_loop().time()
        yield "retry: 1000\n\n"
        while not await request.is_disconnected() and asyncio.get_running_loop().time() - started < 60:
            version = await asyncio.to_thread(_city_version, city)
            if version != last:
                last, idle = version, 0
                yield f"event: change\ndata: {json.dumps({'version': version})}\n\n"
            else:
                idle += 1
                if idle % 15 == 0:
                    yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.get("/cities/{city}/requests")
def city_requests(city: str):
    return store.open_requests(_city(city))


class PhotoReplyIn(BaseModel):
    shop_id: str
    price: float | None = Field(default=None, ge=0, le=10_000_000)
    stock: int | None = Field(default=None, ge=0, le=100_000)
    image_base64: str | None = Field(default=None, max_length=8_000_000)
    image_mime: str | None = None
    mock_hint: dict | None = Field(default=None, description="Test-only: fields the mock model returns")
    inventory_id: int | None = Field(default=None, description="Inventory row the shopkeeper approved from a draft")
    message: str | None = Field(default=None, max_length=500)
    approved_by_shopkeeper: bool = Field(default=True, description="Drafts are only sent after a person approves")


@router.post("/requests/{request_id}/reply")
def reply_with_photo(request_id: int, body: PhotoReplyIn):
    req = store.get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    shop = store.shop(body.shop_id)
    if not shop or shop["city"] != req["city"]:
        raise HTTPException(status_code=403, detail="This shop cannot reply to a request in another city")
    image = None
    if body.image_base64:
        if (body.image_mime or "") not in ALLOWED_MIME:
            raise HTTPException(status_code=415, detail="Use a JPEG, PNG, WEBP or HEIC photo")
        try:
            data = base64.b64decode(body.image_base64.split(",")[-1], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Image is not valid base64") from exc
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Photo must be under 5 MB")
        image = (data, body.image_mime)
    catalog = False
    item = None
    if body.inventory_id is not None:
        if not body.approved_by_shopkeeper:
            raise HTTPException(status_code=409, detail="A drafted reply must be approved by the shopkeeper first")
        from app.commerce_loop.inventory import catalog_image

        item = store.inventory_item(body.inventory_id)
        if not item or item["shop_id"] != body.shop_id:
            raise HTTPException(status_code=404, detail="Inventory item not found for this shop")
        if image is None:
            image = catalog_image(item)
            catalog = image is not None
    result = read_photo(req, image, body.price, mock_hint=body.mock_hint, catalog=catalog)
    response_id = store.add_response(request_id, body.shop_id, body.price, CITIES[req["city"]]["currency"],
                                     body.stock, result["claim"], result["check"], result["check"]["status"],
                                     message=body.message, evidence_class=result.get("evidence_class"),
                                     inventory_id=item["id"] if item else None)
    return {"response_id": response_id, **result}


# ---------------- shop inventory ----------------
class UploadImage(BaseModel):
    name: str = Field(max_length=120)
    data: str = Field(max_length=7_000_000)
    mime: str


class InventoryUploadIn(BaseModel):
    filename: str = Field(max_length=120)
    sheet_base64: str = Field(max_length=4_000_000)
    images: list[UploadImage] = Field(default_factory=list, max_length=60)


def _shop_or_404(shop_id: str) -> dict:
    shop = store.shop(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop


@router.post("/shops/{shop_id}/inventory")
def upload_inventory(shop_id: str, body: InventoryUploadIn):
    from app.commerce_loop.inventory import import_inventory

    _shop_or_404(shop_id)
    try:
        sheet = base64.b64decode(body.sheet_base64.split(",")[-1], validate=True)
        images = [(i.name, base64.b64decode(i.data.split(",")[-1], validate=True), i.mime) for i in body.images]
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="File is not valid base64") from exc
    if sum(len(d) for _, d, _ in images) > 40 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Photos must total under 40 MB; upload in batches")
    try:
        return import_inventory(shop_id, (sheet, body.filename), images)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/shops/{shop_id}/inventory/sample")
def sample_inventory(shop_id: str):
    from app.commerce_loop.inventory import import_sample

    _shop_or_404(shop_id)
    return import_sample(shop_id)


@router.get("/shops/{shop_id}/inventory")
def list_inventory(shop_id: str):
    from app.commerce_loop.inventory import _image_url

    _shop_or_404(shop_id)
    return [{**i, "image_url": _image_url(i)} for i in store.inventory_for(shop_id)]


@router.get("/inventory/template.xlsx")
def inventory_template():
    from app.commerce_loop.inventory import template_xlsx

    return Response(template_xlsx(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="needproof_inventory_template.xlsx"'})


@router.get("/media/{shop_id}/{name}")
def media(shop_id: str, name: str):
    from app.commerce_loop.inventory import _safe, media_dir

    if _safe(name) != name or _safe(shop_id) != shop_id:
        raise HTTPException(status_code=404, detail="Not found")
    path = media_dir(shop_id) / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=300"})


@router.get("/requests/{request_id}/draft")
def request_draft(request_id: int, shop_id: str):
    """AI search over this shop's inventory -> a reply draft. Never sent without the shopkeeper's approval."""
    from app.commerce_loop.inventory import draft_reply

    req = store.get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    shop = _shop_or_404(shop_id)
    if shop["city"] != req["city"]:
        raise HTTPException(status_code=403, detail="This shop cannot see a request in another city")
    return draft_reply(req, shop_id)


@router.get("/shoppers/{shopper_id}")
def shopper_profile(shopper_id: str):
    return {"profile": store.get_profile(shopper_id)}


@router.delete("/shoppers/{shopper_id}")
def forget_shopper(shopper_id: str):
    """'Forget me': deletes the saved profile. Past requests stay anonymous (no profile link is shown)."""
    store.forget_profile(shopper_id)
    store.execute("UPDATE requests SET shopper_id=NULL WHERE shopper_id=?", (shopper_id,))
    return {"forgotten": True}


@router.get("/cities/{city}/analytics")
def analytics(city: str, shop_id: str | None = None):
    from app.commerce_loop.analytics import shop_analytics

    return shop_analytics(_city(city), shop_id)


@router.get("/cities/{city}/insights")
def insights(city: str):
    return city_demand(_city(city))


class BriefIn(BaseModel):
    language: str = Field(default="en", max_length=10)
    shop_id: str | None = None


@router.post("/cities/{city}/brief")
def brief(city: str, body: BriefIn):
    city = _city(city)
    shop = store.shop(body.shop_id) if body.shop_id else None
    return demand_brief(city, body.language, shop["name"] if shop else None, shop_id=body.shop_id)


@router.get("/models")
def available_models():
    """Model names this key can call (names only), to pick one with quota left."""
    from app.commerce_loop.gemini import Gemini, GeminiUnavailable, _describe

    gem = Gemini()
    if gem.is_mock:
        return {"backend": "mock", "models": []}
    try:
        names = [m.name for m in gem._client().models.list()
                 if "generateContent" in (getattr(m, "supported_actions", None) or ["generateContent"])]
    except GeminiUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=_describe(exc)) from exc
    return {"backend": gem.p.gemini_backend, "current": gem.p.gemini_model,
            "models": sorted(n.removeprefix("models/") for n in names if "gemini" in n)}


@router.post("/demo/reset")
def demo_reset():
    store.reset()
    return {"reset": True}


@router.post("/analytics/export")
def analytics_export():
    path = os.path.join(os.path.dirname(store.db_path()), "demand_events.ndjson")
    return {"rows": export_events_ndjson(path), "path": path,
            "next": "bq load --source_format=NEWLINE_DELIMITED_JSON --autodetect needproof_loop.demand_events " + path}
