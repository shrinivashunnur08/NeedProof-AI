
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.algorithms.evsi import bayes_update
from app.main import app


client = TestClient(app)


def test_bayesian_update():
    posterior = bayes_update(
        Decimal("0.6"),
        Decimal("0.9"),
        Decimal("0.8"),
        True,
    )

    assert float(posterior) == pytest.approx(
        0.8709677419354839
    )


def test_demo_selects_harbor():
    response = client.get(
        "/api/decisions/demo-plan"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["mode"] == "SYNTHETIC_RESEARCH_SCENARIO"
    assert data["recommended_action_id"] == "VERIFY_A"

    harbor = next(
        item for item in data["actions"]
        if item["action_id"] == "VERIFY_A"
    )

    assert harbor["net_evsi_inr"] == "81.20"


def test_expensive_verification_changes_decision():
    response = client.get(
        "/api/decisions/demo-plan",
        params={"a_verification_cost_inr": 300},
    )

    assert response.status_code == 200

    assert (
        response.json()["recommended_action_id"]
        == "VERIFY_B"
    )


def test_short_deadline_stops_investigation():
    response = client.get(
        "/api/decisions/demo-plan",
        params={"deadline_minutes": 1},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["recommended_action_id"] is None
    assert data["stopping_reason"] is not None


def test_invalid_prior_is_rejected():
    response = client.get(
        "/api/decisions/demo-plan",
        params={"a_prior": 1.5},
    )

    assert response.status_code == 422


def test_bayesian_impossible_observation():
    with pytest.raises(ValueError):
        bayes_update(
            Decimal("0"),
            Decimal("1"),
            Decimal("1"),
            True,
        )
