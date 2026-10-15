"""Prevent shipping a Cloud Run decision API without the Chunk 13A route."""

from fastapi.testclient import TestClient
from app.cloud_decision_api import app


def test_cloud_decision_api_route_contract() -> None:
    methods = {(route.path, method) for route in app.routes for method in getattr(route, "methods", set())}
    assert ("/api/v1/discovery/stores", "POST") in methods
    assert ("/api/v1/decision/replan", "POST") in methods
    assert ("/api/v1/decision/verification-plan", "POST") in methods
    assert ("/health", "GET") in methods


def test_discovery_route_rejects_get_instead_of_disappearing() -> None:
    response = TestClient(app).get("/api/v1/discovery/stores")
    assert response.status_code == 405, response.text
