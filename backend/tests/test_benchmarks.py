
import pytest
from fastapi.testclient import TestClient

from app.api.merchant_onboarding import local_only
from app.benchmarks.engine import run_benchmarks
from app.main import app


@pytest.fixture(scope="module")
def results():
    return run_benchmarks(
        seed=42,
        basket_scenarios=12,
        evidence_trials=100,
    )


def test_reproducibility(results):
    repeated = run_benchmarks(
        seed=42,
        basket_scenarios=12,
        evidence_trials=100,
    )

    assert repeated == results


def test_trial_counts(results):
    assert len(results["basket"]["trials"]) == 12
    assert len(results["evidence"]["trials"]) == 100

    assert results["mode"] == "SYNTHETIC_BENCHMARK"


def test_optimizer_respects_budget(results):
    for trial in results["basket"]["trials"]:
        optimized = trial["results"]["NEEDPROOF_ORTOOLS"]

        if optimized["feasible"]:
            assert (
                optimized["total_minor"]
                <= trial["budget_inr"] * 100
            )


def test_ortools_dominates_feasible_baselines(results):
    for trial in results["basket"]["trials"]:
        optimized = trial["results"]["NEEDPROOF_ORTOOLS"]

        for name in ("CHEAPEST_FIRST", "SINGLE_MERCHANT"):
            baseline = trial["results"][name]

            if optimized["feasible"] and baseline["feasible"]:
                assert (
                    optimized["total_minor"]
                    <= baseline["total_minor"]
                )


def test_evidence_policy_check_counts(results):
    for trial in results["evidence"]["trials"]:
        policies = trial["results"]

        assert policies["NO_VERIFICATION"]["checks"] == 0
        assert policies["VERIFY_EVERYTHING"]["checks"] == 2
        assert policies["EVSI_ONE_STEP"]["checks"] in (0, 1)


def test_evidence_summary_has_realized_metrics(results):
    for name in (
        "EVSI_ONE_STEP",
        "VERIFY_EVERYTHING",
        "NO_VERIFICATION",
    ):
        metrics = results["evidence"]["summary"][name]

        assert isinstance(
            metrics["average_realized_net_utility_inr"],
            (int, float),
        )

        assert (
            0 <= metrics["failed_selection_rate_pct"] <= 100
        )


def test_benchmark_endpoint():
    app.dependency_overrides[local_only] = lambda: None

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/benchmarks/run",
                params={
                    "seed": 7,
                    "basket_scenarios": 5,
                    "evidence_trials": 20,
                },
            )

            assert response.status_code == 200
            assert response.json()["seed"] == 7

            invalid = client.get(
                "/api/benchmarks/run",
                params={"basket_scenarios": 200},
            )

            assert invalid.status_code == 422
    finally:
        app.dependency_overrides.pop(local_only, None)
