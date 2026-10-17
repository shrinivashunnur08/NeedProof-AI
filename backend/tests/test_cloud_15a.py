"""15A regression: bounded body for streamed requests + security headers.

No token, cloud calls, database writes or production network requests.
"""
import os
os.environ.setdefault("FIREBASE_PROJECT_ID", "test-firebase-project")
os.environ.setdefault("FIREBASE_WEB_APP_ID", "1:000:web:test")
os.environ.setdefault("ALLOWED_ORIGINS", "https://needproof-ai-showcase.web.app")

import asyncio
import json

from fastapi.testclient import TestClient
from app.api_guard_15a import BoundedAPIGuard15A, MAX_BODY_BYTES
from app.cloud_decision_api import app, require_firebase_client


def test_health_unchanged_with_security_headers():
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["x-frame-options"] == "DENY"


def test_authenticated_body_not_modified():
    app.dependency_overrides[require_firebase_client] = lambda: "test-user"
    try:
        r = TestClient(app).post("/api/v1/decision/verification-plan", json={})
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-store"
    finally:
        app.dependency_overrides.clear()


def test_auth_still_fail_closed():
    assert TestClient(app).post("/api/v1/decision/verification-plan", json={}).status_code == 401


def test_large_declared_length_rejected_without_auth():
    r = TestClient(app).post("/api/v1/decision/verification-plan", data=b"x" * (MAX_BODY_BYTES+1), headers={"content-type":"application/json"})
    assert r.status_code == 413
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-frame-options"] == "DENY"


def test_invalid_content_length_400():
    async def handler(scope, receive, send):
        await send({"type":"http.response.start","status":200,"headers":[]})
        await send({"type":"http.response.body","body":b"OK"})
    output = asyncio.run(_asgi_call(BoundedAPIGuard15A(handler),
        [(b"content-length",b"garbage")],[{"type":"http.request","body":b"x","more_body":False}]))
    assert output[0]["status"] == 400


async def _asgi_call(guard, headers, parts, method="POST"):
    scope={"type":"http","method":method,"path":"/api/v1/test","headers":headers,"asgi":{"version":"3.0"}}
    sent=[]
    queue=list(parts)
    async def receive():
        return queue.pop(0) if queue else {"type":"http.disconnect"}
    async def send(msg):
        sent.append(msg)
    await guard(scope, receive, send)
    return sent


def test_streaming_without_content_length_overflow_rejected():
    seen=[]
    async def handler(scope, receive, send):
        seen.append(await receive())
        await send({"type":"http.response.start","status":200,"headers":[]})
        await send({"type":"http.response.body","body":b"OK"})
    parts=[
        {"type":"http.request","body":b"a"*20000,"more_body":True},
        {"type":"http.request","body":b"b"*12769,"more_body":False},
    ]
    sent=asyncio.run(_asgi_call(BoundedAPIGuard15A(handler),[],parts))
    assert sent[0]["status"] == 413
    assert not seen, "Must reject before parsing/processing request"
    assert b"nosniff" in [v for k,v in sent[0]["headers"]]


def test_streaming_at_exact_boundary_replayed_once():
    seen=[]
    async def handler(scope, receive, send):
        seen.append(await receive())
        await send({"type":"http.response.start","status":200,"headers":[]})
        await send({"type":"http.response.body","body":b"OK"})
    parts=[
        {"type":"http.request","body":b"a"*20000,"more_body":True},
        {"type":"http.request","body":b"b"*12768,"more_body":False},
    ]
    sent=asyncio.run(_asgi_call(BoundedAPIGuard15A(handler),[],parts))
    assert sent[0]["status"] == 200
    assert len(seen)==1 and len(seen[0]["body"])==MAX_BODY_BYTES
    assert seen[0]["more_body"] is False


def test_headless_get_passthrough_without_consuming_body():
    received=[]
    async def handler(scope, receive, send):
        received.append(scope["method"])
        await send({"type":"http.response.start","status":200,"headers":[]})
        await send({"type":"http.response.body","body":b"OK"})
    sent=asyncio.run(_asgi_call(BoundedAPIGuard15A(handler),[],[],method="GET"))
    assert received==["GET"] and sent[0]["status"]==200


def test_existing_cache_header_is_not_overwritten():
    async def handler(scope, receive, send):
        await send({"type":"http.response.start","status":200,"headers":[(b"cache-control",b"private, max-age=0")]})
        await send({"type":"http.response.body","body":b""})
    sent=asyncio.run(_asgi_call(BoundedAPIGuard15A(handler),[],[],method="GET"))
    assert [(k,v) for k,v in sent[0]["headers"] if k==b"cache-control"] == [(b"cache-control",b"private, max-age=0")]


def test_duplicate_content_length_is_rejected():
    async def handler(scope,receive,send):
        raise AssertionError("must not reach handler")
    sent=asyncio.run(_asgi_call(BoundedAPIGuard15A(handler),[(b"content-length",b"1"),(b"content-length",b"1")],[]))
    assert sent[0]["status"] == 400


def test_route_flags_still_off_by_default():
    names=["BI_COMMAND_CENTER_14B4_ENABLED","INVENTORY_INTELLIGENCE_14B3_ENABLED","RETAIL_INSIGHTS_14B2_ENABLED", "RETAIL_FORECAST_14B1_ENABLED"]
    assert all(os.environ.get(name,"false").strip().lower() != "true" for name in names)
