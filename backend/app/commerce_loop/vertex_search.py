"""Vertex AI Search over shop inventory (INVENTORY_SEARCH=vertex).

Uploaded inventory rows are indexed as structured documents in a Vertex AI Search data store; a shopper
request is sent as a natural-language query and the hits become candidates for the draft. Code then applies
the same item-type, spec and budget rules as the local search, so Vertex retrieval can widen recall
(synonyms, typos, other languages) but can never put a wrong item into a draft.

Setup (once): create data store `needproof-inventory` and engine `needproof-inventory-search`
(see docs/GOOGLE_CLOUD.md). Uses Application Default Credentials; no API key.
"""
from __future__ import annotations

import logging

import httpx

from app.commerce_loop.providers import get_providers, setting

log = logging.getLogger(__name__)
API = "https://discoveryengine.googleapis.com/v1"


def enabled() -> bool:
    return setting("INVENTORY_SEARCH", "local").lower() == "vertex" and bool(get_providers().gcp_project)


def _paths() -> tuple[str, str]:
    project = get_providers().gcp_project
    base = f"{API}/projects/{project}/locations/global/collections/default_collection"
    store = setting("VERTEX_SEARCH_DATASTORE", "needproof-inventory")
    engine = setting("VERTEX_SEARCH_ENGINE", "needproof-inventory-search")
    return f"{base}/dataStores/{store}/branches/default_branch/documents", \
        f"{base}/engines/{engine}/servingConfigs/default_search:search"


def _headers() -> dict:
    import google.auth
    import google.auth.transport.requests

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())
    return {"Authorization": f"Bearer {creds.token}", "X-Goog-User-Project": get_providers().gcp_project,
            "Content-Type": "application/json"}


def doc_id(shop_id: str, item_id: int) -> str:
    return f"{shop_id}-{item_id}".replace("_", "-")[:60]


def index(shop_id: str, items: list[dict], old_ids: list[int]) -> dict:
    """Replace this shop's documents. Never raises: indexing problems must not block an upload."""
    if not enabled():
        return {"indexed": 0, "backend": "local"}
    docs_url, _ = _paths()
    try:
        headers = _headers()
        with httpx.Client(timeout=30) as client:
            for old in old_ids:
                client.delete(f"{docs_url}/{doc_id(shop_id, old)}", headers=headers)
            docs = [{"id": doc_id(shop_id, it["id"]), "structData": {
                "shop_id": shop_id, "inventory_id": it["id"], "product": it["product"], "brand": it["brand"] or "",
                "sku": it["sku"] or "", "specs": " ".join(f"{k} {v}" for k, v in it["specs"].items()),
                "price": it["price"], "stock": it["stock"]}} for it in items]
            r = client.post(f"{docs_url}:import", headers=headers,
                             json={"inlineSource": {"documents": docs}, "reconciliationMode": "INCREMENTAL"})
            r.raise_for_status()
        return {"indexed": len(docs), "backend": "vertex_ai_search"}
    except Exception as exc:  # noqa: BLE001
        log.warning("Vertex AI Search indexing failed: %s", type(exc).__name__)
        return {"indexed": 0, "backend": "vertex_ai_search", "error": type(exc).__name__}


def query(shop_id: str, text: str, limit: int = 10) -> list[int] | None:
    """Inventory ids for this shop, best first; None means 'use local search instead'."""
    if not enabled():
        return None
    _, search_url = _paths()
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(search_url, headers=_headers(), json={"query": text[:300], "pageSize": 50})
            r.raise_for_status()
        ids = []
        for hit in r.json().get("results", []):
            data = (hit.get("document") or {}).get("structData") or {}
            if data.get("shop_id") == shop_id and data.get("inventory_id") is not None:
                ids.append(int(data["inventory_id"]))
        return ids[:limit]
    except Exception as exc:  # noqa: BLE001
        log.warning("Vertex AI Search query failed: %s", type(exc).__name__)
        return None
