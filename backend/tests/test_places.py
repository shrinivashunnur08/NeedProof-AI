
import json

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.api.places import get_places_service
from app.services.places_service import (
    PlacesService,
    PlacesConfigurationError,
)

client = TestClient(app)


def test_places_service_maps_real_fields():
    def handler(request: httpx.Request):
        assert request.method == "POST"

        assert request.url.path == "/v1/places:searchText"

        assert request.headers["X-Goog-Api-Key"] == "test-key"

        assert "places.displayName.text" in (
            request.headers["X-Goog-FieldMask"]
        )

        body = json.loads(request.content)

        assert body["textQuery"] == (
            "electronics stores in Thane, Maharashtra, India"
        )

        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        "id": "ChIJ_TEST_PLACE",
                        "displayName": {
                            "text": "Example Electronics"
                        },
                        "formattedAddress": (
                            "Example Road, Thane, Maharashtra"
                        ),
                        "googleMapsUri": (
                            "https://maps.google.com/?cid=123"
                        ),
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    service = PlacesService("test-key", transport=transport)

    result = service.search("Thane", "electronics")

    assert len(result.merchants) == 1

    merchant = result.merchants[0]

    assert merchant.name == "Example Electronics"
    assert merchant.is_simulated is False
    assert merchant.stock_status == "UNKNOWN"
    assert merchant.price_status == "UNKNOWN"
    assert merchant.compatibility_status == "UNKNOWN"


def test_missing_api_key():
    service = PlacesService("")

    try:
        service.search("Thane", "electronics")
        assert False, "Expected configuration error"
    except PlacesConfigurationError:
        pass


def test_places_api_route():
    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        "id": "TEST_ID",
                        "displayName": {
                            "text": "Test Computer Store"
                        },
                        "formattedAddress": "Dombivli, Maharashtra",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)

    app.dependency_overrides[get_places_service] = (
        lambda: PlacesService("test-key", transport=transport)
    )

    try:
        response = client.get(
            "/api/places/merchants",
            params={
                "area": "Dombivli",
                "category": "computer",
            },
        )

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"

        data = response.json()

        assert data["mode"] == "LIVE_DISCOVERY"
        assert len(data["merchants"]) == 1

        merchant = data["merchants"][0]

        assert merchant["name"] == "Test Computer Store"
        assert merchant["price_status"] == "UNKNOWN"

    finally:
        app.dependency_overrides.clear()


def test_invalid_search_location():
    response = client.get(
        "/api/places/merchants",
        params={"area": "UnknownCityXYZ"},
    )

    assert response.status_code == 422
