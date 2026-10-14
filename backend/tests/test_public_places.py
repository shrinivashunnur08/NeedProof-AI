"""No live Places calls; tests are free and deterministic."""
import asyncio

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import public_places as places


def test_candidate_results_do_not_claim_stock():
    response = places.parse_places({"places": [
        {"id": "test-1", "displayName": {"text": "Sample Electronics"},
         "formattedAddress": "Example Road", "googleMapsUri": "https://www.google.com/maps/place/sample"},
        {"id": "test-1", "displayName": {"text": "Duplicate"}},
        {"id": "test-2", "displayName": {"text": "Unsafe"}, "googleMapsUri": "javascript:alert(1)"},
    ]})
    assert len(response.stores) == 2
    assert response.status == "CANDIDATES_ONLY"
    assert response.stores[0].inventory_status == "UNKNOWN"
    assert response.stores[0].verification_status == "NOT_VERIFIED"
    assert response.stores[1].maps_url.startswith("https://www.google.com/maps/search/")


def test_invalid_requests_rejected():
    with pytest.raises(ValidationError):
        places.DiscoveryInput(product_query="a", area="Thane")
    with pytest.raises(ValidationError):
        places.DiscoveryInput(product_query="USB charger", area="")


def test_feature_flag_off_makes_no_paid_calls(monkeypatch):
    monkeypatch.setenv("PLACES_DISCOVERY_ENABLED", "false")
    async def should_not_run(_q):
        raise AssertionError("No upstream Places request should be made")
    monkeypatch.setattr(places, "_call_places", should_not_run)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(places.discover_stores(
            places.DiscoveryInput(product_query="65W charger", area="Thane"), "user-1"
        ))
    assert caught.value.status_code == 503


def test_enabled_search_requests_candidates(monkeypatch):
    monkeypatch.setenv("PLACES_DISCOVERY_ENABLED", "true")
    places._recent_users.clear()
    places._recent_all.clear()
    search_queries = []
    async def mock_search(query):
        search_queries.append(query)
        return {"places": [{"id": "test-place", "displayName": {"text": "Test Store"}}]}
    monkeypatch.setattr(places, "_call_places", mock_search)
    result = asyncio.run(places.discover_stores(
        places.DiscoveryInput(product_query="USB-C charger", area="Thane"), "user-1"
    ))
    assert result.stores[0].name == "Test Store"
    assert search_queries == ["USB-C charger retail stores in Thane"]
    assert "stock" in result.disclaimer.lower()


def test_limit_denies_before_paid_call(monkeypatch):
    monkeypatch.setenv("PLACES_DISCOVERY_ENABLED", "true")
    places._recent_users.clear()
    places._recent_all.clear()
    called = 0
    async def mock_search(query):
        nonlocal called
        called += 1
        return {"places": []}
    monkeypatch.setattr(places, "_call_places", mock_search)
    payload = places.DiscoveryInput(product_query="USB-C charger", area="Thane")
    for _ in range(3):
        asyncio.run(places.discover_stores(payload, "same-user"))
    with pytest.raises(HTTPException) as caught:
        asyncio.run(places.discover_stores(payload, "same-user"))
    assert caught.value.status_code == 429
    assert called == 3
