"""One-tap reply links: a real shop answers a shopper's request from WhatsApp, with no app or account.

The link carries an HMAC of (request id, shop id), so it lets exactly that shop answer exactly that request.
The secret comes from LOOP_LINK_SECRET (set on Cloud Run); locally a random secret is kept next to the DB.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from pathlib import Path
from urllib.parse import quote

from app.commerce_loop import store
from app.commerce_loop.providers import setting


def _secret() -> bytes:
    configured = setting("LOOP_LINK_SECRET")
    if configured:
        return configured.encode()
    path = Path(store.db_path()).resolve().parent / ".reply_link_secret"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(32))
    return path.read_text().strip().encode()


def token(request_id: int, shop_id: str) -> str:
    mac = hmac.new(_secret(), f"{request_id}:{shop_id}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")[:24]


def valid(request_id: int, shop_id: str, value: str | None) -> bool:
    return bool(value) and hmac.compare_digest(token(request_id, shop_id), value or "")


def whatsapp_number(phone: str | None) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    return digits if 8 <= len(digits) <= 15 else None


def link(base_url: str, request: dict, shop: dict) -> dict:
    url = f"{base_url.rstrip('/')}/r/{request['id']}?shop={quote(shop['id'])}&t={token(request['id'], shop['id'])}"
    specs = ", ".join(f"{k.replace('_w', '').replace('_', ' ')} {v}" for k, v in (request.get("specs") or {}).items())
    budget = f" Budget {request['currency']} {request['budget']:g}." if request.get("budget") else ""
    text = (f"Hi {shop['name']}, a shopper nearby is looking for: {request['product']}"
            f"{' (' + specs + ')' if specs else ''}.{budget} Do you have it today? "
            f"Reply with one photo of the box or label here: {url}")
    number = whatsapp_number(shop.get("phone"))
    return {"url": url, "text": text, "phone": shop.get("phone"),
            "whatsapp_url": f"https://wa.me/{number}?text={quote(text)}" if number else f"https://wa.me/?text={quote(text)}",
            "direct": bool(number)}
